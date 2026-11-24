# Jobs

A job is one submission to Alfred: one or more files (or remote file URLs) that Alfred processes together. The jobs domain of the SDK creates jobs, reads one job or a page of jobs, and cancels, restarts and checks the sources of a job. This page describes the SDK against Alfred 1.130.0 and later, and notes where older Alfred behaves differently.

## Setup

```python
from alfred.base.config import Configuration
from alfred.http.typed import AuthConfiguration
from alfred.rest import AlfredClient

client = AlfredClient(
    config=Configuration.v1(),
    auth_config=AuthConfiguration({"api_key": "YOUR_API_KEY"}),
)

jobs = client.jobs
```

The examples below use `client` and `jobs` from this snippet. See [authentication.md](authentication.md) and [configuration.md](configuration.md) for the other ways to build a client.

Types are importable from `alfred.rest.jobs`: `JobView` and the `TypedDict` classes `CreateJobDict`, `CreateJobResponseDict`, `JobSummaryDict`, `JobFullDict`, `JobFileDict`, `JobPageDict`, `CancelJobResponseDict`, `RestartJobResponseDict` and `CheckSourcesResponseDict`.

## Summary and full view

Since Alfred 1.130.0 a job comes in two sizes.

- The summary is the default. It holds the job's stage, its file counts and a few flags. It costs the same for a job of one file as for a job of ten thousand files.
- The full view is the complete record: files, metadata, file URLs and error messages. Ask for it with `view="full"`.

Who may ask for the full view: an API key, an Account Admin, or a platform Admin. Anyone else gets HTTP 403. Alfred never answers with a summary instead.

`Jobs.get()` and `Jobs.get_all()` send no `view` parameter unless you pass one, so the API default (summary) applies. Pass `view="full"` or `JobView.FULL` for the full view.

### Summary fields

| Field | Type | Meaning |
|---|---|---|
| `id` | string | Job ID. |
| `correlation_id` | string | Your correlation ID, if any (see [Correlation IDs](#correlation-ids)). |
| `stage` | string | `queued`, `started`, `downloading`, `downloaded`, `uploading`, `uploaded`, `in_progress`, `completed`, `failed`, `invalid`, `canceled`, `syncing`, `synced`, `in_revision`, `waiting_to_be_sent_to_third_party`, `sent_to_third_party`, `pre_completion`, `draft`, `expired`, `canceling`, `restarting`. |
| `channel` | string | Channel the job came through. |
| `priority` | string | snake_case, for example `high`. |
| `user_name` | string | Who submitted the job. |
| `file_sources_count` | int | Number of file sources. |
| `file_count` | int | Number of files. |
| `finished_files` | int | Files that finished. |
| `has_failed_files` | bool | At least one file failed. |
| `failed_files_count` | int | Number of failed files. |
| `has_confirmation_required_files` | bool | At least one file waits for confirmation. |
| `confirmation_required_files_count` | int | Number of such files. |
| `retries` | int | Retries so far. |
| `exceeded_retries` | bool | The retry limit was exceeded. |
| `merge`, `decompose`, `propagate_metadata` | bool | Options the job was created with. |
| `creation_date`, `update_date`, `start_date` | string | ISO 8601 UTC. |

Example:

```json
{
  "id": "6f1c2d3e-0000-4000-8000-000000000001",
  "correlation_id": "erp:invoice:INV-1042",
  "stage": "in_progress",
  "channel": "api",
  "priority": "high",
  "user_name": "integration@example.com",
  "file_sources_count": 2,
  "file_count": 2,
  "finished_files": 1,
  "has_failed_files": false,
  "failed_files_count": 0,
  "has_confirmation_required_files": false,
  "confirmation_required_files_count": 0,
  "retries": 0,
  "exceeded_retries": false,
  "merge": false,
  "decompose": false,
  "propagate_metadata": false,
  "creation_date": "2026-11-24T10:00:00Z",
  "update_date": "2026-11-24T10:01:00Z",
  "start_date": "2026-11-24T10:00:05Z"
}
```

### Full view fields

| Field | Type | Meaning |
|---|---|---|
| `id`, `correlation_id`, `stage`, `channel`, `user_name`, `priority` | | As in the summary, except `priority` (see below). |
| `file_sources_count`, `file_count`, `finished_files`, `retries`, `exceeded_retries` | | As in the summary. |
| `merge`, `decompose`, `propagate_metadata`, `has_failed_files` | | As in the summary. |
| `creation_date`, `update_date`, `start_date` | string | As in the summary. |
| `cancellation_reason` | string | Why the job was canceled. |
| `last_canceled_by` | string | Who canceled it last. |
| `last_cancellation_date` | string | When it was canceled last. |
| `company_id` | string | Your tenant's ID. |
| `bulk_id`, `deferred_session_id` | string | Bulk operation and deferred session the job belongs to. |
| `source`, `container`, `remote_file_name` | string | Where the job's input came from. |
| `parent_file_prefix` | string | Prefix applied to parent file names. |
| `metadata` | dict | Metadata sent at creation. The server sends it as JSON text; the SDK parses it (see below). |
| `total_file_count`, `metadata_objects_count` | int | Counts including children, and metadata objects. |
| `files` | list of file entries | See below. |
| `cancel_count`, `restart_count`, `cached_restart_count`, `redownload_restart_count` | int | How often the job was canceled or restarted. |
| `restarted_by`, `restarted_at` | string | Last restart. |
| `file_urls` | list of string | Source URLs. |
| `error_messages` | list of string | Errors recorded for the job. |
| `remote_sources_available` | bool | Whether remote sources were reachable when checked. |
| `unavailable_source_urls` | list of string | Sources that were not reachable. |
| `has_broken_input_sources` | bool | Some input source is broken. |

Each entry of `files` has: `id`, `creation_date`, `update_date`, `file_name`, `content_type`, `tag_name`, `is_parent`, `group_role`, `group_id`, `is_processing_unit`, `is_result_ready`, `parent_id`, `is_children`, `status`, `is_reextracting`.

### Differences between the two views

- `priority` is snake_case in the summary (`"high"`) and the .NET name in the full view (`"High"`). Compare case-insensitively if you read both.
- The full view does not carry `failed_files_count`, `has_confirmation_required_files` or `confirmation_required_files_count`. Use `has_failed_files` and the `status` of each entry in `files`.
- The server sends `metadata` in the full view as a JSON text string. The SDK parses it into a dict. A value that is empty, not valid JSON, or not a JSON object becomes `{}`. Since 1.130.0 a metadata value may be a string, a list, a list of records or an object; the SDK keeps those values as they are.
- The summary has no `metadata`. The SDK does not add one: a job without a `metadata` key stays without it. The one exception is the full view with metadata not excluded, where `metadata` is always a dict (`{}` when the server sent none).
- Alfred leaves out null values, with one exception: a null string field can arrive as an empty string. Test strings such as `correlation_id` and `last_canceled_by` for emptiness, not only for a missing key.
- In a page with `view="full"`, items are full views without `files`, `file_urls`, `error_messages`, `last_cancellation_date`, `remote_sources_available` and `unavailable_source_urls`. Metadata is included. Read a single job for those.

## Methods

### create

Submits a new job.

`jobs.create(job)`

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `job` | `CreateJobDict` (dict) | required | Job creation payload. All keys are optional in the type; the server decides which combinations are valid. |

Keys of `CreateJobDict`: `session_id`, `propagate_metadata`, `merge`, `decompose`, `metadata`, `channel`, `parent_file_prefix`, `page_rotation`, `container`, `file_name`, `file_names`, `correlation_id`, `password`.

`correlation_id` is a string of at most 512 characters after trimming. Alfred treats it as opaque and case-sensitive.

Returns the HTTP 202 body:

| Field | Type | Meaning |
|---|---|---|
| `job_id` | string | ID of the new job. |
| `correlation_id` | string | The correlation ID you sent, if any. Can be absent or empty when you sent none. |

```python
response = jobs.create(
    {
        "channel": "api",
        "container": "invoices",
        "file_name": "INV-1042.pdf",
        "correlation_id": "erp:invoice:INV-1042",
    }
)
job_id = response["job_id"]
```

Errors worth handling: 400 for a malformed body, for a `correlation_id` that is not a string or is longer than 512 characters, for a refused `password` (see below), and for other validation failures. See [errors.md](errors.md).

#### Password-protected files

Alfred can open password-protected PDFs, zip archives and Office files (docx, xlsx, pptx) when the job carries their password. Send it as `password` when the job is created:

```python
response = jobs.create(
    {
        "session_id": "0f767925-b464-4ffa-b621-1a0aeacac256",
        "channel": "api",
        "password": "the files' password",
    }
)
```

- One password per request. It applies to every file of the job and to anything inside them, such as the entries of a protected zip.
- At most 256 bytes in UTF-8. It is used exactly as sent: not trimmed, not normalized.
- For files uploaded into a deferred session, the password goes here, when the session becomes a job, not with each uploaded file. For remote files, send it with the upload instead (see [files.md](files.md)).
- A protected file whose job has no password, or the wrong one, ends with the status "Password required".
- Alfred answers 400 with a message that says why when it refuses a password: password-protected uploads are not enabled in that environment, the account's pipeline does not support them, or the value is not a string, is empty or is too long. It never accepts the request and ignores the password.
- A job that was given a password cannot be restarted onto a pipeline that cannot open protected files; that refusal is the `password-requires-ingestor` reason described under [restart](#restart).

### get

Reads one job.

`jobs.get(job_id, view=None, exclude=None)`

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `job_id` | `str` or `uuid.UUID` | required | The job. A missing or blank value raises `ValueError` before any request. Other types raise `TypeError`. |
| `view` | `JobView`, `str` or `None` | `None` | `"summary"` or `"full"`, any case. `None` sends nothing and the API default (summary) applies. The SDK does not validate the value; Alfred answers 400 for an unknown one. |
| `exclude` | `str`, iterable of `str`, or `None` | `None` | Parts to drop from the full view: `files`, `metadata`, `fileUrls`, `errorMessages`. A comma-separated string or any iterable of names. Empty means nothing is sent. It only has an effect with `view="full"`; Alfred ignores unknown names. Dropping `files` also saves the server from reading them. |

Returns a `JobSummaryDict` (default) or a `JobFullDict` (`view="full"`); the field tables are above. Existing code that calls `jobs.get(job_id)` positionally keeps working, but now receives a summary (see [Upgrading from 0.6.x](#upgrading-from-06x)).

```python
summary = jobs.get("6f1c2d3e-0000-4000-8000-000000000001")
print(summary["stage"], summary["finished_files"], "/", summary["file_count"])

job = jobs.get(
    "6f1c2d3e-0000-4000-8000-000000000001",
    view="full",
    exclude=["fileUrls", "errorMessages"],
)
for entry in job["files"]:
    print(entry["file_name"], entry["status"])
print(job["metadata"])  # a dict
```

Errors worth handling:

| Status | Server message | Cause |
|---|---|---|
| 400 | `view must be 'summary' or 'full'.` | Unknown `view`. |
| 403 | `The full view needs the Account Admin role; an API key has it. Leave view out, or ask for view=summary.` | `view="full"` without the role. |
| 404 | (empty body) | The job does not exist or belongs to another tenant. |

See [errors.md](errors.md) for how the SDK reports these.

### get_all

Reads one page of jobs.

`jobs.get_all(page_size=None, current_page=None, *, page=None, sort_direction=None, start_date=None, end_date=None, correlation_id=None, channel=None, view=None)`

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `page_size` | `int` | `None` | Items per page. Alfred accepts 10 to 100 and defaults to 10. |
| `current_page` | `int` | `None` | Page number, from 1. Kept so existing positional calls work. |
| `page` | `int` | `None` | The new name for `current_page`. Giving both with different values raises `ValueError`. |
| `sort_direction` | `str` | `None` | `"ASC"` or `"DESC"`. Alfred defaults to `DESC`, newest-updated first. |
| `start_date` | `date`, `datetime` or `str` | `None` | First day to include. |
| `end_date` | `date`, `datetime` or `str` | `None` | Last day to include. Needs `start_date`. |
| `correlation_id` | `str` | `None` | Exact, case-sensitive match. |
| `channel` | `str` | `None` | Only jobs of this channel. Combines with `correlation_id`. |
| `view` | `JobView`, `str` or `None` | `None` | As in `get`: `None` means summary items. |

A value that is `None` is not sent. A page or page size that is given is sent under both names (`page` and `currentPage`, `page_size` and `pageSize`) so the same call works on Alfred 1.130.0 and later and on older versions.

Dates are sent as `YYYY-MM-DD`. A `datetime` contributes its calendar date (its time and time zone are ignored, so convert to UTC first if that matters to you). A string is sent as given. Any other type raises `TypeError`.

Returns a `JobPageDict`, always in this shape:

| Field | Type | Meaning |
|---|---|---|
| `items` | list | Summaries, or full views without the collections listed above when `view="full"`. Never `None`. |
| `page` | int | The page returned. |
| `page_size` | int | Items per page. |
| `total` | int | Jobs matching the filters, across all pages. |
| `has_more` | bool | `page * page_size < total`. |

All five keys are always present. Any other key the server sends on the envelope is kept.

```python
page = jobs.get_all(page_size=25, page=1, sort_direction="DESC")
print(page["total"], "jobs;", len(page["items"]), "on this page")
```

Server-side filter rules (Alfred answers 400 with `{"error": "<message>", "statusCode": 400}`; note the key is `error`, not `message`):

| Rule | Server message |
|---|---|
| Page must be 1 or greater | `Invalid page number. Page must be 1 or greater.` |
| Page size from 10 to 100 | `Invalid page size. Must be between 10 and 100.` |
| Sort direction is `ASC` or `DESC` (any case) | `Invalid sort direction. Must be 'ASC' or 'DESC'.` |
| Dates carry no time component | `Time components are not supported. Please provide dates only (e.g., 2025-01-15).` |
| `end_date` needs `start_date` | `Start date is required when end date is provided.` |
| Dates are not in the future | `Start date cannot be in the future.` / `End date cannot be in the future.` |
| Start is not after end | `Start date cannot be after end date.` |

The date range covers whole UTC days. With only `start_date`, the range runs to the end of today. As for `get`, `view="full"` without the role returns 403 and an unknown `view` returns 400, both with a `message` key.

Walking every page:

```python
def all_jobs(**filters):
    page = 1
    while True:
        result = jobs.get_all(page_size=100, page=page, **filters)
        yield from result["items"]
        if not result["has_more"]:
            return
        page += 1


for job in all_jobs(channel="api", start_date="2026-11-01"):
    print(job["id"], job["stage"])
```

New jobs move the newest-updated-first order while you walk, so an item can appear on two pages or be missed. When that matters, filter with `start_date` and `end_date` on days that are over, so the set no longer changes while you walk it.

### cancel

Cancels a job.

`jobs.cancel(job_id)`

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `job_id` | `str` or `uuid.UUID` | required | The job. Validated as in `get`. |

Returns `{"canceled": bool}`. `False` means Alfred did not cancel the job, for example because it is already finished.

```python
result = jobs.cancel("6f1c2d3e-0000-4000-8000-000000000001")
if not result["canceled"]:
    print("The job was not canceled")
```

Errors worth handling: 404 when the job does not exist or is not yours, and 403 when the caller is not allowed to cancel it. See [errors.md](errors.md).

### restart

Restarts a job.

`jobs.restart(job_id, redownload_remote_files=False)`

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `job_id` | `str` or `uuid.UUID` | required | The job. |
| `redownload_remote_files` | `bool` | `False` | Download the job's remote sources again instead of using the copies Alfred already holds. |

Returns `{"restarted": bool}`.

```python
result = jobs.restart("6f1c2d3e-0000-4000-8000-000000000001", redownload_remote_files=True)
print(result["restarted"])
```

Alfred can refuse a restart. The refusal is an HTTP error, 409 or 400, with a body like:

```json
{
  "restarted": false,
  "refused": true,
  "reason": "sources-missing",
  "message": "Human-readable explanation."
}
```

`reason` identifies the rule. `sources-missing` (409, a redownload restart whose sources are gone) also carries `detail` and `missing_sources`. 400 refusals use reasons such as `csv-requires-ingestor` and `password-requires-ingestor`. A 409 can succeed later if the sources come back. See [errors.md](errors.md) for how to read the body.

As for `cancel`, Alfred answers 404 when the job does not exist or is not yours, and 403 when the caller is not allowed to restart it.

### check_sources

Checks whether the remote sources of a job can still be downloaded.

`jobs.check_sources(job_id)`

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `job_id` | `str` or `uuid.UUID` | required | The job. |

Returns:

| Field | Type | Meaning |
|---|---|---|
| `available` | bool | All sources are reachable. |
| `unavailable_urls` | list of string | The URLs that are not. Empty when every source is reachable. |

Alfred's response is built from a field named `unavailableUrls`; its JSON serializer converts every property name to snake_case, so it arrives as `unavailable_urls`.

```python
check = jobs.check_sources("6f1c2d3e-0000-4000-8000-000000000001")
if not check["available"]:
    print("Unreachable:", check.get("unavailable_urls", []))
```

Errors worth handling: 404 when the job does not exist or is not yours. See [errors.md](errors.md).

## Correlation IDs

A correlation ID ties a job to an operation in your own system, such as an invoice or an email. Send it as `correlation_id` in `create`, read it back from `get`, and search by it with `get_all(correlation_id=...)`.

- At most 512 characters after trimming; leading and trailing whitespace is removed. Blank counts as none.
- Opaque and case-sensitive. Alfred never changes or generates it, and the filter is an exact match, not a prefix search.
- Not unique. Several jobs can share one ID, and Alfred does not deduplicate on it.
- Not globally unique across producers. Prefix it with the source system, for example `erp:invoice:INV-1042`.
- Set at creation. Updates and retries keep the saved value; they cannot replace it.

```python
jobs.create({"channel": "api", "file_name": "INV-1042.pdf", "correlation_id": "erp:invoice:INV-1042"})

page = jobs.get_all(correlation_id="erp:invoice:INV-1042", channel="api")
for job in page["items"]:
    print(job["id"], job["stage"])
```

## Waiting for a job to finish

Poll with the summary: it is cheap and holds the stage. Stop on a terminal stage: `completed`, `failed`, `invalid`, `canceled` or `expired`. `canceling` and `restarting` are not terminal.

```python
import time

TERMINAL_STAGES = {"completed", "failed", "invalid", "canceled", "expired"}


def wait_for_job(job_id, interval=5.0, timeout=600.0):
    deadline = time.monotonic() + timeout
    while True:
        job = jobs.get(job_id)  # summary
        if job["stage"] in TERMINAL_STAGES:
            return job
        if time.monotonic() >= deadline:
            raise TimeoutError(f"Job {job_id} is still {job['stage']}")
        time.sleep(interval)


job = wait_for_job("6f1c2d3e-0000-4000-8000-000000000001")
if job["stage"] == "completed" and not job["has_failed_files"]:
    full = jobs.get(job["id"], view="full", exclude="metadata")
```

Keep the interval at a few seconds so you do not flood the API. To be told instead of asking, subscribe to events: see [realtime.md](realtime.md).

## Compatibility with Alfred older than 1.130.0

- Older Alfred ignores `view`. `get()` then returns the full shape whatever you ask. The SDK still parses `metadata` if it is present. Code that reads `files` after `get(job_id, view="full")` works on both.
- Older Alfred answers `get_all()` with `{"result": [...], "total": N, "is_empty": bool}`. The SDK converts it to the envelope above: `items` from `result`, `page` and `page_size` from what you asked for (1 and 10 when you did not), and `has_more` computed from `total`. Items are then the old full-shaped items, so a `metadata` key is parsed when present. `is_empty` is dropped; use `not page["items"]`.
- Older Alfred ignores `page` and `page_size`, which is why the SDK also sends `currentPage` and `pageSize`.
- The `correlation_id` filter and field need an Alfred version that supports correlation IDs (1.127.0 and later).

## Upgrading from 0.6.x

Two calls changed result shape because the API changed in Alfred 1.130.0.

`get()` returns the summary unless you pass `view="full"`:

```python
# Before (0.6.x): the full record
job = jobs.get(job_id)
files = job["files"]

# After: ask for the full record
job = jobs.get(job_id, view="full")
files = job["files"]
```

Callers that worked around this with `client.jobs.http_client.get("/api/job/detail/<id>", params={"view": "full"})` can switch to `jobs.get(job_id, view="full")`. The full view needs an API key, an Account Admin or a platform Admin.

`get_all()` returns `items`, not `result`, and a page envelope instead of `total` and `is_empty`:

```python
# Before (0.6.x)
response = jobs.get_all(page_size=50, current_page=1)
for job in response["result"]:
    ...
if response["is_empty"]:
    ...

# After
response = jobs.get_all(page_size=50, page=1)
for job in response["items"]:
    ...
if response["has_more"]:
    ...
```

Other changes:

- List items are summaries and have no `metadata`. Pass `view="full"` to `get_all` to get it.
- `get_all(page_size, current_page)` still works positionally. Use `page` in new code.
- `get_all` sends `page` and `currentPage` (and `page_size` and `pageSize`) together. An explicit `0` is now sent, and the server rejects it, instead of being silently dropped.
- Job IDs are URL-quoted, and a blank ID raises `ValueError` instead of calling `/api/job/detail/`.
- New: `JobView`, `exclude`, filters on `get_all`, `correlation_id` and `password` in `create`, and `cancel`, `restart` and `check_sources`.

## See also

- [errors.md](errors.md): how HTTP errors surface in the SDK.
- [files.md](files.md): reading the files of a job.
- [sessions.md](sessions.md): deferred upload sessions.
- [realtime.md](realtime.md): events instead of polling.
- [compatibility.md](compatibility.md): supported Python versions and dependencies.
- [authentication.md](authentication.md), [configuration.md](configuration.md): building the client.
