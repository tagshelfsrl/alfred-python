# Authentication

Every request the SDK sends to Alfred must be authenticated. The SDK supports three methods: an API key, OAuth with a username and password, and HMAC request signing. You choose one when you build the client, by what you put in `AuthConfiguration`.

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

`AuthConfiguration` is a plain dictionary with three optional keys: `api_key`, `oauth` and `hmac`. The client picks the method when it is constructed.

## Choosing a method

| Method | Use it for | `AuthConfiguration` key | Sent as |
| --- | --- | --- | --- |
| API key | Servers and unattended jobs. Recommended by the Alfred documentation for automated processes. | `api_key` | Header `X-TagshelfAPI-Key` |
| OAuth (password grant) | Acting as a signed-in user. | `oauth` with `username` and `password` | Header `Authorization: Bearer <token>` |
| HMAC | Per-request signatures for a user account. | `hmac` with `api_key` and `secret_key` | Header `Authorization: amx <secret_key>:<signature>:<nonce>:<timestamp>` |

### Which method wins

If you supply more than one, the client uses the first of this list and silently ignores the rest:

1. an API key, from `auth_config["api_key"]` or, when that is empty, from the `ALFRED_API_KEY` environment variable;
2. OAuth;
3. HMAC.

This includes the environment variable: if `ALFRED_API_KEY` is set in your environment and you also pass `oauth` credentials, the API key is used and the OAuth credentials are never tried. If none of the three is available, constructing the client fails (see [errors.md](errors.md)).

## API key

Create an API key for an application in the Alfred console. The secret is shown only once, when the key is created or rotated. Alfred also shows a short key ID (it starts with `ak_live_` or `ak_test_`). The key ID names the key in the console and in usage reports, and it is not accepted as a credential: always use the secret.

```python
from alfred.http.typed import AuthConfiguration

auth_config = AuthConfiguration({"api_key": "YOUR_API_KEY"})
```

Or leave the key out of your code and set the environment variable:

```bash
export ALFRED_API_KEY="YOUR_API_KEY"
```

```python
from alfred.http.typed import AuthConfiguration

auth_config = AuthConfiguration({})  # the key is read from ALFRED_API_KEY
```

An explicit `api_key` takes precedence over the environment variable. The SDK reads `ALFRED_API_KEY` once, when it builds the HTTP client.

An API key calls the API with the full access of its workspace, so treat it like a password: keep it out of source control and client-side code, and rotate it on a schedule. A rotated key's previous secret keeps working for a limited grace period and is then refused.

## OAuth (username and password)

The SDK exchanges the credentials for a bearer token and sends the token on each request.

```python
from alfred.http.typed import AuthConfiguration

auth_config = AuthConfiguration(
    {"oauth": {"username": "user@example.com", "password": "YOUR_PASSWORD"}}
)
```

What the client does:

- It requests a token lazily, on the first request, with `POST /token` (form-encoded `grant_type=password`, `username`, `password`), and keeps the token in memory.
- When a request is answered with `401 Unauthorized`, it discards the token, fetches a new one and resends that request once. What you get when that fails too is described in [errors.md](errors.md).
- Alfred's public documentation says tokens typically expire after one month, so most scripts fetch a single token. The SDK does not read the expiry: it fetches a new token only after a `401`.

## HMAC

Each request is signed with a per-request signature.

```python
from alfred.http.typed import AuthConfiguration

auth_config = AuthConfiguration(
    {"hmac": {"api_key": "BASE64_API_KEY", "secret_key": "YOUR_SECRET_KEY"}}
)
```

`api_key` must be the base64 text of the user's API key: the SDK base64-decodes it and uses the bytes as the signing key. `secret_key` is sent as the identifier at the start of the `amx` header value and is part of the signed data.

The signature covers the request's method, URL, a timestamp, a one-time value and, when the request has a body, a hash of that body.

## What each part of the SDK supports

| Part of the SDK | API key | OAuth | HMAC |
| --- | --- | --- | --- |
| REST client (`AlfredClient`) | Yes | Yes | Yes |
| Real-time client (`AlfredRealTimeClient`) | Yes | No | No |

The real-time client reads only `auth_config["api_key"]`. It does not read `ALFRED_API_KEY`, and it ignores `oauth` and `hmac`. If you rely on the environment variable for the REST client, pass the key explicitly to the real-time client as well. See [realtime.md](realtime.md#credentials).

```python
import os

from alfred.base.config import Configuration
from alfred.http.typed import AuthConfiguration
from alfred.realtime import AlfredRealTimeClient

auth_config = AuthConfiguration({"api_key": os.environ["ALFRED_API_KEY"]})
realtime_client = AlfredRealTimeClient(Configuration.v1(), auth_config)
```

## Credentials in logs

With debug logging on, the SDK logs each request with its headers and leaves out the `Authorization`, `Proxy-Authorization`, `Cookie` and `X-TagshelfAPI-Key` headers. The body of the OAuth token request, which holds the username and password, is logged as `[redacted]`. Other request bodies that are text are logged, and so are full URLs with their query strings, so treat `DEBUG` logs as sensitive. [configuration.md](configuration.md#logging) describes what is logged, and [errors.md](errors.md#logging-and-redaction) what is redacted.

The real-time client passes the API key in the query string of its connection URL. The SDK keeps the key out of its own error messages and log lines, but anything else that records that URL, such as a proxy, can show it. See [realtime.md](realtime.md#failure-modes).

## Errors worth handling

- Building the client without any credentials fails immediately. See [errors.md](errors.md).
- A key that is wrong, revoked or past its grace period is answered with `401 Unauthorized` on every request. With OAuth, one automatic token refresh is attempted first. See [errors.md](errors.md).
- Alfred also rejects requests with no `User-Agent` header (`403 Forbidden`). The SDK always sends one, so you only meet this if you supply your own HTTP client.

## See also

- [Getting started](getting-started.md)
- [Configuration](configuration.md): base URL, timeouts, retries, logging
- [Real-time events](realtime.md)
- [Error handling](errors.md)
