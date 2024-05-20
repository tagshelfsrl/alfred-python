# Native imports
import base64
import hashlib
import hmac
import os
from datetime import datetime
from typing import Dict, Any
from urllib.parse import quote
from time import time, sleep
from uuid import uuid4
from xml.etree import ElementTree as ET

# 3rd party imports
from requests import Session, Request, PreparedRequest, Response
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Project imports
from .typed import *  # pylint: disable=W0401, W0614
from ..base.constants import RESPONSE_TYPE_HEADER_MAPPING
from ..base.exceptions import AlfredMissingAuthException
from ..utils import logging


class HttpClient:
    base_url: Text
    max_retries: int
    timeout: float
    session: Session
    auth_config: AuthConfiguration
    auth_method: Optional[AuthMethod] = None
    token: Optional[Text] = None
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
            attempt (default: 3).
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
        if self.max_retries <= 0:
            raise ValueError(
                f"Max retries ({self.max_retries}) cannot be zero or less."
            )
        retry_strategy = Retry(
            total=self.max_retries,
            status_forcelist=[429, 500, 502, 503, 504],
            backoff_factor=1,
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
            pool_maxsize = min(32, os.cpu_count() + 4)

        adapter = HTTPAdapter(
            pool_maxsize=pool_maxsize,
            pool_connections=pool_size,
            max_retries=retry_strategy,
        )
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

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
        Intercepts the response and raises an exception if the status code is not 200.
        """
        # Extract rate limit headers
        self.rate_limit = {
            "limit": int(response.headers.get("X-RateLimit-Limit", 0)),
            "remaining": int(response.headers.get("X-RateLimit-Remaining", 0)),
            "reset_time": datetime.utcfromtimestamp(
                int(response.headers.get("X-RateLimit-Reset", 0))
            ),
        }

        # if the response is unauthorized, attempt to re-authenticate OAuth
        if (
            response.status_code == 401
            and self.auth_method == AuthMethod.OAUTH
            and self.refresh_token_retry_count == 0
        ):
            self.refresh_token_retry_count += 1
            self.token = None
            self.__auth_with_oauth(response.request)
            response = self.session.send(response.request)
            if response.status_code != 401:
                self.refresh_token_retry_count = 0
            return response

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
        """
        data = {"grant_type": "password", "username": username, "password": password}
        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        _, response = self.request(
            HttpMethod.POST,
            "/token",
            data=data,
            headers=headers,
            skip_auth=True,
        )
        response_json = response.json()
        return response_json.get("access_token")

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

        if prepped_request.body:
            md5_hash = hashlib.md5()
            md5_hash.update(prepped_request.body.encode("utf-8"))
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

    def __get_headers(self, headers: Optional[Dict[str, str]]) -> Dict[str, str]:
        """
        Get the request headers.

        Args:
        - headers: HTTP headers
        """
        headers = headers or {}
        default_headers = {
            "Accept-Charset": "utf-8",
            "Content-Type": "application/json",
            "Accept": RESPONSE_TYPE_HEADER_MAPPING.get(self.response_type),
        }

        return {**default_headers, **headers}

    @staticmethod
    def __parse_response(response: Response):
        """
        Parse the response based on the response type.

        Args:
        - response: HTTP response
        """

        # Get the response type based on the content type header.
        content_type = response.headers.get("Content-Type").split(";")[0]
        reversed_response_type_header_mapping = {
            v: k for k, v in RESPONSE_TYPE_HEADER_MAPPING.items()
        }
        response_type = reversed_response_type_header_mapping.get(content_type)

        try:
            if response_type == ResponseType.XML:
                return ET.fromstring(response.text)
            elif response_type == ResponseType.JSON:
                return response.json()
            elif response_type == ResponseType.TEXT:
                return response.text
            else:
                return response.text
        except Exception as e:
            raise ValueError(f"Failed to parse response: {e}")

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
        if timeout is None:
            timeout = self.timeout
        elif timeout <= 0:
            raise ValueError(timeout)

        headers = self.__get_headers(headers)
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

        response = self.session.send(prepped_request, timeout=timeout)

        response.raise_for_status()
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
        if self.rate_limit and self.throttle_threshold > 0:
            remaining = self.rate_limit.get("remaining", 0)
            limit = self.rate_limit.get("limit", 0)

            if remaining <= 0:
                self.throttle_delay = min(self.throttle_delay * self.throttle_delay_backoff, self.throttle_delay_max)
                return True
            else:
                # Reset the throttle delay in case the rate limit has been reset.
                self.throttle_delay = self.__initial_throttle_delay

                # Check if the remaining rate limit is less than the threshold.
                return (remaining / limit) * 100 <= self.throttle_threshold
        return False

    def throttle_request(self, delay: float = 1.0):
        """
        Throttle the request by delaying for a given time.
        """
        if self.should_throttle():
            logging.warning("Rate limit is close to being reached. Throttling request.")
            sleep(delay)

    def __logger_interceptor(self, response: Response, *args, **kwargs):
        """
        Log the HTTP status code and response body of erroneous responses.
        """

        # Log detailed HTTP request information.
        body = (
            response.request.body
            if not isinstance(response.request.body, bytes)
            else ""
        )
        self.logger.debug(
            {
                "message": "HTTP request details.",
                "method": response.request.method,
                "url": response.request.url,
                "headers": {
                    k: v
                    for k, v in response.request.headers.items()
                    if k.lower() not in ["authorization", "cookie", "x-tagshelfapi-key"]
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
