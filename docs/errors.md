# Error handling

Every call the SDK makes to the Alfred API either returns its parsed result or raises an exception that derives from `alfred.exceptions.AlfredError`. This page lists those exceptions, says when each is raised, shows how to handle the common cases, and explains what the client retries by itself.

Errors that describe a failed HTTP call also inherit from the matching exception in the `requests` library, so code that already catches `requests.exceptions.HTTPError` or `requests.exceptions.RequestException` keeps working.

## Setup

```python
from alfred.base.config import Configuration
from alfred.http.typed import AuthConfiguration
from alfred.rest import AlfredClient

client = AlfredClient(
    config=Configuration.v1(),
    auth_config=AuthConfiguration({"api_key": "YOUR_API_KEY"}),
)
```

All exceptions are importable from `alfred.exceptions`. The examples below also use the client's raw HTTP layer, `client.http_client`, for endpoints that the typed helpers do not wrap. It raises the same exceptions.

## Exception hierarchy

```text
AlfredError                         Base of everything the SDK raises on purpose.
|-- AlfredMissingAuthException      No API key, OAuth or HMAC credentials were given.
|-- AlfredMissingArgument           A required argument is missing from a call (for example a file name).
|-- ConnectionError                 The realtime (socket) connection could not be opened. Not a requests error.
|-- AlfredRequestError              The request never produced an answer from the API. Also a requests RequestException.
|   |-- AlfredConnectionError       DNS failure, refused or reset connection, TLS failure. Also a requests ConnectionError.
|   |-- AlfredTimeoutError          The API did not answer within the timeout. Also a requests Timeout.
|       |-- AlfredConnectTimeoutError   The connection could not be opened in time. Also an AlfredConnectionError.
|-- AlfredResponseParseError        A successful response whose body could not be parsed. Also a ValueError.
|-- AlfredApiError                  The API answered with a 4xx or 5xx status. Also a requests HTTPError.
    |-- AlfredBadRequestError       400
    |-- AlfredAuthenticationError   401, or a refused OAuth token request
    |-- AlfredPermissionError       403
    |-- AlfredNotFoundError         404
    |-- AlfredConflictError         409
    |-- AlfredPayloadTooLargeError  413 (has max_bytes)
    |-- AlfredRateLimitError        429 (has retry_after)
    |-- AlfredServerError           500-599 (has retry_after)
```

`AlfredMissingAuthException` and `AlfredMissingArgument` can also be imported from `alfred.base.exceptions`. Any 4xx status without its own class (for example 422) raises a plain `AlfredApiError`.

`ConnectionError` in `alfred.exceptions` is the SDK's own class and shadows the Python built-in of the same name when imported with `from alfred.exceptions import *`. Import it as `alfred.exceptions.ConnectionError`.

## Status codes

| Status | Exception | Typical cause | What to do |
| --- | --- | --- | --- |
| 400 | `AlfredBadRequestError` | A parameter or body is invalid, or the server refused an operation that does not qualify (for example re-processing a file in the wrong state). | Fix the request. Read `message`, `reason` and `errors`. Do not retry unchanged. |
| 401 | `AlfredAuthenticationError` | Missing, wrong or revoked API key; invalid HMAC signature; bad OAuth credentials or an expired token. | Check the credentials. With OAuth the client already refreshed the token once (see below). |
| 403 | `AlfredPermissionError` | The account lacks a role the call needs (for example the job `full` view needs the Account Admin role), or the account is suspended. | Change the request or the account's permissions. Do not retry. |
| 404 | `AlfredNotFoundError` | The job or file does not exist or is not visible to this account. The body is empty, so `message` is `Not Found`. | Check the id. Treat as "absent" if that is a valid outcome for you. |
| 409 | `AlfredConflictError` | The resource is busy or in a state that refuses the operation (a running file, a job being cancelled or restarted). | Wait and retry later, or read `reason` and `message` to see why. |
| 413 | `AlfredPayloadTooLargeError` | The file is over the size limit. | Send a smaller file. `max_bytes` has the limit when the server reports it. |
| 429 | `AlfredRateLimitError` | More than 2500 calls in a minute. | Wait `retry_after` seconds (or about a minute when it is `None`), then retry. |
| 500-599 | `AlfredServerError` | The API failed, or a gateway in front of it did (the body can be HTML or empty). | The client already retried idempotent calls. Retry later; give `correlation_id` to support if present. |
| other 4xx | `AlfredApiError` | A status without a dedicated class. | Read `status_code` and `message`. |

## What an API error carries

Every `AlfredApiError` has these attributes:

| Attribute | Meaning |
| --- | --- |
| `status_code` | The HTTP status code. |
| `message` | The best human-readable message found in the answer. It is taken from `message`, `Message`, `error_description`, `error` or `detail` in a JSON object, from a bare JSON string, or from plain text. HTML is reduced to its visible words, whitespace is collapsed and the text is capped at 300 characters. With an empty body it is the HTTP reason phrase, for example `Not Found`. |
| `reason` | The server's machine-readable `reason` when the body has one (for example `sources-missing` when a job restart is refused), otherwise `None`. |
| `correlation_id` | The server's error reference when the body has one, otherwise `None`. See below. |
| `errors` | The individual reasons as a list of strings, when the body lists them under `errors` (a refused classification request does), otherwise an empty list. When the body has no other message, `message` is these reasons joined with `; `. |
| `body` | The parsed JSON body (a dict, list or string), the text of a body that is not JSON, or `None` when the body is empty. |
| `response` | The `requests.Response`. |
| `request` | The `requests.PreparedRequest`. |
| `method` | The HTTP method, for example `GET`. |
| `url` | The request URL without credentials, query string or fragment. The full URL is on `request.url`. |

`AlfredRateLimitError` and `AlfredServerError` also have `retry_after` (seconds as a float, or `None`). `AlfredPayloadTooLargeError` also has `max_bytes` (an int, or `None`).

`str(error)` reads like this and never contains request headers, credentials or the query string:

```text
403 Forbidden for GET https://app.tagshelf.com/api/job/detail/0a1b2c3d: The full view needs the Account Admin role; an API key has it.
```

When the answer has no message, the reason phrase is not repeated: `404 Not Found for GET https://app.tagshelf.com/api/job/detail/0a1b2c3d`.

The API has no single error format. Bodies seen in practice are `{"message": "..."}`, `{"message": "...", "correlation_id": "..."}`, `{"error": "...", "statusCode": 400}`, `{"errors": ["...", "..."]}`, `{"error": "invalid_grant", "error_description": "..."}`, a bare JSON string (file re-extract and re-process), plain text, HTML from a gateway, and an empty body. The SDK handles all of them, and a body that claims to be JSON but is not never causes a second exception.

### The correlation id is a support reference

When the server fails a request it can add `correlation_id` to the body, a short code such as `3f9a1c07b2de`. It identifies that one failure in the server's logs. It is not the correlation id of a job. Quote it when you contact support, and log it with your own request context.

## Handling common cases

### Job not found

```python
from alfred.exceptions import AlfredNotFoundError

try:
    job = client.jobs.get("00000000-0000-0000-0000-000000000000")
except AlfredNotFoundError as error:
    print(error)  # 404 Not Found for GET https://app.tagshelf.com/api/job/detail/0000...
    job = None
```

### Permission denied on the full job view

Asking for a job's `full` view needs the Account Admin role. An API key has it; other credentials may not. Fall back to the `summary` view:

```python
from alfred.exceptions import AlfredPermissionError

job_id = "0a1b2c3d-0000-0000-0000-000000000000"
try:
    job, _ = client.http_client.get(
        f"/api/job/detail/{job_id}", params={"view": "full"}
    )
except AlfredPermissionError as error:
    print(error.status_code, error.message)
    job, _ = client.http_client.get(
        f"/api/job/detail/{job_id}", params={"view": "summary"}
    )
```

### Busy, retry later (409)

Re-processing a file answers 409 when the file or its job is busy, and 400 when the file does not qualify. In both cases the body is a plain sentence that ends up in `message`.

```python
import time

from alfred.exceptions import AlfredBadRequestError, AlfredConflictError

file_id = "5e6f7a8b-0000-0000-0000-000000000000"
for attempt in range(5):
    try:
        client.http_client.post(f"/api/file/reprocess/{file_id}")
        break
    except AlfredConflictError as error:
        print(f"Busy: {error.message}")
        time.sleep(2 ** attempt)
    except AlfredBadRequestError as error:
        print(f"Not eligible: {error.message}")
        break
```

Job restart refusals add a machine-readable `reason` (for example `sources-missing`) next to the message; read it from `error.reason`.

### Rate limited (429)

The API allows 2500 calls per minute. The client already retries a rate-limited GET, PUT or DELETE (see below). A POST is not retried, and a call that is still limited after the retries raises `AlfredRateLimitError`:

```python
import time

from alfred.exceptions import AlfredRateLimitError

try:
    page = client.jobs.get_all(page_size=100, current_page=1)
except AlfredRateLimitError as error:
    wait = error.retry_after if error.retry_after is not None else 60
    time.sleep(wait)
    page = client.jobs.get_all(page_size=100, current_page=1)
```

`retry_after` comes from the `Retry-After` header, given in seconds or as an HTTP date. It is `None` when the server did not send a usable header.

### File too large (413)

```python
import tempfile

from alfred.exceptions import AlfredPayloadTooLargeError

with tempfile.NamedTemporaryFile(suffix=".pdf") as handle:
    handle.write(b"%PDF-1.4 ...")
    handle.flush()
    with open(handle.name, "rb") as upload:
        try:
            client.files.upload_file(
                {"file": upload, "filename": "scan.pdf", "session_id": "SESSION_ID"}
            )
        except AlfredPayloadTooLargeError as error:
            limit = error.max_bytes
            print("Over the limit" + (f" of {limit} bytes" if limit else ""))
```

### Timeouts and connection failures

These errors mean the API never answered, so there is no `status_code`.

```python
from alfred.exceptions import (
    AlfredConnectionError,
    AlfredRequestError,
    AlfredTimeoutError,
)

try:
    job = client.jobs.get("0a1b2c3d-0000-0000-0000-000000000000")
except AlfredTimeoutError:
    print("The API took longer than the timeout.")
except AlfredConnectionError as error:
    print(f"Could not reach the API: {error}")
except AlfredRequestError as error:
    print(f"The request failed: {error}")
```

A connect timeout is both a timeout and a connection error (`AlfredConnectTimeoutError`), so it is caught by the first matching `except` clause. Put the order you want first. The original `requests` or urllib3 exception is available as `error.__cause__`. The error message never contains the query string of the URL.

### Catching everything

```python
from alfred.exceptions import AlfredApiError, AlfredError, AlfredRequestError

try:
    job = client.jobs.get("0a1b2c3d-0000-0000-0000-000000000000")
except AlfredApiError as error:
    print(error.status_code, error.message, error.correlation_id)
except AlfredRequestError as error:
    print(f"No answer from the API: {error}")
except AlfredError as error:
    print(f"Other SDK error: {error}")
```

`AlfredError` also covers missing credentials, missing arguments, unparsable successful responses and realtime connection errors. A bug in your own code, or a bad URL passed to the client, still raises the usual Python or `requests` exception.

## Automatic retries and timeouts

The HTTP client uses urllib3's retry logic. These are the rules, which come from urllib3 2.2:

| Failure | GET, PUT, DELETE | POST, PATCH |
| --- | --- | --- |
| Status 429, 500, 502, 503 or 504 | Retried | Not retried: the server may already have acted. |
| Connection could not be opened (refused, DNS, connect timeout) | Retried | Retried: nothing was sent. |
| Read timeout or connection dropped after sending | Retried | Not retried. |
| Any other status (400, 401, 403, 404, 409, 413, 501, ...) | Not retried | Not retried. |

HEAD, OPTIONS and TRACE follow the GET column. A `Retry-After` header on a 413, 429 or 503 answer to GET, PUT or DELETE is also honoured as a reason to retry.

- Each call is sent once plus up to `max_retries` retries.
- Before the first retry the client does not wait. Later retries wait `retry_backoff_factor * 2 ** (n - 1)` seconds, where `n` is the retry number, capped at 120 seconds. With the defaults the waits are 0, 2 and 4 seconds.
- When the server sends `Retry-After`, the client waits that long instead. This wait is not capped, so a server that asks for a long wait makes the call block for that long.
- When retries run out, you get the typed error built from the last answer, with the real message and body, not a generic retry error.
- The OAuth token request is a POST and is not retried. If the API answers a call with 401 while using OAuth, the client discards the token, fetches a new one and sends the call once more, using the same timeout. If the API refuses to issue the token you get `AlfredAuthenticationError`; if the token endpoint is rate limited or failing you get `AlfredRateLimitError` or `AlfredServerError`, since neither says anything about your credentials.

Settings go in the HTTP configuration passed to the client:

```python
from alfred.base.config import Configuration
from alfred.http.typed import AuthConfiguration, HttpConfiguration
from alfred.rest import AlfredClient

http_config = HttpConfiguration(
    {
        "timeout": 10,
        "max_retries": 5,
        "retry_backoff_factor": 0.5,
    }
)
client = AlfredClient(
    config=Configuration.v1(),
    auth_config=AuthConfiguration({"api_key": "YOUR_API_KEY"}),
    http_config=http_config,
)
```

| Setting | Default | Meaning |
| --- | --- | --- |
| `timeout` | `5` | Seconds to wait for the connection and for each read. Must be above zero. A single call can override it with its `timeout` argument. |
| `max_retries` | `3` | Retries per call. `0` turns retries off. Negative values raise `ValueError`. |
| `retry_backoff_factor` | `1` | Base of the wait between retries, in seconds. `0` retries without waiting. Negative values raise `ValueError`. |
| `throttle_threshold` | `20` | The client slows down when the remaining rate limit is at or below this percentage of the limit. `0` turns throttling off. |
| `throttle_delay` | `1` | Seconds to sleep before a request while throttling. It doubles, up to 60 seconds, while the remaining count is zero, and resets when it recovers. |
| `pool_connections` | `True` | Use a connection pool. |
| `response_type` | `ResponseType.JSON` | Format requested in the `Accept` header. |

Because the timeout applies to each attempt, a GET that keeps timing out can take about `timeout * (max_retries + 1)` seconds plus the waits before it raises `AlfredTimeoutError`.

### Throttling

When a response has `X-RateLimit-Limit` and `X-RateLimit-Remaining` headers, the client records them in `client.http_client.rate_limit` (with `limit`, `remaining` and `reset_time`) and sleeps before the next request if little is left. A response without these headers, or with values that are not numbers, means the limit is unknown, and the client does not throttle. It never uses the reset time to decide anything, because the server's value is not reliable.

## Responses that cannot be parsed

A successful response is parsed according to its `Content-Type`: JSON, XML or text. A response without a content type is treated as text, and an empty body (for example a 204) returns `None`. A body that cannot be parsed raises `AlfredResponseParseError`, which is also a `ValueError`. Its `response` attribute holds the raw response.

## Compatibility with code that catches requests exceptions

Existing integrations keep working. This code behaves as before, and `status_code` is now also available on the error itself:

```python
import requests

try:
    client.jobs.get("0a1b2c3d-0000-0000-0000-000000000000")
except requests.exceptions.HTTPError as error:
    print(error.response.status_code)
except requests.exceptions.RequestException as error:
    print("Network problem", error)
```

What changed for existing code:

- Error messages are now the server's message instead of the generic `404 Client Error: Not Found for url: ...`.
- A call that ran out of retries on 429 or 5xx raises `AlfredRateLimitError` or `AlfredServerError` (an `HTTPError`), where it used to raise `requests.exceptions.RetryError`.
- A GET that times out on every retry raises `AlfredTimeoutError`; before it surfaced as a `requests.exceptions.ConnectionError`.
- `max_retries` may be `0`.
- A token response without `access_token` raises `AlfredAuthenticationError` instead of sending `Bearer None`.
- A response that cannot be parsed still raises `ValueError`, now an `AlfredResponseParseError`.

## Logging and redaction

The client logs to the standard logger named `alfred-python`. Nothing is logged unless you enable that logger, for example with `logging.getLogger("alfred-python").setLevel(logging.DEBUG)` and a handler.

- At `DEBUG`, every request is logged with its method, URL, headers and text body. Headers `Authorization`, `Proxy-Authorization`, `Cookie` and `X-TagshelfAPI-Key` are never logged. Binary bodies (JSON requests and file uploads are sent as bytes) are not logged. The body of the OAuth token request, which holds the username and password, is replaced with `[redacted]`.
- At `DEBUG`, a response with a status of 400 or above is logged with its status and full body text. Successful response bodies are not logged.
- At `WARNING`, the client reports that it is throttling.
- The logged URL includes the query string, unlike `error.url` and `str(error)`. Keep debug logs private if you pass secrets in query parameters.

The OAuth password and every credential header are also kept out of exception messages.

## Realtime connection errors

`alfred.exceptions.ConnectionError` is raised when the realtime (socket) client cannot connect. It derives from `AlfredError` but is not a `requests` error, and its `message` attribute holds the text. See [realtime.md](realtime.md) for how to handle it.

## See also

- [getting-started.md](getting-started.md)
- [authentication.md](authentication.md)
- [configuration.md](configuration.md)
- [jobs.md](jobs.md)
- [files.md](files.md)
- [classification.md](classification.md)
- [realtime.md](realtime.md)
- [compatibility.md](compatibility.md)
