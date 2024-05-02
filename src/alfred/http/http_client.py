# Native imports
import os
import hmac
import base64
import hashlib
from time import time
from uuid import uuid4
from urllib.parse import quote
from typing import Optional, Text, Dict, Any

# 3rd party imports
from urllib3.util.retry import Retry
from requests import Session, Request, PreparedRequest
from requests.adapters import HTTPAdapter

# Project imports
from .typed import *  # pylint: disable=W0401, W0614
from ..base.exceptions import AlfredMissingAuthException


class HttpClient:
    base_url: Text
    max_retries: int
    timeout: float
    session: Session
    auth_config: AuthConfiguration
    auth_method: Optional[AuthMethod] = None
    token: Optional[Text] = None

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
        """
        self.base_url = base_url
        self.session = Session()
        self.auth_config = auth_config
        config = config or {}

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

    def __auth_with_api_key(self, api_key: Text):
        """
        Set the X-TagshelfAPI-Key header using the provided API key or a
        default value from the environment variable.

        Args:
        - api_key: A string that represents an API key used for authentication.
          If no value is provided, the function will attempt to retrieve the API key from
          the environment variable.
        """
        key = api_key
        if not key:
            key = os.getenv("ALFRED_API_KEY")

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

        response = self.request(
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
        }

        return {**default_headers, **headers}

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

        response = self.session.send(prepped_request, timeout=timeout)

        response.raise_for_status()
        return response
