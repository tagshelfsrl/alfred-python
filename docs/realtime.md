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
- If `api_key` is missing, the SDK still tries to connect, sending the literal text `apiKey=None`, and the server refuses the connection (see [The server refuses the key](#the-server-refuses-the-key)).

Because the key is in a URL, it can appear in proxy and server logs. The SDK keeps it out of its own connection errors (see [Failure modes](#failure-modes)). Use a key meant for this purpose.

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

A function with one parameter, called with the error text when an attempt to connect fails: the initial attempt in the constructor, and every failed reconnection attempt afterwards. The argument is the error message, a string (or whatever the server sent with a refusal). The SDK removes the API key from that text before calling you.

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

`realtime_client.on(event, callback)` subscribes to a socket event by its name. The Alfred socket server sends exactly two event names, `job_event` and `file_event` (the values of `alfred.base.constants.EventType`), so `on("job_event", callback)` is the same subscription as `on_job_event(callback)`.

There is no per-event subscription on the server. Every job event arrives as `job_event` and every file event as `file_event`; what happened is in the `event_name` field of the data, for example `alfred_event_job_finished`. To react to one kind of event, subscribe to the stream and test `event_name`:

```python
def handle_job_event(data):
    name = data.get("event_name")
    if name == "alfred_event_job_finished":
        print("finished:", data["job_id"])
    elif name == "alfred_event_job_failed":
        print("failed:", data["job_id"], data.get("error_messages"))


realtime_client.on_job_event(handle_job_event)
```

The members of `JobEvent` and `FileEvent` in `alfred.base.constants` (`job_finished_event`, `file_done_event` and so on) are not names the server sends, neither as socket events nor in `event_name`. A callback registered with one of them, as earlier versions of the README showed, is never called. Use the two streams and the `event_name` values in the [event catalogue](#event-catalogue).

Alfred also defines a third stream, `bulk_task_event`, for bulk operations, but version 1.130.0 sends nothing on it. The SDK has no helper for it; `on("bulk_task_event", callback)` subscribes to it.

### Register callbacks early

The socket connects in the constructor, so there is a short window before your `on_*` calls in which an event could arrive and find no callback. For a job you create yourself, register the callbacks first and create the job afterwards (the worked example does this).

## Event catalogue

The socket server forwards the events Alfred publishes, to the account the API key belongs to and to no one else. Each one arrives as a `job_event` or a `file_event`, and your callback receives the event's fields as a dictionary. The SDK passes that dictionary on unchanged. The names and fields below are those of Alfred 1.130.0.

Fields every event has:

| Field | Meaning |
| --- | --- |
| `event_name` | What happened, for example `alfred_event_job_finished`. |
| `company_id`, `company_name` | The account the event belongs to. |
| `timestamp` | Present on every event. Use `update_date` when you need to order events. |

A job that has just finished arrives like this:

```json
{
  "event_name": "alfred_event_job_finished",
  "timestamp": "2026-11-24T10:01:00Z",
  "company_id": "286e2ed0-3626-4faa-a745-8ebf3488fbd7",
  "company_name": "Example Corp",
  "job_id": "7a1d5c3e-9b2f-4e8a-8c61-3f2b9d0e4a17",
  "correlation_id": "erp:invoice:INV-1042",
  "creation_date": "2026-11-24T10:00:00Z",
  "update_date": "2026-11-24T10:01:00Z"
}
```

Things to know about the data:

- Field names are snake_case. Unlike the REST API, a field without a value is sent as `null` rather than left out.
- The socket delivers the event's fields directly. The outer envelope that webhook deliveries carry (`event_id`, `event_type`, `event_time`, with the fields under `event`) is not included.
- Dates are ISO 8601. `creation_date` and `update_date` are those of the job or file the event is about.
- `stage` and `file_status` hold the same values as the REST API; the job stages are listed in [jobs.md](jobs.md).

### Job events

All of these arrive as `job_event`. Every one carries `job_id` and `correlation_id` (the job's correlation ID, `null` when it has none; see [jobs.md](jobs.md#correlation-ids)), plus `creation_date` and `update_date`.

| `event_name` | When Alfred sends it | Other fields |
| --- | --- | --- |
| `alfred_event_job_create` | A job is created. | `user_name`, `merge`, `metadata`, `file_count`, `file_urls` |
| `alfred_event_job_start` | The job begins processing. | |
| `alfred_event_job_stage_update` | The job moves to another stage. | `stage` |
| `alfred_event_job_retry` | The job has failed and used up its retries. It follows `alfred_event_job_failed`, with `exceeded_retries` set to `true`. Despite the name, Alfred 1.130.0 does not send it when a job is retried. | `user_name`, `merge`, `metadata`, `file_count`, `retries`, `exceeded_retries`, `error_messages`, `file_urls` |
| `alfred_event_job_invalid` | The job fails the validation of its input. | `retries`, `exceeded_retries`, `error_messages`, `has_broken_input_sources` |
| `alfred_event_job_failed` | The job stops on an error it cannot recover from. | `retries`, `exceeded_retries`, `error_messages` |
| `alfred_event_job_cancelled` | The job is cancelled. | `cancellation_reason`, `error_messages` |
| `alfred_event_job_expired` | The job expires before it finishes. | `previous_stage`, `attempt_started_at`, `expiration_days` |
| `alfred_event_job_finished` | The job completes all its stages. | |

A job is over after `alfred_event_job_finished`, `alfred_event_job_failed`, `alfred_event_job_invalid`, `alfred_event_job_cancelled` or `alfred_event_job_expired`.

### File events

All of these arrive as `file_event`. Unless noted, each carries `job_id`, `creation_date` and `update_date`.

| `event_name` | When Alfred sends it | Other fields |
| --- | --- | --- |
| `alfred_event_file_create` | A file is created in Alfred. Alfred 1.130.0 defines this event but does not send it. | `file_id`, `file_name`, `file_name_without_extension`, `blob_name`, `blob_url` |
| `alfred_event_file_added_to_job` | A file is linked to a job. | `file_id` (no dates) |
| `alfred_event_file_update` | The file's record is updated. Alfred 1.130.0 defines this event but does not send it. | `file_id`, `file_log_id`, `file_name`, `file_name_without_extension`, `blob_name`, `blob_url` |
| `alfred_event_file_status_update` | The file's status changes. | `file_id`, `blob_name`, `blob_url`, `tag_id`, `tag_name`, `manual_classification`, `classification_score`, `classification_status`, `file_status` |
| `alfred_event_file_change_tag` | The file's tag (document type) changes. | `file_id`, `previous_tag_id`, `previous_tag_name`, `proposed_tag_id`, `classification_score`, `new_tag_id`, `new_tag_name` (no dates) |
| `alfred_event_file_change_tag` | The file's tag is removed. It has the same name as a tag change and different fields. | `file_id`, `tag_being_removed_id`, `tag_being_removed_name`, `classification_score` (no dates) |
| `alfred_event_file_category_create` | A category is recorded for the file. | `file_log_id`, `description`, `confidence` |
| `alfred_event_file_category_delete` | A category of the file is deleted. | `file_log_id`, `description`, `confidence` |
| `alfred_event_file_extracted_data_create` | Content extracted from the file is stored. | `file_log_id`, `content`, `provider` |
| `alfred_event_file_extracted_data_delete` | Extracted content of the file is deleted. | `file_log_id`, `content`, `provider` |
| `alfred_event_file_property_create` | A property of the file is created. | `file_log_id`, `name`, `value` |
| `alfred_event_file_property_delete` | A property of the file is deleted. | `file_log_id`, `name`, `value` |
| `alfred_event_file_move` | The file moves to another location. | `file_id`, `file_name`, `file_name_without_extension`, `blob_name`, `blob_url`, `previous_file_directory`, `new_file_directory` |
| `alfred_event_file_move_to_pending` | The file is moved to pending. | `file_id`, `file_name`, `file_name_without_extension`, `blob_name`, `blob_url` |
| `alfred_event_file_move_to_recycle_bin` | The file is moved to the recycle bin. | `file_id`, `file_name`, `file_name_without_extension`, `blob_name`, `blob_url` |
| `alfred_event_file_move_to_decomposed` | A file that was split into documents is moved aside. | `file_id`, `file_name`, `file_name_without_extension`, `blob_name`, `blob_url` |
| `alfred_event_file_decomposed` | A file was split into its documents. | `file_id`, `file_name`, `file_name_without_extension`, `blob_name`, `blob_url` (no `job_id`) |
| `alfred_event_file_failed` | The file fails a stage of its pipeline. | `file_id`, `blob_name`, `blob_url`, `tag_id`, `tag_name`, `classification_score`, `classification_status`, `file_status`, `error_messages` |
| `alfred_event_file_done` | The file completes its pipeline. | `file_id`, `blob_name`, `blob_url`, `tag_id`, `tag_name`, `file_status` |

The events that identify the file by `file_log_id` do not carry `file_id`.

### Names in the public Event API pages

The public pages at <https://docs.tagshelf.dev/event-api> describe the same events as webhook deliveries, and their examples use other spellings: `job_finished_event` where the socket sends `alfred_event_job_finished`, and `job_event_type` where it sends `job_event`. The names in the tables above are the ones this client receives.

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

Verbose mode logs the full event data, which includes document content for some events (`content` in `alfred_event_file_extracted_data_create`). Do not enable it where logs are shared. Because the logger is shared with the REST client, `verbose=True` also turns on the REST client's DEBUG request logging when the real-time client was the one that configured the logger.

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
- Every incoming event is handled on its own new thread. Callbacks can run at the same time and in a different order from the order the events were sent.
- An exception in a callback is raised on that thread. It does not reach your main thread, and it does not close the connection.

So:

- Do not do slow or blocking work in a callback; hand it to a queue or a thread pool.
- Protect shared state with a lock, or pass work through `queue.Queue` or `threading.Event`.
- Do not assume `alfred_event_job_stage_update` events are handled in the order the stages happened. Use the `update_date` field if order matters.
- Catch exceptions inside callbacks if you want to log them.

## Worked example

Submit a job with the REST client, wait for the event that ends it, and fall back to polling if nothing arrives. The callback is registered before the job is created, and it ignores the events of other jobs.

```python
import os
import threading
import time

from alfred.base.config import Configuration
from alfred.http.typed import AuthConfiguration
from alfred.realtime import AlfredRealTimeClient
from alfred.rest import AlfredClient

api_key = os.environ["ALFRED_API_KEY"]
config = Configuration.v1()
auth_config = AuthConfiguration({"api_key": api_key})

client = AlfredClient(config=config, auth_config=auth_config)

# The events after which a job does no more work, and the stages that match them.
ENDED = {
    "alfred_event_job_finished": "finished",
    "alfred_event_job_failed": "failed",
    "alfred_event_job_invalid": "invalid",
    "alfred_event_job_cancelled": "cancelled",
    "alfred_event_job_expired": "expired",
}
STOPPED = {"completed", "failed", "invalid", "canceled", "expired"}  # see jobs.md

job_id = None
outcome = {}
done = threading.Event()
lock = threading.Lock()


def handle_job_event(data):
    if not isinstance(data, dict):
        return
    result = ENDED.get(data.get("event_name"))
    with lock:
        if result is None or job_id is None:
            return
        if str(data.get("job_id", "")).lower() != job_id.lower():
            return
        outcome["result"] = result
        outcome["errors"] = data.get("error_messages")
        done.set()


def connection_failed(error):
    print("connection attempt failed:", error)


realtime_client = AlfredRealTimeClient(config, auth_config, error_callback=connection_failed)
realtime_client.on_job_event(handle_job_event)

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

- `job_id` is set under the lock after `jobs.create` returns. An event for that job arriving between creation and assignment is ignored, which is why the loop also checks the job with `jobs.get` every 30 seconds. That check also covers events lost to a dropped connection: when it finds the job in a stopped stage, it ends the wait with the stage as the result. `STOPPED` is the set of stages after which a job does no more work; see [jobs.md](jobs.md).
- `handle_job_event` runs on a socket thread and only records the result; the work stays on the main thread.
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

The transport's own error quotes the connection URL, which includes `apiKey=<key>`. The SDK replaces the key with `[redacted]` in the exception message, in the text it passes to `error_callback` and in its own log lines, and it does not chain the original exception. Anything else that records the URL, such as a proxy or the socket library's own debug logging, can still show the key. There is more on the exception classes in [errors.md](errors.md).

`alfred.exceptions.ConnectionError` is not the built-in `ConnectionError`; import it under another name as above to avoid confusion.

### The connection drops later

Nothing is raised in your code. The SDK logs `Disconnected from the server.` (only with `verbose=True`) and the socket library reconnects by itself.

### Reconnection

The SDK uses the default `socketio.Client` settings, so reconnection is on, with unlimited attempts. The wait before each attempt starts at 1 second and doubles up to a cap of 5 seconds, with up to 0.5 seconds of random variation. Observed against a local test server: after the server was stopped, failed attempts came a few seconds apart, and when the server came back the client reconnected on its own and `on_connect` ran again. Your registered callbacks stay in place.

Details specific to this SDK:

- Every failed reconnection attempt runs the SDK's connection-error handler, which logs the error (with `verbose=True`), calls `disconnect()` (logging `Closing connection...`) and calls your `error_callback` with the error. This does not stop the reconnection: the socket library keeps retrying. So `error_callback` is a "this attempt failed" signal, not a "gave up" one. Count failures in it if you want to alert after a number of them.
- `disconnect()` called while an outage is being retried does not cancel the retry loop, and the client reconnects when the server returns. To stop for good during an outage, end the process: the socket threads do not keep it alive.
- There is no "reconnected" callback other than `on_connect`.
- Events sent while you were disconnected are not replayed, by the client or by the server. After a reconnection, read the current state with the REST client (`jobs.get`, `files.get`).

### The server refuses the key

The socket server checks the key when the client connects: it reads `apiKey` from the connection URL and asks Alfred which account the key belongs to. Without a key, or with one Alfred does not accept, it refuses the connection. For your code the result is the same as other connection failures: `error_callback`, then `alfred.exceptions.ConnectionError` from the constructor.

## Limitations

- Credentials: API key only, sent in the URL's query string.
- Two streams only, `job_event` and `file_event`: the server has no per-event subscription, so filter by `event_name`, `job_id` or `file_id` in your callback. The `JobEvent` and `FileEvent` enums do not hold names the server sends.
- One callback per stream (a new registration replaces the old one), and no way to remove one other than replacing it.
- No replay of missed events, and no reconnection hook beyond `on_connect`.
- Callbacks are concurrent and unordered (see [Threading](#threading)).
- `disconnect()` does not cancel a reconnection in progress.
- The client connects in its constructor and cannot be re-created cheaply; to reconnect after `disconnect()`, build a new `AlfredRealTimeClient`.
- Events reach only the account the API key belongs to.

## See also

- [Jobs](jobs.md): job stages, creating and reading jobs
- [Files](files.md) and [Data points](data-points.md): read results after `alfred_event_file_done`
- [Authentication](authentication.md)
- [Configuration](configuration.md): `realtime_url` and logging
- [Error handling](errors.md)
