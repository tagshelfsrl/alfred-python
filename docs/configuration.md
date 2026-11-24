# Configuration

Configuration has three layers: `Configuration`, which says where Alfred is (base URL, real-time URL, API version); `HttpConfiguration`, which tunes the HTTP client (timeout, retries, throttling, response type); and logging, which is off until you set it up. You can also replace the HTTP client entirely.

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

`AlfredClient` takes four arguments:

| Name | Type | Default | Meaning |
| --- | --- | --- | --- |
| `config` | `ConfigurationDict` | required | Where Alfred is and which API version to use. Build it with `Configuration.v1()`. |
| `auth_config` | `AuthConfiguration` | required | Credentials. See [authentication.md](authentication.md). |
| `http_config` | `HttpConfiguration` | `None` | HTTP client settings. `None` means the defaults listed below. |
| `http_client` | `HttpClient` or compatible object | `None` | Use this HTTP client instead of building one. See [Custom HTTP client](#custom-http-client). |

The domain objects (`client.files`, `client.sessions`, `client.jobs`, `client.data_points`) are created the first time you read the property, and then reused.

## `Configuration`

`Configuration.v1(overrides=None)` returns a dictionary with three keys. `Configuration.default()` is the same thing, and currently targets API version 1.

| Key | Default | Used by |
| --- | --- | --- |
| `version` | `1` | Selects the domain implementations. Version 1 is the only one that exists. |
| `base_url` | `https://app.tagshelf.com` | REST client. Endpoint paths such as `/api/file/detail/...` are appended to it, so give it without a trailing slash. |
| `realtime_url` | `https://sockets.tagshelf.io` | Real-time client. See [realtime.md](realtime.md). |

Override either URL by passing a dictionary:

```python
from alfred.base.config import Configuration

config = Configuration.v1(
    {
        "base_url": "https://staging.example.com",
        "realtime_url": "https://sockets.staging.example.com",
    }
)
print(config["base_url"], config["realtime_url"])
```

Both keys are optional; leave one out to keep its default.

If `config["version"]` is anything other than `1`, the error is raised when you first read a domain property (for example `client.files`), not when you build the client.

When you pass your own `http_client`, `base_url` is not used by the SDK: the HTTP client you supply decides where requests go. `realtime_url` is still used by the real-time client.

## `HttpConfiguration`

All keys are optional. Pass the ones you want to change as `http_config`:

```python
from alfred.base.config import Configuration
from alfred.http.typed import AuthConfiguration
from alfred.rest import AlfredClient

client = AlfredClient(
    config=Configuration.v1(),
    auth_config=AuthConfiguration({"api_key": "YOUR_API_KEY"}),
    http_config={"timeout": 30, "max_retries": 5},
)
print(client.http_client.timeout, client.http_client.max_retries)
```

| Key | Type | Default | Meaning |
| --- | --- | --- | --- |
| `timeout` | number (seconds) | `5` | Timeout for each HTTP request. Must be greater than zero. |
| `max_retries` | integer | `3` | Maximum retries per request. `0` turns retries off. |
| `retry_backoff_factor` | number (seconds) | `1` | Base of the wait between retries. `0` retries without waiting. |
| `pool_connections` | boolean | `True` | `True` uses a connection pool (10 pools of up to `min(32, cpu_count + 4)` connections each). `False` uses a single connection. |
| `response_type` | `ResponseType` | `ResponseType.JSON` | The format the client asks for. See [Response types](#response-types). |
| `throttle_delay` | number (seconds) | `1` | How long to sleep before a request when the client decides to throttle. |
| `throttle_threshold` | integer (percent) | `20` | Throttle when the remaining rate limit is at or below this percentage of the limit. `0` turns throttling off. |

Keys you leave out take these defaults. An invalid `timeout`, `max_retries`, `retry_backoff_factor` or `response_type` raises `ValueError` when the client is built.

### Timeout

The default timeout is 5 seconds. It is passed to `requests` as a single number, so it applies separately to connecting and to waiting for data from the server: it is not a deadline for the whole request. Uploading a large file with `files.upload_file` can need a higher value. The domain methods do not take a per-call timeout; to set one for a single call, use the lower-level `client.http_client.get(...)` or `.post(...)` with `timeout=`.

### Retries

Failed requests are retried when the server answers `429`, `500`, `502`, `503` or `504`. The first retry is sent at once and later ones wait longer each time (`retry_backoff_factor` sets the pace: 2 and then 4 seconds with the default). The retry rules come from `urllib3` and apply to its idempotent methods only: `GET`, `PUT`, `DELETE`, `HEAD`, `OPTIONS` and `TRACE`. `POST` requests (session creation, job creation, both upload methods) are not retried after the server has answered. That avoids duplicate sessions, files and jobs, but it means you must decide what to do when a `POST` fails. [errors.md](errors.md#automatic-retries-and-timeouts) has the complete retry rules and settings, and the error raised when retries run out.

### Throttling

Alfred allows each client 2,500 requests per minute per endpoint and reports the remaining allowance in `X-RateLimit-Limit` and `X-RateLimit-Remaining` headers. The SDK reads them after every response and keeps the latest values in `client.http_client.rate_limit`, a dictionary with `limit`, `remaining` and `reset_time` (a UTC `datetime`).

Before each request, if `remaining` is at or below `throttle_threshold` percent of `limit`, the client logs a warning and sleeps for `throttle_delay` seconds. When `remaining` reaches zero, the delay doubles on every request, up to 60 seconds, and returns to the configured value as soon as the allowance recovers.

[errors.md](errors.md#throttling) describes what the client does when a response carries no rate-limit headers.

```python
from alfred.base.config import Configuration
from alfred.http.typed import AuthConfiguration
from alfred.rest import AlfredClient

client = AlfredClient(
    config=Configuration.v1(),
    auth_config=AuthConfiguration({"api_key": "YOUR_API_KEY"}),
    http_config={"throttle_threshold": 0},  # never sleep because of rate limits
)
```

### Response types

`response_type` is one of the constants in `alfred.base.typed.ResponseType`, which are plain strings:

| Constant | Value | `Accept` header sent |
| --- | --- | --- |
| `ResponseType.JSON` | `"json"` | `application/json` |
| `ResponseType.TEXT` | `"text"` | `text/plain` |
| `ResponseType.XML` | `"xml"` | `application/xml` |

The setting only changes the `Accept` header. The SDK decides how to parse a response from the `Content-Type` header the server returns, not from this setting:

| Response `Content-Type` | What the SDK returns |
| --- | --- |
| `application/json` | The parsed JSON (a dictionary or list). |
| `application/xml` | An `xml.etree.ElementTree.Element`. |
| `text/plain`, or anything else | The response body as text. |

The Alfred API answers in JSON, and every domain page in this documentation shows JSON results. Keep the default unless you have a reason to change it; whether the server honours other `Accept` values could not be verified. A response with a body that cannot be parsed as its declared type raises `AlfredResponseParseError`, which is also a `ValueError`. A response with no body (for example `204 No Content`) returns `None`, and one with a body but no `Content-Type` header is returned as text; see [data-points.md](data-points.md) for where an empty answer can happen and [errors.md](errors.md#responses-that-cannot-be-parsed) for the details.

## Logging

The SDK logs through the standard `logging` logger named `alfred-python`. It has no handler and no level until you configure one, so by default nothing is printed.

`setup_logger` configures it:

```python
from alfred.utils import setup_logger

setup_logger({"level": "DEBUG", "name": "my-app"})
```

| Option | Type | Meaning |
| --- | --- | --- |
| `level` | string or int | Required. A `logging` level such as `"INFO"` or `"DEBUG"`. |
| `name` | string | Label printed on every line. It does not rename the logger (always `alfred-python`). |
| `papertrail_host`, `papertrail_port` | string, int | Also send log lines to this syslog (Papertrail) address over UDP. Both are needed. |
| `format` | string | Accepted, but it has no effect: the output layout is fixed. |

`setup_logger` replaces any handlers already on the `alfred-python` logger, and logs to standard error. Each line is the time, the `name` and a JSON object:

```text
Nov 24 05:57:25 my-app {"msg": {"message": "HTTP request details.", "method": "GET", "url": "https://app.tagshelf.com/api/deferred/detail/...", "headers": {"Accept": "application/json", ...}, "body": null}, "level": "DEBUG"}
```

What the SDK logs at `DEBUG`:

- every request: method, URL, headers and body. The `Authorization`, `Proxy-Authorization`, `Cookie` and `X-TagshelfAPI-Key` headers are left out. Bodies that `requests` holds as bytes (JSON bodies and file uploads) are logged as an empty string, and the body of the OAuth token request, which holds the username and password, is logged as `[redacted]`;
- for responses that are not successful (status 400 and above): status code, body, size and content type.

The URL, request and response bodies can contain your document data, so enable `DEBUG` with care.

The real-time client configures this logger itself if it has no level yet, so `setup_logger` is optional there. See [realtime.md](realtime.md#verbose-mode-and-logging). If you call `setup_logger` before creating the real-time client, your setup is kept.

## Custom HTTP client

Pass `http_client` to replace the built-in client, for example to add tracing, to route through a proxy library, or to test without a network. The SDK still requires `config` and `auth_config`, but with your own client `auth_config`, `http_config` and `base_url` are ignored.

The domain methods call these methods on the client and expect each to return a tuple `(parsed_body, response)`:

| Domain method | Call made |
| --- | --- |
| `sessions.create()` | `post("/api/deferred/create")` |
| `sessions.get(id)` | `get("/api/deferred/detail/<id>")` |
| `files.get(id)` | `get("/api/file/detail/<id>")` |
| `files.download(id)` | `get("/api/file/download/<id>")`; also reads `response.content` and the `Content-Type` and `Content-Disposition` response headers |
| `files.upload(payload)` | `post("/api/file/upload", data=payload)` |
| `files.upload_file(payload)` | `post("/api/file/uploadfile", data=form_fields, files=parts)` |
| `data_points.get_values(id)` | `get("/api/values/file/<id>")` |
| `jobs.*` | `get` and `post`; see [jobs.md](jobs.md) |

A minimal test double, which is also how the SDK's own tests work:

```python
from alfred.base.config import Configuration
from alfred.http.typed import AuthConfiguration
from alfred.rest import AlfredClient


class FakeHttpClient:
    def post(self, uri, **kwargs):
        return {"session_id": "00000000-0000-0000-0000-000000000001"}, None

    def get(self, uri, **kwargs):
        return {"id": "00000000-0000-0000-0000-000000000001", "status": "open"}, None


client = AlfredClient(
    config=Configuration.v1(),
    auth_config=AuthConfiguration({"api_key": "unused"}),
    http_client=FakeHttpClient(),
)

session_id = client.sessions.create()["session_id"]
print(client.sessions.get(session_id)["status"])
```

To extend rather than replace, subclass `alfred.http.HttpClient` and pass an instance as `http_client`. It takes `(base_url, auth_config, config)`.

## Errors worth handling

- `ValueError` for an invalid `timeout`, `max_retries`, `retry_backoff_factor` or `response_type` when the client is built.
- An unsupported `version` when a domain is first used.
- Everything that goes wrong during a request (timeouts, refused connections, HTTP error statuses) is covered in [errors.md](errors.md).

## See also

- [Authentication](authentication.md)
- [Real-time events](realtime.md): `realtime_url`, logging and verbose mode
- [Error handling](errors.md)
- [Compatibility](compatibility.md)
