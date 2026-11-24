# Data points

A data point is a piece of information Alfred extracts from a document, such as an invoice total or a customer name. Which data points a file gets depends on its tag (document type). Data points were previously called metadata; the API still uses `metadata` in some field names, such as `metadata_id`.

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

### `get_values`

`client.data_points.get_values(file_id)` returns the extracted values of one file.

| Parameter | Type | Default | Meaning |
| --- | --- | --- | --- |
| `file_id` | `str` | required | The file's ID: the `file_id` returned by [`files.upload_file`](files.md#upload_file), or the `id` of a file from a [job](jobs.md). |

Returns a list of dictionaries, one per data point of the file's tag. Each has:

| Field | Type | Meaning |
| --- | --- | --- |
| `id` | string | The ID of this value. |
| `file_log_id` | string | The file the value belongs to. |
| `metadata_id` | string | The data point definition (stable for the tag). |
| `metadata_name` | string | The data point's display name. It can be renamed in the console. |
| `field_key` | string | A stable machine key for the data point. Use it, not the name, to look values up in your code. |
| `value` | string | The value, after any formatting configured for the tag. |
| `classification_score` | number | Alfred's confidence in the value. |
| `extracted_value` | string | The extractor's original output. Present only when formatting changed it; when absent, `value` is the original. |
| `normalized_value` | string | The value after type normalisation, when one was computed. |
| `validation` | object | The recorded outcome of the tag's validators (overall status and one entry per validator). Present only when validation ran. |

Fields with no value are left out, so read optional ones with `.get()`.

```python
values = client.data_points.get_values("559167cb-4c76-4e28-bf15-34cbf614119c")

by_key = {item["field_key"]: item["value"] for item in values}
print(by_key.get("total"))
```

Example response:

```json
[
  {
    "id": "5b0d1c52-3a4e-4a61-9d0e-0c7e0a9d11aa",
    "file_log_id": "559167cb-4c76-4e28-bf15-34cbf614119c",
    "metadata_id": "8c1f6e0d-7a2b-4b8e-b0a4-2f6d3c9e5a10",
    "metadata_name": "Total",
    "field_key": "total",
    "value": "123.45",
    "classification_score": 0.93
  }
]
```

Values are strings, whatever the data point's type.

Call it after the file has finished processing. Values read earlier can be missing or incomplete. Check the file's `status` with [`files.get`](files.md#get), or wait for the job (see [jobs.md](jobs.md) or [real-time events](realtime.md)). A file that Alfred holds for human review (status `confirmation_required`) has values that a reviewer may still change.

Situations to handle (see [errors.md](errors.md)):

- `404`: the file does not exist, or its tag has no data points to extract (the body says so), or the lookup failed. Treat it as "no values for this file".
- `401`: your credentials are not allowed to read this file.
- No content (`204`): the server can answer with no body when it has nothing for the file. In this version of the SDK, a response without a `Content-Type` header makes `get_values` fail with `AttributeError` (`'NoneType' object has no attribute 'split'`) rather than returning an empty result. Wrap the call if you read files that may have no values.

## Connections to other domains

- The file ID comes from [`files.upload_file`](files.md#upload_file) (it returns `file_id`), or from the files of a job ([`jobs`](jobs.md)).
- The data points of a file depend on the tag shown in [`files.get`](files.md#get) (`tag_id`, `tag_name`). A file with no tag has no data points.
- If Alfred splits a document into several files, each page or part is a separate file with its own values. See `parent_id` in [`files.get`](files.md#get).

## See also

- [Files](files.md): file details, including the tag and status
- [Jobs](jobs.md): find a job's files
- [Real-time events](realtime.md): the `file_done_event` event
- [Error handling](errors.md)
