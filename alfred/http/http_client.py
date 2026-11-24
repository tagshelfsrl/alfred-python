# Native imports
import base64
import hashlib
import hmac
import logging
import os
from datetime import datetime, timezone
from importlib import metadata
from typing import Dict, Any
from urllib.parse import quote, urlsplit
from time import time, sleep
from uuid import uuid4
from xml.etree import ElementTree as ET

# 3rd party imports
from requests import Session, Request, PreparedRequest, Response
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import ConnectTimeout, RequestException, Timeout
from requests.adapters import HTTPAdapter
from urllib3.exceptions import ReadTimeoutError
from urllib3.util.retry import Retry

# Project imports
from .typed import *  # pylint: disable=W0401, W0614
from ..base.typed import ResponseType
from ..base.constants import RESPONSE_TYPE_HEADER_MAPPING
from ..base.exceptions import AlfredMissingAuthException
from ..exceptions import (
    AlfredApiError,
    AlfredAuthenticationError,
    AlfredConnectionError,
    AlfredConnectTimeoutError,
    AlfredRequestError,
    AlfredResponseParseError,
    AlfredTimeoutError,
    MAX_MESSAGE_LENGTH,
    parse_retry_after,
)

# Statuses urllib3 retries. Only for methods urllib3 considers idempotent
# (GET, HEAD, PUT, DELETE, OPTIONS, TRACE): a POST is never re-sent because of
# a status, since the server may already have acted on it.
RETRY_STATUS_FORCELIST = (429, 500, 502, 503, 504)

# Headers that must never reach the logs.
SENSITIVE_HEADERS = ("authorization", "proxy-authorization", "cookie", "x-tagshelfapi-key")


class _Retry(Retry):
    """
    Retry policy that never fails on the Retry-After header.

    urllib3 raises InvalidHeader for a Retry-After value it cannot read, from
    inside the send, so the answer (its status, its body) would never reach
    the caller. The header is read with the SDK's own parser instead, which
    also accepts fractional seconds; a value that cannot be read counts as
    absent, and the ordinary backoff applies.
    """

    def parse_retry_after(self, retry_after):
        seconds = parse_retry_after(retry_after)
        return seconds if seconds is not None else 0


def _default_user_agent() -> Text:
    """
    Descriptive User-Agent. The API rejects requests that have none.
    """
    try:
        return f"alfred-python/{metadata.version('alfred-python')}"
    except Exception:  # pylint: disable=broad-except
        return "alfred-python"


def _cap_detail(text: Text, query: Text) -> Text:
    """
    Shorten the text of a transport error and remove the URL query string,
    which could carry keys.
    """
    if query:
        text = text.replace(query, "[query removed]")
    text = " ".join(text.split())
    if len(text) > MAX_MESSAGE_LENGTH:
        text = text[: MAX_MESSAGE_LENGTH - 3] + "..."
    return text


def _to_int(value: Any) -> Optional[int]:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


class HttpClient:
    base_url: Text
    max_retries: int
    timeout: float
    session: Session
    auth_config: AuthConfiguration
    auth_method: Optional[AuthMethod] = None
    token: Optional[Text] = None
    # Kept for backward compatibility; the token refresh no longer needs a counter.
    refresh_token_retry_count: int = 0
    response_type: ResponseType = ResponseType.JSON
    rate_limit: Optional[Dict[str, Any]] = None
    __initial_throttle_delay: float
    throttle_delay: float
    throttle_threshold: int
    throttle_delay_backoff: float = 2
    throttle_delay_max: float = 60

    def __init__(
        self,
        base_url: Text,
        auth_config: AuthConfiguration,
        config: Optional[HttpConfiguration] = None,
    ) -> None:
        """
        Constructor for base HTTP client.

        Args:
        - base_url: Base URL of the API.
        - config: HTTP client configuration.
            - config.pool_connections: If True, the requests Session will use
            pool connections (default: True).
            - config.timeout: Timeout for the requests in seconds. Should be higher than
            zero (default: 5).
            - config.max_retries: Maximum number of retries each request should
            attempt (default: 3). Zero disables retries.
            - config.retry_backoff_factor: Backoff factor between retries in seconds
            (default: 1). Zero retries without waiting.
            - config.response_type {ResponseType}: Specifies the expected format of the response data (default: JSON).
            - config.throttle_delay: Delay in seconds to throttle requests (default: 1).
            - config.throttle_threshold: Percentage of rate limit remaining to throttle requests (default: 20).
                Set to 0 to disable throttling. 20 means that if the remaining rate limit is less than 20%
                of the total rate limit, the http client will throttle the request.
        """
        self.base_url = base_url
        self.session = Session()
        self.auth_config = auth_config
        config = config or {}

        # Initialize logger
        self.logger = logging.getLogger("alfred-python")

        # Setup retry strategy
        self.max_retries = config.get("max_retries", 3)
        if self.max_retries < 0:
            raise ValueError(f"Max retries ({self.max_retries}) cannot be negative.")
        self.retry_backoff_factor = config.get("retry_backoff_factor", 1)
        if self.retry_backoff_factor < 0:
            raise ValueError(
                f"Retry backoff factor ({self.retry_backoff_factor}) cannot be negative."
            )
        # raise_on_status=False: when retries run out the caller gets the last
        # response, which becomes a typed error with the server's message,
        # instead of an opaque requests RetryError.
        retry_strategy = _Retry(
            total=self.max_retries,
            status_forcelist=list(RETRY_STATUS_FORCELIST),
            backoff_factor=self.retry_backoff_factor,
            respect_retry_after_header=True,
            raise_on_status=False,
        )

        # Setup timeout
        self.timeout = config.get("timeout", 5)
        if self.timeout <= 0:
            raise ValueError(f"Timeout ({self.timeout}) cannot be zero or less.")

        # Set up response type
        self.response_type = config.get("response_type", ResponseType.JSON)

        # Validate that it's a valid response type.
        if self.response_type not in RESPONSE_TYPE_HEADER_MAPPING.keys():
            raise ValueError(f"Invalid response type: {self.response_type}")

        # Setup throttle delay
        self.throttle_delay = config.get("throttle_delay", 1)
        self.throttle_threshold = config.get("throttle_threshold", 20)
        self.__initial_throttle_delay = self.throttle_delay

        # Setup pool connections
        pool_size = 1
        pool_maxsize = 1
        if config.get("pool_connections", True):
            pool_size = 10
            pool_maxsize = min(32, (os.cpu_count() or 1) + 4)

        adapter = HTTPAdapter(
            pool_maxsize=pool_maxsize,
            pool_connections=pool_size,
            max_retries=retry_strategy,
        )
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        self.session.headers["User-Agent"] = _default_user_agent()

        # Setup API key (if any)
        self.__auth_with_api_key(self.auth_config.get("api_key"))

        # Setup OAuth (if any)
        if not self.auth_method and self.auth_config.get("oauth"):
            self.auth_method = AuthMethod.OAUTH

        # Setup HMAC
        if not self.auth_method and self.auth_config.get("hmac"):
            self.auth_method = AuthMethod.HMAC

        if not self.auth_method:
            raise AlfredMissingAuthException

        # Setup interceptor
        self.session.hooks["response"].append(self.__response_interceptor)
        self.session.hooks["response"].append(self.__logger_interceptor)

    def __response_interceptor(self, response: Response, *args, **kwargs):
        """
        Records the rate limit headers of every response. Missing or malformed
        headers mean "unknown", never "zero".
        """
        limit = _to_int(response.headers.get("X-RateLimit-Limit"))
        remaining = _to_int(response.headers.get("X-RateLimit-Remaining"))
        reset = _to_int(response.headers.get("X-RateLimit-Reset"))

        reset_time = None
        if reset is not None:
            try:
                reset_time = datetime.fromtimestamp(reset, tz=timezone.utc).replace(
                    tzinfo=None
                )
            except (OverflowError, OSError, ValueError):
                reset_time = None

        if limit is None and remaining is None and reset_time is None:
            self.rate_limit = None
        else:
            self.rate_limit = {
                "limit": limit,
                "remaining": remaining,
                "reset_time": reset_time,
            }

    def __auth_with_api_key(self, api_key: Text):
        """
        Set the X-TagshelfAPI-Key header using the provided API key or a
        default value from the environment variable.

        Args:
        - api_key: A string that represents an API key used for authentication.
          If no value is provided, the function will attempt to retrieve the API key from
          the environment variable.
        """
        key = api_key or os.getenv("ALFRED_API_KEY")
        if not key:
            return

        self.session.headers.update({"X-TagshelfAPI-Key": key})
        self.auth_method = AuthMethod.API_KEY

    def __auth_with_oauth(self, prepped_request: PreparedRequest):
        """
        Handles authentication using OAuth by obtaining an access token and
        setting it in the HTTP headers.

        Args:
        - prepped_request: Prepared Request object.
        """
        username = self.auth_config.get("oauth", {}).get("username")
        password = self.auth_config.get("oauth", {}).get("password")
        if not self.token:
            self.token = self.__get_token(username, password)

        prepped_request.headers.update({"Authorization": f"Bearer {self.token}"})

    def __get_token(self, username: Text, password: Text):
        """
        Get access token.

        Args:
        - username: A string that represents the username used for authentication.
        - password: A string that represents the user's password used for authentication.

        Raises AlfredAuthenticationError if the API refuses the credentials or
        answers without an access token. A rate limit or a server failure while
        asking for the token raises AlfredRateLimitError or AlfredServerError.
        """
        data = {"grant_type": "password", "username": username, "password": password}
        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        response = self.__perform(
            HttpMethod.POST,
            "/token",
            data=data,
            headers=headers,
            skip_auth=True,
            error_class=AlfredAuthenticationError,
        )

        def failure(message: Text):
            # Built from the response, so the error carries what the API sent.
            return AlfredAuthenticationError.from_response(response, message)

        try:
            response_json = response.json()
        except ValueError as exc:
            raise failure("The token response was not valid JSON.") from exc

        token = response_json.get("access_token") if isinstance(response_json, dict) else None
        if not isinstance(token, str) or not token:
            raise failure("The token response did not contain an access_token.")
        return token

    def __auth_with_hmac(self, prepped_request: PreparedRequest):
        """
        Generates a HMAC-based authentication header for API requests using provided
        API key and secret key.

        Args:
        - prepped_request: Prepared Request object.
        """
        api_key = self.auth_config.get("hmac", {}).get("api_key")
        secret_key = self.auth_config.get("hmac", {}).get("secret_key")

        nonce = str(uuid4())
        request_uri = quote(prepped_request.url, safe="").lower()
        request_method = prepped_request.method.upper()
        request_timestamp = str(int(time()))
        request_content = ""

        # requests produces a str body for form data and bytes for JSON and multipart.
        body = prepped_request.body
        if isinstance(body, str):
            body = body.encode("utf-8")
        if isinstance(body, (bytes, bytearray)) and body:
            md5_hash = hashlib.md5()
            md5_hash.update(body)
            request_content = base64.b64encode(md5_hash.digest()).decode("utf-8")

        # Prepare the signature
        signature_raw_data = (
            secret_key
            + request_method
            + request_uri
            + request_timestamp
            + nonce
            + request_content
        )
        signature = signature_raw_data.encode("utf-8")

        # Create HMAC signature
        secret_byte_array = base64.b64decode(api_key)
        hmac_signature = hmac.new(secret_byte_array, signature, hashlib.sha256).digest()
        signature_base64 = base64.b64encode(hmac_signature).decode("utf-8")

        # Prepare the Authorization header
        hmac_key = f"amx {secret_key}:{signature_base64}:{nonce}:{request_timestamp}"
        prepped_request.headers.update({"Authorization": hmac_key})

    def __get_headers(self, headers: Optional[Dict[str, str]], has_files: bool = False) -> Dict[str, str]:
        """
        Get the request headers.

        Args:
        - headers: HTTP headers
        """
        headers = headers or {}
        default_headers = {
            "Accept-Charset": "utf-8",
            "Accept": RESPONSE_TYPE_HEADER_MAPPING.get(self.response_type),
        }

        # Set default Content-Type only if it's not a file upload
        if "Content-Type" not in headers and not has_files:
            default_headers["Content-Type"] = "application/json"

        return {**default_headers, **headers}

    @staticmethod
    def __parse_response(response: Response):
        """
        Parse the response based on the response type.

        Args:
        - response: HTTP response
        """

        # An empty body (204, empty 200) has nothing to parse.
        if not response.content:
            return None

        # Get the response type based on the content type header. Without one, treat it as text.
        content_type = (response.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        reversed_response_type_header_mapping = {
            v: k for k, v in RESPONSE_TYPE_HEADER_MAPPING.items()
        }
        response_type = reversed_response_type_header_mapping.get(content_type)

        try:
            if response_type == ResponseType.XML:
                return ET.fromstring(response.text)
            elif response_type == ResponseType.JSON:
                return response.json()
            else:
                return response.text
        except Exception as e:
            raise AlfredResponseParseError(
                f"Failed to parse response: {e}", response=response
            ) from e

    def __send(self, prepped_request: PreparedRequest, timeout: float) -> Response:
        """
        Sends a prepared request, turning transport failures into SDK errors.
        """
        try:
            return self.session.send(prepped_request, timeout=timeout)
        except RequestException as exc:
            method = prepped_request.method
            url = prepped_request.url
            # urllib3 messages quote the URL, query string included.
            detail = _cap_detail(str(exc), urlsplit(url).query)
            kwargs = {"method": method, "url": url, "request": prepped_request}
            # When urllib3 runs out of retries on a read timeout, requests reports a
            # ConnectionError whose reason is the timeout: it is still a timeout.
            reason = getattr(exc.args[0], "reason", None) if exc.args else None
            if isinstance(exc, ConnectTimeout):
                error = AlfredConnectTimeoutError(f"Connection timed out: {detail}", **kwargs)
            elif isinstance(exc, Timeout) or isinstance(reason, ReadTimeoutError):
                error = AlfredTimeoutError(f"Request timed out: {detail}", **kwargs)
            elif isinstance(exc, RequestsConnectionError):
                error = AlfredConnectionError(f"Connection failed: {detail}", **kwargs)
            else:
                error = AlfredRequestError(f"Request failed: {detail}", **kwargs)
            raise error from exc

    def __perform(
        self,
        method: HttpMethod,
        uri: Text,
        params: Optional[Dict[str, object]] = None,
        data: Optional[Dict[str, object]] = None,
        headers: Optional[Dict[str, str]] = None,
        files: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
        skip_auth: Optional[bool] = False,
        error_class: Optional[type] = None,
    ) -> Response:
        """
        Sends the request and returns the response, or raises for 4xx/5xx.
        """
        if timeout is None:
            timeout = self.timeout
        elif timeout <= 0:
            raise ValueError(timeout)

        headers = self.__get_headers(headers, has_files=bool(files))
        url = self.base_url + uri

        kwargs = {
            "method": method.value,
            "url": url,
            "params": params,
            "headers": headers,
            "files": files,
        }

        if headers and headers.get("Content-Type") == "application/json":
            kwargs["json"] = data
        else:
            kwargs["data"] = data

        request = Request(**kwargs)
        prepped_request = self.session.prepare_request(request)

        if not skip_auth:
            if self.auth_method == AuthMethod.OAUTH:
                self.__auth_with_oauth(prepped_request)

            elif self.auth_method == AuthMethod.HMAC:
                self.__auth_with_hmac(prepped_request)

        self.throttle_request(self.throttle_delay)

        response = self.__send(prepped_request, timeout)

        # The token may have expired: fetch a new one and send the request once more.
        if (
            response.status_code == 401
            and not skip_auth
            and self.auth_method == AuthMethod.OAUTH
        ):
            self.token = None
            self.__auth_with_oauth(prepped_request)
            response = self.__send(prepped_request, timeout)

        if response.status_code >= 400:
            # error_class says what a refusal of this request means (a refused
            # token request is an authentication failure). A rate limit or a
            # server failure keeps its own class: it says nothing about the caller.
            status = response.status_code
            if error_class is not None and status != 429 and status < 500:
                raise error_class.from_response(response)
            raise AlfredApiError.from_response(response)
        return response

    def request(
        self,
        method: HttpMethod,
        uri: Text,
        params: Optional[Dict[str, object]] = None,
        data: Optional[Dict[str, object]] = None,
        headers: Optional[Dict[str, str]] = None,
        files: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
        skip_auth: Optional[bool] = False,
    ):
        """
        Makes a request to the Alfred API using the configured HTTP client.

        Args:
        - method: HTTP method.
        - uri: Fully qualified URI.
        - params: Query string parameters.
        - data: Body data.
        - headers: HTTP headers.
        - timeout: Timeout for the requests in seconds.
        """
        response = self.__perform(
            method, uri, params, data, headers, files, timeout, skip_auth
        )
        return self.__parse_response(response), response

    def get(
        self,
        uri: Text,
        params: Optional[Dict[str, object]] = None,
        data: Optional[Dict[str, object]] = None,
        headers: Optional[Dict[str, str]] = None,
        files: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ):
        """
        Makes a GET request to the Alfred API.

        Args:
        - uri: Fully qualified URI.
        - params: Query string parameters.
        - data: Body data.
        - headers: HTTP headers.
        - files: Files to upload.
        - timeout: Timeout for the requests in seconds.
        """
        return self.request(HttpMethod.GET, uri, params, data, headers, files, timeout)

    def post(
        self,
        uri: Text,
        params: Optional[Dict[str, object]] = None,
        data: Optional[Dict[str, object]] = None,
        headers: Optional[Dict[str, str]] = None,
        files: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ):
        """
        Makes a POST request to the Alfred API.

        Args:
        - uri: Fully qualified URI.
        - params: Query string parameters.
        - data: Body data.
        - headers: HTTP headers.
        - files: Files to upload.
        - timeout: Timeout for the requests in seconds.
        """
        return self.request(HttpMethod.POST, uri, params, data, headers, files, timeout)

    def put(
        self,
        uri: Text,
        params: Optional[Dict[str, object]] = None,
        data: Optional[Dict[str, object]] = None,
        headers: Optional[Dict[str, str]] = None,
        files: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ):
        """
        Makes a PUT request to the Alfred API.

        Args:
        - uri: Fully qualified URI.
        - params: Query string parameters.
        - data: Body data.
        - headers: HTTP headers.
        - files: Files to upload.
        - timeout: Timeout for the requests in seconds.
        """
        return self.request(HttpMethod.PUT, uri, params, data, headers, files, timeout)

    def delete(
        self,
        uri: Text,
        params: Optional[Dict[str, object]] = None,
        data: Optional[Dict[str, object]] = None,
        headers: Optional[Dict[str, str]] = None,
        files: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ):
        """
        Makes a DELETE request to the Alfred API.

        Args:
        - uri: Fully qualified URI.
        - params: Query string parameters.
        - data: Body data.
        - headers: HTTP headers.
        - files: Files to upload.
        - timeout: Timeout for the requests in seconds.
        """
        return self.request(
            HttpMethod.DELETE, uri, params, data, headers, files, timeout
        )

    def should_throttle(self) -> bool:
        """
        Check if the client should throttle requests based on rate limiting headers.
        """

        # We should throttle if the remaining rate limit is less than the threshold in percentage.
        # For example, if the rate limit is 100 and the remaining is 20, we should throttle.
        # If the rate limit is 100 and the remaining is 80, we should not throttle.
        # Missing headers mean the limit is unknown, and then we never throttle.
        if not self.rate_limit or self.throttle_threshold <= 0:
            return False

        remaining = self.rate_limit.get("remaining")
        limit = self.rate_limit.get("limit")

        if remaining is None or (limit is not None and limit <= 0):
            self.throttle_delay = self.__initial_throttle_delay
            return False

        if remaining <= 0:
            self.throttle_delay = min(
                self.throttle_delay * self.throttle_delay_backoff,
                self.throttle_delay_max,
            )
            return True

        # Reset the throttle delay in case the rate limit has been reset.
        self.throttle_delay = self.__initial_throttle_delay

        # Check if the remaining rate limit is less than the threshold.
        return limit is not None and (remaining / limit) * 100 <= self.throttle_threshold

    def throttle_request(self, delay: float = 1.0):
        """
        Throttle the request by delaying for a given time.
        """
        if self.should_throttle():
            self.logger.warning("Rate limit is close to being reached. Throttling request.")
            sleep(delay)

    def __logger_interceptor(self, response: Response, *args, **kwargs):
        """
        Log the HTTP status code and response body of erroneous responses.
        """

        # Log detailed HTTP request information.
        # The token request carries the username and password: never log its body.
        is_token_request = (
            urlsplit(response.request.url).path.rstrip("/").lower().endswith("/token")
        )
        if is_token_request:
            body = "[redacted]"
        elif isinstance(response.request.body, bytes):
            body = ""
        else:
            body = response.request.body
        self.logger.debug(
            {
                "message": "HTTP request details.",
                "method": response.request.method,
                "url": response.request.url,
                "headers": {
                    k: v
                    for k, v in response.request.headers.items()
                    if k.lower() not in SENSITIVE_HEADERS
                },
                "body": body,
            }
        )

        # Log response details if not successful.
        if not response.ok:
            self.logger.debug(
                {
                    "message": "HTTP response details.",
                    "method": response.request.method,
                    "url": response.request.url,
                    "status_code": response.status_code,
                    "body": response.text,
                    "response_size": len(response.content),
                    "response_content_type": response.headers.get("Content-Type"),
                }
            )
