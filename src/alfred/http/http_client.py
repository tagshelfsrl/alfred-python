# Native imports
import os
from enum import Enum
from typing import TypedDict, Optional, Text, Dict, Any

# 3rd party imports
from urllib3.util.retry import Retry
from requests import Session, Request
from requests.adapters import HTTPAdapter


class HttpMethod(Enum):
    POST = "POST"
    GET = "GET"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"
    HEAD = "HEAD"


class OAuthConfiguration(TypedDict):
    username: Text
    password: Text


class HmacConfiguration(TypedDict):
    api_key: Text
    secret_key: Text


class AuthConfiguration(TypedDict):
    api_key: Optional[Text]
    oauth: Optional[OAuthConfiguration]
    hmac: Optional[HmacConfiguration]


class HttpConfiguration(TypedDict):
    pool_connections: Optional[bool]
    timeout: Optional[float]
    max_retries: Optional[int]


class HttpClient:
    def __init__(
        self,
        base_url: Text,
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

    def request(
        self,
        method: HttpMethod,
        uri: Text,
        params: Optional[Dict[str, object]] = None,
        data: Optional[Dict[str, object]] = None,
        headers: Optional[Dict[str, str]] = None,
        files: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
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

        headers = self.get_headers({})
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
        response = self.session.send(prepped_request, timeout=timeout)

        response.raise_for_status()
        return response

    def get_headers(self, headers: Optional[Dict[str, str]]) -> Dict[str, str]:
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
