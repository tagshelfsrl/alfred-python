# alfred-python documentation

Each page is self-contained: you can land on any of them from a search and use it without reading another. This page lists what each one covers and a suggested reading order.

## Pages

| Page | What it covers |
| --- | --- |
| [getting-started.md](getting-started.md) | Install, create a client, and a complete walkthrough: open a session, upload files, create a job, wait for it, read file details and data points. |
| [authentication.md](authentication.md) | The three ways to authenticate (API key, OAuth with username and password, HMAC), the `ALFRED_API_KEY` environment variable, which method each part of the SDK supports. |
| [configuration.md](configuration.md) | `Configuration.v1` and its overrides, the HTTP settings and their defaults, response types, logging with `setup_logger`, and plugging in your own HTTP client. |
| [files.md](files.md) | `client.files`: get a file's details, download the original, upload remote files, upload a local file into a session. |
| [sessions.md](sessions.md) | `client.sessions`: open and inspect deferred sessions, which group several uploads into a single job. |
| [jobs.md](jobs.md) | `client.jobs`: create jobs, read a job, list jobs. |
| [data-points.md](data-points.md) | `client.data_points`: read the values Alfred extracted from a file. |
| [classification.md](classification.md) | Standalone classification: classify a text or a file against criteria you send with the request, without setting up document types first. A new `client.classifications` domain. |
| [realtime.md](realtime.md) | `AlfredRealTimeClient`: subscribe to job and file events instead of polling, the event catalogue, threading, reconnection and failure modes. |
| [errors.md](errors.md) | What the SDK raises and how to handle it. |
| [compatibility.md](compatibility.md) | Supported Python versions and the dependency policy. |

## Suggested reading order

1. [getting-started.md](getting-started.md) for the whole flow in one place.
2. [authentication.md](authentication.md), because every client needs credentials.
3. The domain pages you need: [files.md](files.md), [sessions.md](sessions.md), [jobs.md](jobs.md), [data-points.md](data-points.md).
4. [realtime.md](realtime.md) once you want events instead of polling.
5. [configuration.md](configuration.md) and [errors.md](errors.md) when you move to production: timeouts, retries, logging and failure handling.

## How the domains fit together

Alfred processes documents as jobs. A job groups one or more files, and every file that is classified gets a tag (a document type) whose data points Alfred extracts.

- A deferred session ([sessions.md](sessions.md)) lets you upload local files one at a time ([files.md](files.md)) and then submit them together as one job ([jobs.md](jobs.md)).
- Files at public URLs or in connected cloud storage skip the session: `client.files.upload` creates the job directly.
- Once a file is processed, read its details ([files.md](files.md)) and its extracted values ([data-points.md](data-points.md)).
- Processing is asynchronous. Poll the job, or listen for events ([realtime.md](realtime.md)).

## Conventions in these pages

- Every example builds the client the same way:

  ```python
  from alfred.base.config import Configuration
  from alfred.http.typed import AuthConfiguration
  from alfred.rest import AlfredClient

  client = AlfredClient(
      config=Configuration.v1(),
      auth_config=AuthConfiguration({"api_key": "YOUR_API_KEY"}),
  )
  ```

- Response bodies are returned as parsed JSON (dictionaries and lists). The Alfred API uses `snake_case` field names, and fields with no value are usually left out, so use `.get()` for optional fields.
- Identifiers (file, job and session IDs) are UUID strings.
- Where a page says a statement could not be verified, it was not confirmed against the SDK code, the Alfred server source or the public API documentation at <https://docs.tagshelf.dev>.
