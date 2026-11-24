# Real-time events

Alfred processes documents asynchronously. The real-time client keeps a socket open to Alfred and calls your function when something happens to a job or a file: a job starts, moves to another stage, finishes or fails; a file is classified, moved or done. It is built on `python-socketio` and is the `AlfredRealTimeClient` class in `alfred.realtime`.

## When to use it instead of polling

| | Polling (`jobs.get` in a loop) | Real-time events |
| --- | --- | --- |
| Latency | Up to your polling interval | As soon as Alfred emits the event |
| Cost | A request per check, counted against your rate limit | One long-lived connection |
| Code | A loop and a deadline | Callbacks, plus keeping the process alive |
| Missed events | Never: you ask for the current state | Possible: events sent while you are disconnected are not replayed by the SDK (see [Limitations](#limitations)) |
| Credentials | API key, OAuth or HMAC | API key only |

Use real-time events when many jobs are in flight, when latency matters, or when you want to react to intermediate steps. Use polling for a short script with one job, and as a safety net next to events: the worked example below does both.

## Setup

```python
from alfred.base.config import Configuration
from alfred.http.typed import AuthConfiguration
from alfred.realtime import AlfredRealTimeClient

realtime_client = AlfredRealTimeClient(
    Configuration.v1(),
    AuthConfiguration({"api_key": "YOUR_API_KEY"}),
)
```

Unlike the REST client, the real-time client connects inside its constructor and the constructor blocks until the connection is established or has failed. When it returns, you are connected.

## Constructing the client

`AlfredRealTimeClient(config, auth_config, verbose=False, error_callback=None, on_connect=None)`

| Parameter | Type | Default | Meaning |
| --- | --- | --- | --- |
| `config` | `ConfigurationDict` | required | Build with `Configuration.v1()`. Its `realtime_url` is the server to connect to. |
| `auth_config` | `AuthConfiguration` | required | Credentials. Only `api_key` is used. |
| `verbose` | `bool` | `False` | Log connection details and every event received. See [Verbose mode and logging](#verbose-mode-and-logging). |
| `error_callback` | callable taking one argument | `None` | Called with the error when a connection attempt fails. See [Connection lifecycle](#connection-lifecycle-and-callbacks). |
| `on_connect` | callable taking no arguments | `None` | Called every time the client connects, including after a reconnection. |

The constructed object has these public members: `on_job_event`, `on_file_event`, `on`, `disconnect`, and the attribute `socket`, the underlying `socketio.Client`.

### The `realtime_url` setting

The server address comes from `config["realtime_url"]`. The default is `https://sockets.tagshelf.io`. Override it to point at another environment:

```python
from alfred.base.config import Configuration

config = Configuration.v1({"realtime_url": "https://sockets.staging.example.com"})
```

`base_url` (the REST address) and `realtime_url` are independent: changing one does not change the other. See [configuration.md](configuration.md#configuration).

### Credentials

The real-time client supports API keys only.

- It reads `auth_config["api_key"]`. It does not fall back to the `ALFRED_API_KEY` environment variable the way the REST client does, so pass the key explicitly.
- `oauth` and `hmac` settings are ignored.
- The key is sent in the query string of the connection URL: `<realtime_url>?apiKey=<key>`. The socket library adds its own parameters after it (`transport`, `EIO`, `t`), so the key is visible in the request URL.
- If `api_key` is missing, the SDK still connects, sending the literal text `apiKey=None`. The server is expected to refuse it; how it refuses (and so what error you see) could not be verified, because the socket server is not part of the REST API source.

Because the key is in a URL, it can appear in proxy and server logs, and in the SDK's own connection error messages (see [Failure modes](#failure-modes)). Use a key meant for this purpose and keep error messages out of shared logs.

```python
import os

from alfred.base.config import Configuration
from alfred.http.typed import AuthConfiguration
from alfred.realtime import AlfredRealTimeClient

realtime_client = AlfredRealTimeClient(
    Configuration.v1(),
    AuthConfiguration({"api_key": os.environ["ALFRED_API_KEY"]}),
)
```

## Connection lifecycle and callbacks

1. The constructor creates a `socketio.Client` with its default settings and connects. The socket library connects over HTTP long-polling first and then tries to upgrade to a WebSocket.
2. When Alfred accepts the connection, the SDK logs `Successfully connected to: <realtime_url>` at INFO level and calls `on_connect()`.
3. Events arrive and are handed to the callbacks you registered.
4. If the connection drops, the socket library reconnects by itself (see [Reconnection](#reconnection)). Each successful reconnection calls `on_connect()` again.
5. `disconnect()` closes the connection.

### `on_connect`

A function without parameters, called each time a connection is established, on a background thread. Use it to learn that you are live, and to re-check state after a reconnection (events sent while you were away are not replayed).

### `error_callback`

A function with one parameter, called with the error text when an attempt to connect fails: the initial attempt in the constructor, and every failed reconnection attempt afterwards. The argument is the error message, a string (or whatever the server sent with a refusal). The message can contain the connection URL, and so the API key.

```python
import os

from alfred.base.config import Configuration
from alfred.http.typed import AuthConfiguration
from alfred.realtime import AlfredRealTimeClient


def connected():
    print("connected")


def connection_failed(error):
    print("connection attempt failed:", str(error)[:80])


realtime_client = AlfredRealTimeClient(
    Configuration.v1(),
    AuthConfiguration({"api_key": os.environ["ALFRED_API_KEY"]}),
    error_callback=connection_failed,
    on_connect=connected,
)
```

If the initial connection fails, `error_callback` is called first and then the constructor raises `alfred.exceptions.ConnectionError`. See [Failure modes](#failure-modes).

## Subscribing to events

Subscribe after the client is constructed. Each method takes one callback, which receives the event data as its only argument: the decoded JSON (normally a dictionary).

A subscription is a name. Registering a second callback for a name you already used replaces the first one; there is one callback per name.

### `on_job_event`

`realtime_client.on_job_event(callback)` subscribes to `job_event`, the stream of all job events.

```python
def handle_job_event(data):
    print("job event:", data)


realtime_client.on_job_event(handle_job_event)
```

### `on_file_event`

`realtime_client.on_file_event(callback)` subscribes to `file_event`, the stream of all file events.

```python
def handle_file_event(data):
    print("file event:", data)


realtime_client.on_file_event(handle_file_event)
```

### `on`

`realtime_client.on(event, callback)` subscribes to one specific event, to receive only that event. `event` is the event's name, a string. The members of `alfred.base.constants.JobEvent` and `FileEvent` hold these names in their `.value`, so use `.value`:

```python
from alfred.base.constants import FileEvent, JobEvent

realtime_client.on(JobEvent.JOB_FINISHED_EVENT.value, lambda data: print("finished", data))
realtime_client.on(FileEvent.FILE_DONE_EVENT.value, lambda data: print("file done", data))
realtime_client.on("job_failed_event", lambda data: print("failed", data))  # the same name as a plain string
```

Whether the server sends each event under its own name, under `job_event` / `file_event`, or both could not be verified from the code available: the SDK only registers handlers for those names. The previous README stated that both kinds work. If a specific event never arrives, try `on_job_event` or `on_file_event` and look at the `event_name` field in the data.

### Register callbacks early

The socket connects in the constructor, so there is a short window before your `on_*` calls in which an event could arrive and find no callback. For a job you create yourself, register the callbacks first and create the job afterwards (the worked example does this).

## Event catalogue

The SDK defines two enums in `alfred.base.constants`, `JobEvent` (8 members) and `FileEvent` (16 members), and a third, `EventType`, for the two catch-all streams:

| `EventType` member | Value | Subscribed with | Receives |
| --- | --- | --- | --- |
| `JOB_EVENT` | `job_event` | `on_job_event` | all job events |
| `FILE_EVENT` | `file_event` | `on_file_event` | all file events |

The "wire value" below is the string you pass to `on(...)`, `Enum.value`.

### Job events

A job is one unit of work with one or more files.

| `JobEvent` member | Wire value | When it fires |
| --- | --- | --- |
| `JOB_CREATE_EVENT` | `job_create_event` | A new job is created for a file or set of files. |
| `JOB_START_EVENT` | `job_start_event` | The job begins its workflow. |
| `JOB_STAGE_UPDATE_EVENT` | `job_stage_update_event` | The job moves from one stage to the next. |
| `JOB_RETRY_EVENT` | `job_retry_event` | The job retries its current stage after a recoverable failure. |
| `JOB_EXCEEDED_RETRIES_EVENT` | `job_exceeded_retries_event` | The job has used up its retries for a stage. |
| `JOB_FAILED_EVENT` | `job_failed_event` | The job stops because of an error it cannot recover from. |
| `JOB_INVALID_EVENT` | `job_invalid_event` | The job fails its first validation, for example an unsupported file type or missing input. |
| `JOB_FINISHED_EVENT` | `job_finished_event` | The job completed all its stages successfully. |

### File events

| `FileEvent` member | Wire value | When it fires |
| --- | --- | --- |
| `FILE_ADD_TO_JOB_EVENT` | `file_add_to_job_event` | A file is uploaded and linked to a job. |
| `FILE_STATUS_UPDATE_EVENT` | `file_status_update_event` | The file's status changes. |
| `FILE_UPDATE_EVENT` | `file_update_event` | The file's classification status changes, automatically or by a person. |
| `FILE_DONE_EVENT` | `file_done_event` | The file completed every stage of its pipeline. |
| `FILE_FAILED_EVENT` | `file_failed_event` | The file failed a stage of its pipeline. The payload names the reason. |
| `FILE_CATEGORY_CREATE_EVENT` | `file_category_create_event` | A tag (document type) was assigned to the file. |
| `FILE_CATEGORY_DELETE_EVENT` | `file_category_delete_event` | The file was not given a tag. It is not classified or indexed, and no data points are extracted. |
| `FILE_CHANGE_TAG_EVENT` | `file_change_tag_event` | The file's tag changed, by the pipeline or by a human validator. |
| `FILE_REMOVE_TAG_EVENT` | `file_remove_tag_event` | The file's tag was removed. |
| `FILE_EXTRACTED_DATA_CREATE_EVENT` | `file_extracted_data_create_event` | Content was extracted from the file. |
| `FILE_EXTRACTED_DATA_DELETE_EVENT` | `file_extracted_data_delete_event` | The extracted content of the file was deleted. |
| `FILE_PROPERTY_CREATE_EVENT` | `file_property_create_event` | A property was created for the file (its binary information was updated). |
| `FILE_PROPERTY_DELETE_EVENT` | `file_property_delete_event` | A property of the file was deleted. |
| `FILE_MOVE_EVENT` | `file_move_event` | The file's location changed, for example when it is classified, fails classification or its pipeline fails. |
| `FILE_MOVE_TO_PENDING_EVENT` | `file_move_to_pending_event` | The file's status became Pending: it has not completed its pipeline. |
| `FILE_MOVE_TO_RECYCLE_BIN_EVENT` | `file_move_to_recycle_bin_event` | The file was moved to the recycle bin. |

### Payload fields

The payload fields below come from the public Event API pages (<https://docs.tagshelf.dev/event-api>). Those pages describe the events as webhook deliveries, wrapped in an envelope:

```json
{
  "event_id": "UUID of the event",
  "event_type": "job_event_type or file_event_type",
  "event_time": "Unix timestamp",
  "event": { "event_name": "job_finished_event", "event_type": "job_event_type", "job_id": "..." }
}
```

Whether the socket delivers the same envelope, or only the inner `event` object, could not be verified: the socket server is not in the sources available. The SDK does not change the data; it passes your callback whatever the server sent. Write callbacks that accept both, as the worked example does: `fields = data.get("event", data)`.

Every event in the public documentation carries `event_name`, `event_type`, `company_id` and `company_name`. Most also carry `creation_date` and `update_date` (ISO 8601). The fields specific to each event:

| Wire value | Specific fields |
| --- | --- |
| `job_create_event` | `job_id`, `user_name`, `merge`, `metadata`, `file_count`, `file_urls` |
| `job_start_event` | `job_id` |
| `job_stage_update_event` | `job_id`, `stage` |
| `job_retry_event` | `job_id`, `user_name`, `merge`, `metadata`, `file_count`, `retries`, `exceeded_retries`, `error_messages`, `file_urls` |
| `job_exceeded_retries_event` | `job_id`, `user_name`, `merge`, `metadata`, `file_count`, `retries`, `exceeded_retries`, `error_messages`, `file_urls` |
| `job_failed_event` | `job_id`, `retries`, `exceeded_retries`, `error_messages` |
| `job_invalid_event` | `job_id`, `retries`, `exceeded_retries`, `error_messages` |
| `job_finished_event` | `job_id` |
| `file_add_to_job_event` | `file_id`, `job_id` (no dates) |
| `file_status_update_event` | `file_id`, `blob_name`, `blob_url`, `tag_id`, `tag_name`, `manual_classification`, `classification_score`, `classification_status`, `file_status` |
| `file_update_event` | `file_id`, `file_log_id`, `file_name`, `file_name_without_extension`, `blob_name`, `blob_url` |
| `file_done_event` | `file_id`, `blob_name`, `blob_url`, `tag_id`, `tag_name`, `file_status` |
| `file_failed_event` | `file_id`, `blob_name`, `blob_url`, `tag_id`, `tag_name`, `classification_score`, `classification_status`, `file_status`, `error_messages` |
| `file_category_create_event` | `file_log_id`, `description` (the tag), `confidence` |
| `file_category_delete_event` | `file_log_id`, `description`, `confidence` |
| `file_change_tag_event` | `file_id`, `previous_tag_id`, `previous_tag_name`, `proposed_tag_id`, `classification_score`, `new_tag_id`, `new_tag_name` (no dates) |
| `file_remove_tag_event` | `file_id`, `tag_being_removed_id`, `tag_being_removed_name`, `classification_score` (no dates) |
| `file_extracted_data_create_event` | `file_log_id`, `content`, `provider` |
| `file_extracted_data_delete_event` | `file_log_id`, `content`, `provider` |
| `file_property_create_event` | `file_log_id`, `name`, `value` |
| `file_property_delete_event` | `file_log_id`, `name`, `value` |
| `file_move_event` | `file_id`, `file_name`, `file_name_without_extension`, `blob_name`, `blob_url`, `previous_file_directory`, `new_file_directory` |
| `file_move_to_pending_event` | `file_id`, `file_name`, `file_name_without_extension`, `blob_name`, `blob_url` |
| `file_move_to_recycle_bin_event` | `file_id`, `file_name`, `file_name_without_extension`, `blob_name`, `blob_url` |

Notes on the public pages, which are documentation of webhook events and not of this client:

- Some examples on the public pages carry a different `event_name` than the page's event: the add-to-job example shows `file_added_to_job_event` (the SDK's value is `file_add_to_job_event`), the remove-tag example shows `file_change_tag_event`, and the exceeded-retries example shows `job_retry_event`. Treat the SDK's wire values in the tables above as the names to subscribe to.
- The public examples show `event_type` values `job_event_type` and `file_event_type`, which differ from the `job_event` and `file_event` names the SDK subscribes to. How they relate could not be verified.
- Field types in the public pages are written as descriptions, and some examples hold strings where the description says a number or boolean (`retries`, `exceeded_retries`, `confidence`). Convert defensively.
- The server's job-correlation documentation says job events (create, start, stage update, finish, failure, invalidation, retry and others) also expose the job's `correlation_id`, beside `job_id`. Whether it reaches socket payloads was not verified.
- The `stage` values of `job_stage_update_event` are the job stages listed in [jobs.md](jobs.md).

## Verbose mode and logging

The SDK logs through the `alfred-python` logger (see [configuration.md](configuration.md#logging)). When the real-time client is constructed and that logger has no level yet, it calls `setup_logger` itself: level `DEBUG` when `verbose=True`, otherwise `INFO`, writing to standard error. If you configured the logger before constructing the client, your configuration is kept and `verbose` only controls which messages are emitted.

| Message | Level | When |
| --- | --- | --- |
| `Attempting to establish a connection...` | DEBUG | Only with `verbose=True`, before connecting. |
| `Successfully connected to: <url>` | INFO | Each time a connection is established. The URL is the `realtime_url`, without the key. |
| `Event <name> received: <data>` | DEBUG | Only with `verbose=True`, for every event delivered to a callback. |
| `Disconnected from the server.` | INFO | Only with `verbose=True`, when the connection closes. |
| `Connection error:  <error>` | ERROR | Only with `verbose=True`, when a connection attempt fails. |
| `Closing connection...` | INFO | Every time `disconnect()` runs, which includes each failed connection attempt (see below). |

Verbose mode logs the full event data, which includes document content for some events (`content` in `file_extracted_data_create_event`). Do not enable it where logs are shared. Because the logger is shared with the REST client, `verbose=True` also turns on the REST client's DEBUG request logging when the real-time client was the one that configured the logger.

## Keeping the script alive

The socket works on background threads that do not keep Python alive. When your main thread reaches the end of the script, the process exits and the connection is dropped. A script that only listens must block.

The simplest way is to wait on the underlying socket:

```python
import os

from alfred.base.config import Configuration
from alfred.http.typed import AuthConfiguration
from alfred.realtime import AlfredRealTimeClient

realtime_client = AlfredRealTimeClient(
    Configuration.v1(),
    AuthConfiguration({"api_key": os.environ["ALFRED_API_KEY"]}),
)
realtime_client.on_job_event(lambda data: print(data))

try:
    realtime_client.socket.wait()  # blocks while connected or reconnecting
except KeyboardInterrupt:
    pass
finally:
    realtime_client.disconnect()
```

`socket.wait()` returns when the connection ends, and also waits through reconnection attempts. For a script that stops after something specific happens (a job finishing), use a `threading.Event` as in the worked example.

### Shutting down cleanly

Call `realtime_client.disconnect()`. It sends the disconnect message and closes the connection, and it is safe to call more than once. Do it in a `finally` block so it runs on errors and Ctrl+C.

Do not rely on `disconnect()` to stop an automatic reconnection that is already running (see [Reconnection](#reconnection)).

## Threading

`python-socketio` runs your callbacks on its own threads, never on your main thread:

- `on_connect` and `error_callback` run on the socket library's threads (and `error_callback` for the initial attempt runs on the thread that constructs the client).
- In the version this SDK pins (`python-socketio` 5.11.2 with `python-engineio` 4.9.0), every incoming event is handled on its own new thread. Callbacks can run at the same time and in a different order from the order the events were sent.
- An exception in a callback is raised on that thread. It does not reach your main thread, and it does not close the connection.

So:

- Do not do slow or blocking work in a callback; hand it to a queue or a thread pool.
- Protect shared state with a lock, or pass work through `queue.Queue` or `threading.Event`.
- Do not assume `job_stage_update_event` callbacks run in the order the stages happened. Use the `update_date` field if order matters.
- Catch exceptions inside callbacks if you want to log them.

## Worked example

Submit a job with the REST client, wait for its `job_finished_event` or `job_failed_event`, and fall back to polling if nothing arrives. The callbacks are registered before the job is created, and they ignore events of other jobs.

```python
import os
import threading
import time

from alfred.base.config import Configuration
from alfred.base.constants import JobEvent
from alfred.http.typed import AuthConfiguration
from alfred.realtime import AlfredRealTimeClient
from alfred.rest import AlfredClient

api_key = os.environ["ALFRED_API_KEY"]
config = Configuration.v1()
auth_config = AuthConfiguration({"api_key": api_key})

client = AlfredClient(config=config, auth_config=auth_config)

STOPPED = {"completed", "failed", "invalid", "canceled", "expired"}  # see jobs.md

job_id = None
outcome = {}
done = threading.Event()
lock = threading.Lock()


def fields_of(data):
    # The public Event API wraps the fields in {"event": {...}}; accept both shapes.
    if isinstance(data, dict):
        return data.get("event", data)
    return {}


def finished(data):
    event = fields_of(data)
    with lock:
        if event.get("job_id") == job_id:
            outcome["result"] = "finished"
            done.set()


def failed(data):
    event = fields_of(data)
    with lock:
        if event.get("job_id") == job_id:
            outcome["result"] = "failed"
            outcome["errors"] = event.get("error_messages")
            done.set()


def connection_failed(error):
    print("connection attempt failed")  # the message can contain the API key: do not log it


realtime_client = AlfredRealTimeClient(config, auth_config, error_callback=connection_failed)
realtime_client.on(JobEvent.JOB_FINISHED_EVENT.value, finished)
realtime_client.on(JobEvent.JOB_FAILED_EVENT.value, failed)

try:
    session_id = client.sessions.create()["session_id"]
    with open("invoice.pdf", "rb") as local_file:
        client.files.upload_file({"file": local_file, "session_id": session_id})

    with lock:
        job_id = client.jobs.create({"session_id": session_id})["job_id"]
    print("job created:", job_id)

    deadline = time.monotonic() + 15 * 60
    while not done.wait(timeout=30):  # wake up every 30 s to check the job directly
        stage = client.jobs.get(job_id)["stage"]
        print("still waiting, stage:", stage)
        if stage in STOPPED:  # the event was missed: the job has ended anyway
            outcome["result"] = stage
            break
        if time.monotonic() > deadline:
            raise TimeoutError(f"job {job_id} did not end in time")

    print("outcome:", outcome)
finally:
    realtime_client.disconnect()
```

Points to notice:

- `job_id` is set under the lock after `jobs.create` returns. A very fast event for that job arriving between creation and assignment would be ignored, which is why the loop also checks the job with `jobs.get` every 30 seconds. That check also covers events lost to a dropped connection: when it finds the job in a stopped stage, it ends the wait with the stage as the result. `STOPPED` is the set of stages after which a job does no more work; confirm it against [jobs.md](jobs.md).
- `finished` and `failed` run on socket threads, and only set a flag; the work stays on the main thread.
- `disconnect()` is in `finally`.

## Failure modes

### The initial connection fails

The constructor raises `alfred.exceptions.ConnectionError` with a message that starts `Could not establish connection with server:`. Before raising, it calls `error_callback` with the underlying error. Causes: no network, a wrong `realtime_url`, a server that is down, and a server that refuses the key.

The socket library also waits a short time after the transport connects for the server to confirm the connection (its default wait is 1 second). If the confirmation does not arrive in that time, or the server refuses it, the constructor raises the same exception class, and the end of the message is `One or more namespaces failed to connect`, taken from the library.

```python
from alfred.base.config import Configuration
from alfred.exceptions import ConnectionError as AlfredConnectionError
from alfred.http.typed import AuthConfiguration
from alfred.realtime import AlfredRealTimeClient

try:
    realtime_client = AlfredRealTimeClient(
        Configuration.v1({"realtime_url": "http://127.0.0.1:1"}),
        AuthConfiguration({"api_key": "YOUR_API_KEY"}),
    )
except AlfredConnectionError:
    print("could not connect; fall back to polling")
```

The exception message contains the request URL, which includes `apiKey=<key>`. Do not log it as is. There is more on the exception classes in [errors.md](errors.md).

`alfred.exceptions.ConnectionError` is not the built-in `ConnectionError`; import it under another name as above to avoid confusion.

### The connection drops later

Nothing is raised in your code. The SDK logs `Disconnected from the server.` (only with `verbose=True`) and the socket library reconnects by itself.

### Reconnection

The SDK uses the default `socketio.Client` settings, so reconnection is on, with unlimited attempts. The wait before each attempt starts at 1 second and doubles up to a cap of 5 seconds, with up to 0.5 seconds of random variation. Observed against a local test server: after the server was stopped, failed attempts came a few seconds apart, and when the server came back the client reconnected on its own and `on_connect` ran again. Your registered callbacks stay in place.

Details specific to this SDK:

- Every failed reconnection attempt runs the SDK's connection-error handler, which logs the error (with `verbose=True`), calls `disconnect()` (logging `Closing connection...`) and calls your `error_callback` with the error. This does not stop the reconnection: the socket library keeps retrying. So `error_callback` is a "this attempt failed" signal, not a "gave up" one. Count failures in it if you want to alert after a number of them.
- `disconnect()` called while an outage is being retried does not cancel the retry loop, and the client reconnects when the server returns. To stop for good during an outage, end the process: the socket threads do not keep it alive.
- There is no "reconnected" callback other than `on_connect`.
- Events emitted while you were disconnected are not replayed by the client. Whether the server buffers them could not be verified. After a reconnection, read the current state with the REST client (`jobs.get`, `files.get`).

### The server refuses the key

Behaviour of the real Alfred socket server when it refuses an API key could not be tested, because that needs a real key and the server is not part of the available sources. By the SDK's code, the result is the same as other connection failures: `error_callback`, then `alfred.exceptions.ConnectionError` from the constructor.

## Limitations

- Credentials: API key only, sent in the URL's query string.
- No event filtering on the client beyond the name; filter by `job_id` or `file_id` in your callback.
- One callback per event name (a new registration replaces the old one), and no way to remove one other than replacing it.
- No replay of missed events, and no reconnection hook beyond `on_connect`.
- Callbacks are concurrent and unordered (see [Threading](#threading)).
- `disconnect()` does not cancel a reconnection in progress.
- The client connects in its constructor and cannot be re-created cheaply; to reconnect after `disconnect()`, build a new `AlfredRealTimeClient`.
- Payload structure is documented from the public webhook pages and was not verified against the socket server.

## See also

- [Jobs](jobs.md): job stages, creating and reading jobs
- [Files](files.md) and [Data points](data-points.md): read results after `file_done_event`
- [Authentication](authentication.md)
- [Configuration](configuration.md): `realtime_url` and logging
- [Error handling](errors.md)
