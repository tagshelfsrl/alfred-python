# Native imports
from enum import Enum
from typing import TypedDict, Optional, Text


class HttpMethod(Enum):
    POST = "POST"
    GET = "GET"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"
    HEAD = "HEAD"


class AuthMethod(Enum):
    API_KEY = ("apikey",)
    OAUTH = ("oauth",)
    HMAC = ("hmac",)


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