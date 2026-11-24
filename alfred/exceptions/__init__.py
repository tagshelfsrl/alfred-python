"""
Exceptions raised by the Alfred SDK.

Everything the SDK raises on purpose derives from :class:`AlfredError`. The
errors that describe a failed HTTP call also inherit from the matching
``requests`` exception, so code written against ``requests`` keeps working.

This module must not import anything else from the ``alfred`` package: both
``alfred.base`` and ``alfred.http`` import it.
"""
# Native imports
import html
import json
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from http import HTTPStatus
from typing import Any, Dict, Optional, Text, Type
from urllib.parse import urlsplit, urlunsplit

# 3rd party imports
import requests

__all__ = [
    "AlfredError",
    "AlfredMissingAuthException",
    "AlfredMissingArgument",
    "ConnectionError",
    "AlfredRequestError",
    "AlfredConnectionError",
    "AlfredTimeoutError",
    "AlfredConnectTimeoutError",
    "AlfredResponseParseError",
    "AlfredApiError",
    "AlfredBadRequestError",
    "AlfredAuthenticationError",
    "AlfredPermissionError",
    "AlfredNotFoundError",
    "AlfredConflictError",
    "AlfredPayloadTooLargeError",
    "AlfredRateLimitError",
    "AlfredServerError",
]

# Longest message kept from a server answer. Keeps an HTML error page out of
# exception messages and logs.
MAX_MESSAGE_LENGTH = 300

_JSON_START = ('{', '[', '"')
_HTML_BLOCKS = re.compile(r"<(script|style)\b.*?</\1\s*>", re.IGNORECASE | re.DOTALL)
_HTML_TAGS = re.compile(r"<[^>]*>")
_SECONDS = re.compile(r"^\d+(\.\d+)?$")
_MESSAGE_KEYS = ("message", "Message", "error_description", "error", "detail")


class AlfredError(Exception):
    """
    Base class of every exception the Alfred SDK raises on purpose.
    """


class AlfredMissingAuthException(AlfredError):
    """
    Raised when proper authentication/authorization have not been provided.
    """


class AlfredMissingArgument(AlfredError):
    """
    Raised when a payload is missing a required argument based on the whole context
    of the operation.
    """


class ConnectionError(AlfredError):  # pylint: disable=redefined-builtin
    """
    Raised when the realtime connection cannot be established.
    """

    def __init__(self, message="A connection error occurred"):
        self.message = message
        super().__init__(self.message)


def _safe_url(url: Optional[Text]) -> Optional[Text]:
    """
    Return the URL without credentials, query string or fragment, so it can be
    shown in messages and logs.
    """
    if not url:
        return None
    try:
        parts = urlsplit(url)
        netloc = parts.netloc.rpartition("@")[2]
        return urlunsplit((parts.scheme, netloc, parts.path, "", ""))
    except ValueError:
        return None


def _cap(text: Text, limit: int = MAX_MESSAGE_LENGTH) -> Text:
    text = " ".join(text.split())
    if len(text) > limit:
        return text[: limit - 3].rstrip() + "..."
    return text


def _clean_text(text: Text) -> Text:
    """
    Reduce server text to a short single line. Markup is removed first, so an
    HTML error page from a gateway yields its visible words, not its source.
    """
    if text.lstrip().startswith("<"):
        text = _HTML_BLOCKS.sub(" ", text)
        text = html.unescape(_HTML_TAGS.sub(" ", text))
    return _cap(text)


def _message_from_body(body: Any) -> Optional[Text]:
    """
    Pull the most human-readable message out of a parsed error body.
    """
    if isinstance(body, str):
        return _clean_text(body) or None
    if isinstance(body, dict):
        for key in _MESSAGE_KEYS:
            value = body.get(key)
            if isinstance(value, (str, dict)):
                found = _message_from_body(value)
                if found:
                    return found
    return None


def _string_field(body: Any, *names: Text) -> Optional[Text]:
    if isinstance(body, dict):
        for name in names:
            value = body.get(name)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def _int_field(body: Any, name: Text) -> Optional[int]:
    if not isinstance(body, dict):
        return None
    value = body.get(name)
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def _parse_body(response: requests.Response) -> Any:
    """
    Return the parsed JSON body, the text, or None when the body is empty.
    Never raises: a body that claims to be JSON but is not is returned as text.
    """
    try:
        text = response.text
    except Exception:  # pylint: disable=broad-except
        return None
    if not text or not text.strip():
        return None
    content_type = (response.headers.get("Content-Type") or "").lower()
    if "json" in content_type or text.lstrip().startswith(_JSON_START):
        try:
            return json.loads(text)
        except ValueError:
            pass
    return text


def parse_retry_after(value: Optional[Text]) -> Optional[float]:
    """
    Convert a ``Retry-After`` header (seconds or an HTTP date) to seconds.
    Returns None when the header is absent or not understood.
    """
    if not value:
        return None
    value = value.strip()
    if _SECONDS.match(value):
        return float(value)
    try:
        when = parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError):
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return max(0.0, (when - datetime.now(timezone.utc)).total_seconds())


def _phrase(status_code: Optional[int], response: Optional[requests.Response]) -> Text:
    reason = getattr(response, "reason", None)
    if isinstance(reason, str) and reason.strip():
        return reason.strip()
    try:
        return HTTPStatus(status_code).phrase
    except ValueError:
        return "Error"


def _describe(method: Optional[Text], url: Optional[Text]) -> Text:
    return " ".join(part for part in (method, url) if part)


class AlfredRequestError(AlfredError, requests.exceptions.RequestException):
    """
    The request never produced an answer from the API (network failure).

    Attributes:
    - message: What went wrong, without the query string of the URL.
    - method, url: The request that failed; url has no query string.
    - request: The prepared ``requests`` request.
    """

    def __init__(
        self,
        message: Optional[Text] = None,
        *,
        method: Optional[Text] = None,
        url: Optional[Text] = None,
        request: Any = None,
    ):
        self.message = message or "The request failed"
        self.method = method
        self.url = _safe_url(url)
        text = self.message
        target = _describe(method, self.url)
        if target:
            text = f"{target}: {text}"
        super().__init__(text, request=request)


class AlfredConnectionError(AlfredRequestError, requests.exceptions.ConnectionError):
    """
    DNS failure, refused or reset connection, TLS failure.
    """


class AlfredTimeoutError(AlfredRequestError, requests.exceptions.Timeout):
    """
    The API did not answer within the timeout.
    """


class AlfredConnectTimeoutError(
    AlfredTimeoutError, AlfredConnectionError, requests.exceptions.ConnectTimeout
):
    """
    The connection could not be opened within the timeout. It is both a
    timeout and a connection error, like ``requests.exceptions.ConnectTimeout``.
    """


class AlfredResponseParseError(AlfredError, ValueError):
    """
    A successful response whose body could not be parsed.

    Attributes:
    - response: The ``requests`` response.
    - status_code: HTTP status of that response.
    """

    def __init__(self, message: Text, *, response: Any = None):
        self.response = response
        self.status_code = getattr(response, "status_code", None)
        super().__init__(message)


class AlfredApiError(AlfredError, requests.exceptions.HTTPError):
    """
    The API answered with a 4xx or 5xx status.

    Use :meth:`from_response` to build the right subclass for a response.

    Attributes:
    - status_code: HTTP status code.
    - message: Best human-readable message found in the answer.
    - reason: The server's machine-readable ``reason``, when it sent one.
    - correlation_id: The server's error reference for support, when present.
      It is not the correlation id of a job.
    - body: Parsed JSON body, the text of a non-JSON body, or None if empty.
    - response, request: The ``requests`` objects.
    - method, url: The request; url has no query string or credentials.
    """

    def __init__(
        self,
        message: Optional[Text] = None,
        *,
        status_code: Optional[int] = None,
        reason: Optional[Text] = None,
        correlation_id: Optional[Text] = None,
        body: Any = None,
        response: Any = None,
        request: Any = None,
        method: Optional[Text] = None,
        url: Optional[Text] = None,
    ):
        if request is None and response is not None:
            request = getattr(response, "request", None)
        self.status_code = status_code
        self.reason = reason
        self.correlation_id = correlation_id
        self.body = body
        self.method = method
        self.url = _safe_url(url)
        phrase = _phrase(status_code, response)
        self.message = message or phrase
        text = " ".join(
            part
            for part in (str(status_code) if status_code is not None else "", phrase)
            if part
        )
        target = _describe(method, self.url)
        if target:
            text = f"{text} for {target}" if text else target
        if self.message != phrase:
            text = f"{text}: {self.message}" if text else self.message
        super().__init__(text or self.message, response=response, request=request)

    @classmethod
    def from_response(
        cls, response: requests.Response, message: Optional[Text] = None
    ) -> "AlfredApiError":
        """
        Build the exception for an error response.

        Called on :class:`AlfredApiError` itself the class is chosen from the
        status code; called on a subclass that class is used.
        """
        status = response.status_code
        error_class = cls if cls is not AlfredApiError else _class_for_status(status)
        body = _parse_body(response)
        request = getattr(response, "request", None)
        kwargs: Dict[str, Any] = {
            "status_code": status,
            "message": message or _message_from_body(body) or _phrase(status, response),
            "reason": _string_field(body, "reason"),
            "correlation_id": _string_field(body, "correlation_id", "correlationId"),
            "body": body,
            "response": response,
            "request": request,
            "method": getattr(request, "method", None),
            "url": getattr(request, "url", None) or response.url,
        }
        if issubclass(error_class, (AlfredRateLimitError, AlfredServerError)):
            kwargs["retry_after"] = parse_retry_after(response.headers.get("Retry-After"))
        if issubclass(error_class, AlfredPayloadTooLargeError):
            kwargs["max_bytes"] = _int_field(body, "max_bytes")
        return error_class(**kwargs)


class AlfredBadRequestError(AlfredApiError):
    """400: the request was rejected as invalid."""


class AlfredAuthenticationError(AlfredApiError):
    """401, or any failure to obtain an OAuth token."""


class AlfredPermissionError(AlfredApiError):
    """403: authenticated, but not allowed (role, suspended account, user agent)."""


class AlfredNotFoundError(AlfredApiError):
    """404: the resource does not exist (or is not visible to the caller)."""


class AlfredConflictError(AlfredApiError):
    """409: the resource is in a state that refuses the operation."""


class AlfredPayloadTooLargeError(AlfredApiError):
    """
    413: the file or body is over the size limit.

    Attribute ``max_bytes``: the limit reported by the server, or None.
    """

    def __init__(self, *args, max_bytes: Optional[int] = None, **kwargs):
        self.max_bytes = max_bytes
        super().__init__(*args, **kwargs)


class AlfredRateLimitError(AlfredApiError):
    """
    429: too many calls.

    Attribute ``retry_after``: seconds to wait from the ``Retry-After``
    header, or None when the server did not send a usable one.
    """

    def __init__(self, *args, retry_after: Optional[float] = None, **kwargs):
        self.retry_after = retry_after
        super().__init__(*args, **kwargs)


class AlfredServerError(AlfredApiError):
    """
    5xx: the server or a gateway in front of it failed.

    Attribute ``retry_after``: seconds from the ``Retry-After`` header, or None.
    """

    def __init__(self, *args, retry_after: Optional[float] = None, **kwargs):
        self.retry_after = retry_after
        super().__init__(*args, **kwargs)


_STATUS_CLASSES: Dict[int, Type[AlfredApiError]] = {
    400: AlfredBadRequestError,
    401: AlfredAuthenticationError,
    403: AlfredPermissionError,
    404: AlfredNotFoundError,
    409: AlfredConflictError,
    413: AlfredPayloadTooLargeError,
    429: AlfredRateLimitError,
}


def _class_for_status(status_code: int) -> Type[AlfredApiError]:
    if status_code in _STATUS_CLASSES:
        return _STATUS_CLASSES[status_code]
    if 500 <= status_code <= 599:
        return AlfredServerError
    return AlfredApiError
