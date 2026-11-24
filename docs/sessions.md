# Sessions

A deferred session is a container for files that reach Alfred at different times or from different places but belong to one job. You open a session, upload files into it one at a time, then submit the session as a job. It is the way to send files from your own machine or server.

The flow, and where each step is documented:

1. Open a session with [`sessions.create`](#create).
2. Upload each file with [`files.upload_file`](files.md#upload_file), passing the `session_id`.
3. Submit the session with [`jobs.create`](jobs.md), passing the same `session_id`. This closes the session and starts processing.

Files at public URLs or in connected cloud storage do not need a session: [`files.upload`](files.md#upload) creates the job directly.

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

## Methods

### `create`

`client.sessions.create()` opens a new session in your company. It takes no parameters.

Returns a dictionary:

| Field | Type | Meaning |
| --- | --- | --- |
| `session_id` | string | The new session's ID (a UUID). You need it for every upload and for creating the job. |

```python
session = client.sessions.create()
session_id = session["session_id"]
print(session_id)
```

```json
{
  "session_id": "0f767925-b464-4ffa-b621-1a0aeacac256"
}
```

Notes:

- When a session opens, Alfred reserves the job that its files will belong to. [`get`](#get) shows that job's ID as `job_id` before you submit anything.
- `create` is a `POST` and is not retried automatically (see [Retries](configuration.md#retries)). A timed-out call may have created a session you never saw; an unused session is harmless and expires on its own.

Errors worth handling (see [errors.md](errors.md)): `401` for bad credentials; `403` when the account is not active; `500` when Alfred could not create the session.

### `get`

`client.sessions.get(session_id)` returns a session's status and the job its files belong to. Use it to check that a session is still open before you upload more files.

| Parameter | Type | Default | Meaning |
| --- | --- | --- | --- |
| `session_id` | `str` | required | The ID returned by `create`. |

Returns a dictionary:

| Field | Type | Meaning |
| --- | --- | --- |
| `id` | string | The session ID. |
| `status` | string | `open` while you can upload, `closed` after the job is submitted, `expired` if the session stayed open past its lifetime. |
| `job_id` | string | The job the session's files belong to. Alfred starts processing it when you submit the session. |
| `user_name` | string | The user or API-key application that opened the session. |
| `company_id` | string | The company the session belongs to. |
| `creation_date`, `update_date` | string | ISO 8601 timestamps in UTC. |

```python
session = client.sessions.get("0f767925-b464-4ffa-b621-1a0aeacac256")

if session["status"] != "open":
    raise RuntimeError("Open a new session: " + session["status"])
```

```json
{
  "id": "0f767925-b464-4ffa-b621-1a0aeacac256",
  "creation_date": "2026-10-14T13:05:11.120Z",
  "update_date": "2026-10-14T13:05:11.120Z",
  "status": "open",
  "user_name": "my-integration-app",
  "company_id": "286e2ed0-3626-4faa-a745-8ebf3488fbd7",
  "job_id": "7a1d5c3e-9b2f-4e8a-8c61-3f2b9d0e4a17"
}
```

Errors worth handling (see [errors.md](errors.md)): `404` when no session with that ID exists in your company (the response has no body).

## Session lifetime

Sessions expire. Alfred closes a session automatically after its configured lifetime, and a closed or expired session rejects further uploads with a `400` whose message tells you to open a new session. The lifetime is not part of the API, so check `status` before a long upload run, and open a new session instead of reusing an old ID. An expired session that was never submitted keeps its reserved job as a draft; it is not processed.

## Connections to other domains

- Files uploaded with [`upload_file`](files.md#upload_file) carry the session's ID in their `deferred_session_id` field.
- [`jobs.create`](jobs.md) takes `session_id`. Submitting closes the session: you cannot add files afterwards.
- A session holds files for one job. To process another batch, open another session.

## See also

- [Files](files.md): `upload_file` adds files to a session
- [Jobs](jobs.md): `jobs.create` submits a session
- [Getting started](getting-started.md): the whole flow end to end
- [Error handling](errors.md)
