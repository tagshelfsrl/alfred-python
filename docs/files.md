# Files

A file is a document that Alfred processes: it is classified under a tag (a document type), its data points are extracted, and its status moves from `uploaded` to `finished` (or to a failure). `client.files` sends files to Alfred, reads their details and downloads the originals.

There are two ways to send files, and they behave differently:

| Your files are... | Method | What happens |
| --- | --- | --- |
| At public URLs, or in cloud storage you connected to Alfred | [`upload`](#upload) | Alfred fetches the files and creates a job straight away. |
| On your machine or server | [`upload_file`](#upload_file) with a [session](sessions.md) | You upload each file into the session, then submit the session as one job with [`jobs.create`](jobs.md). |

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

Importing `alfred.rest` loads the `libmagic` system library (through `python-magic`), which `upload_file` uses to detect file types. If the library is missing, the import fails. See the install notes in the [README](../README.md#install).

## Methods

### `get`

`client.files.get(file_id)` returns the details of one file: its status, the tag Alfred assigned and how confident it is, size, page count and the metadata you attached.

| Parameter | Type | Default | Meaning |
| --- | --- | --- | --- |
| `file_id` | `str` | required | The file's ID (a UUID), as returned by `upload_file` or found through its job. |

Returns the file as a dictionary. Fields with no value are left out, so use `.get()` for anything optional. The fields most integrations use:

| Field | Type | Meaning |
| --- | --- | --- |
| `id` | string | The file's ID. |
| `file_name`, `file_name_without_extension` | string | The name the file was stored under. |
| `content_type` | string | The file's MIME type, for example `application/pdf`. |
| `file_size` (also `size`) | integer | Size in bytes. |
| `status` | string | Where the file is in processing, for example `finished`. The values are listed in the public [File Status](https://docs.tagshelf.dev/endpoints/file/file-status) page. |
| `tag_id`, `tag_name` | string | The tag (document type) assigned to the file. `tag_id` is present only once the file has a tag. |
| `classification_score` | number | Confidence in the tag, from 0 to 1. |
| `channel` | string | How the file reached Alfred, for example `api`. |
| `metadata` | object | The metadata you attached when you uploaded the file. |
| `page_count`, `page_number` | integer | Number of pages; for a page split out of a larger document, its page number in the original. |
| `parent_id`, `is_parent` | string, boolean | Set when Alfred split a document into several files. `parent_id` points at the original. |
| `deferred_session_id` | string | The session the file was uploaded into, if any. |
| `is_duplicate`, `duplicate_origin_id` | boolean, string | Whether the file is an exact copy of one Alfred already processed, and which one. |
| `creation_date`, `update_date` | string | ISO 8601 timestamps in UTC. |

The response has more fields (review and assignment state, duplicate flags, the stored blob name and so on). The `FileDetailsResponse` type in `alfred.rest.files` lists a subset; the SDK returns whatever the server sent. The full list is in the public [Get a file](https://docs.tagshelf.dev/endpoints/file) reference.

```python
file = client.files.get("559167cb-4c76-4e28-bf15-34cbf614119c")

print(file["status"], file.get("tag_name"), file.get("classification_score"))
```

Example response (shortened):

```json
{
  "id": "559167cb-4c76-4e28-bf15-34cbf614119c",
  "creation_date": "2026-10-14T13:05:11.300Z",
  "update_date": "2026-10-14T13:07:40.910Z",
  "file_name": "invoice-1042.pdf",
  "content_type": "application/pdf",
  "file_size": 182344,
  "channel": "api",
  "status": "finished",
  "tag_id": "a3c7e2b1-58d4-4f0e-9c2a-6b1d7e8f9a03",
  "tag_name": "Invoice",
  "classification_score": 0.97,
  "deferred_session_id": "0f767925-b464-4ffa-b621-1a0aeacac256",
  "metadata": { "customer": "ACME" },
  "page_count": 1
}
```

Errors worth handling (see [errors.md](errors.md)): a `404` when the file does not exist or belongs to another account (the response has no body), and a `409` when the file exists but is not in a state that can be read yet. A `409` is worth retrying after a few seconds.

### `download`

`client.files.download(file_id)` downloads the original file, as uploaded.

| Parameter | Type | Default | Meaning |
| --- | --- | --- | --- |
| `file_id` | `str` | required | The file's ID. |

Returns a dictionary:

| Field | Type | Meaning |
| --- | --- | --- |
| `file` | `io.BytesIO` | The whole file, already in memory. Read it with `.getvalue()` or `.read()`. |
| `original_name` | string | The file name from the `Content-Disposition` response header. |
| `mime_type` | string | The `Content-Type` response header. |

```python
result = client.files.download("559167cb-4c76-4e28-bf15-34cbf614119c")

with open(result["original_name"], "wb") as target:
    target.write(result["file"].getvalue())
```

Notes:

- The file is read fully into memory; there is no streaming. Keep that in mind for large files.
- `original_name` comes from the server and is used as the name you would write to. If you save to disk, sanitise it (it could contain path separators) rather than trusting it blindly.
- If the response has no `Content-Disposition` header, the call fails with a `TypeError` (`argument of type 'NoneType' is not iterable`). Alfred sets the header for downloads, so this appears only behind a proxy that strips it.
- A downloaded file whose `Content-Type` is `application/json` or `application/xml` is also run through the SDK's response parser (see [Response types](configuration.md#response-types)), and a file that does not parse as its declared type raises `ValueError`.

Errors worth handling: `404` when the file does not exist (see [errors.md](errors.md)).

### `upload`

`client.files.upload(payload)` asks Alfred to fetch one or more files from public URLs or from connected cloud storage, and to process them as a new job. Nothing is sent from your machine; Alfred does the download.

`payload` is a dictionary (`UploadRemoteFilePayload`). A request must use exactly one kind of source: `url` or `urls`, or `source` with `container` and `file_name` or `file_names`.

| Field | Type | Default | Meaning |
| --- | --- | --- | --- |
| `url` | `str` | none | URL of a single file. |
| `urls` | `list[str]` | none | URLs of several files (up to 100). |
| `source` | `str` | none | Name of a connected remote source (cloud storage). Needs `container` and a file name. |
| `container` | `str` | none | Container (bucket) inside the remote source. |
| `file_name`, `file_names` | `str`, `list[str]` | none | With `source` and `container`: the name(s) of the file(s) in that container. Not in the SDK's type; see the note below. |
| `filename`, `filenames` | `str`, `list[str]` | none | Listed by the SDK's type, but the server does not read them (see the note below). |
| `merge` | `bool` | `false` | Merge all the files into one PDF. Only works when the files are images. |
| `metadata` | `dict` or `list[dict]` | none | Your own data. Send one object for a single file, or when `merge` or `propagate_metadata` is true. Otherwise send one object per file, in the same order as the URLs. |
| `propagate_metadata` | `bool` | `false` | Apply the single `metadata` object to every file. |
| `parent_file_prefix` | `str` | none | Virtual folder for the documents split out of each file (used when splitting). |

Returns a dictionary. The server answers `202 Accepted` with:

| Field | Type | Meaning |
| --- | --- | --- |
| `job_id` | string | The new job's ID. Follow it with [`jobs.get`](jobs.md). |
| `correlation_id` | string | The correlation ID you sent, or an empty string. |
| `warnings` | list of strings | Advice about the request. Present only when there is something to say. |

```python
result = client.files.upload(
    {
        "urls": [
            "https://files.example.com/invoices/invoice-1042.pdf",
            "https://files.example.com/invoices/invoice-1043.pdf",
        ],
        "metadata": [{"customer": "ACME"}, {"customer": "Globex"}],
    }
)

print(result["job_id"])
```

```json
{
  "job_id": "7a1d5c3e-9b2f-4e8a-8c61-3f2b9d0e4a17",
  "correlation_id": ""
}
```

Things to know:

- The result has a `job_id`, not a `file_id`. The `UploadResponse` type in the SDK says `file_id`; that is only right for `upload_file`. To find the files of the job, use [`jobs.get`](jobs.md).
- The SDK sends your dictionary to the server as is, without validating or filtering it. Fields that the public API accepts but the SDK's type does not list, such as `decompose`, `page_rotation`, `priority`, `channel` and `correlation_id`, are forwarded and work at runtime; a type checker will flag them. See the public [Upload files from URLs](https://docs.tagshelf.dev/endpoints/file) reference for what they do. The cloud-storage file names are sent as `file_name` or `file_names`, which the SDK's type does not list. The type lists `filename` and `filenames` instead; the server source (version 1.130.0) reads only `file_name` and `file_names` for `/api/file/upload`, so `filename` and `filenames` have no effect there. They were not found in the server code for URL uploads either, so do not expect them to rename URL-based files.
- Retries: `upload` is a `POST` and is not retried automatically (see [Retries](configuration.md#retries)). If it fails with a timeout, check the job list before sending again, or you may create the job twice.

Errors worth handling (see [errors.md](errors.md)): `400` when no source, more than one kind of source, an unsupported file type for your company, or a metadata count that does not match the file count; `401` for bad credentials.

### `upload_file`

`client.files.upload_file(payload)` uploads one local file into a [deferred session](sessions.md). The file is not processed until you submit the session with [`jobs.create`](jobs.md).

`payload` is a dictionary (`UploadLocalFilePayload`):

| Field | Type | Default | Meaning |
| --- | --- | --- | --- |
| `file` | binary file object | required | An open file in binary mode (`open(path, "rb")`) or an `io.BytesIO`. It must be seekable. |
| `session_id` | `str` | required | The session to add the file to. Create one with [`sessions.create`](sessions.md#create). It must be open. |
| `filename` | `str` | none | The name to store the file under. Required for `io.BytesIO`; ignored for a real file (see below). |
| `metadata` | `dict` | `{}` | Your own data for this file. Sent as a JSON string; returned later in the file's `metadata`. |

Returns:

| Field | Type | Meaning |
| --- | --- | --- |
| `file_id` | string | The uploaded file's ID. Keep it: it is the ID you pass to `get`, `download` and [`data_points.get_values`](data-points.md). |

```python
session_id = client.sessions.create()["session_id"]

with open("invoice-1042.pdf", "rb") as local_file:
    result = client.files.upload_file(
        {
            "file": local_file,
            "session_id": session_id,
            "metadata": {"customer": "ACME"},
        }
    )

print(result["file_id"])
```

```json
{
  "file_id": "559167cb-4c76-4e28-bf15-34cbf614119c"
}
```

Uploading from memory, where you must give the name:

```python
import io

session_id = client.sessions.create()["session_id"]

content = io.BytesIO(b"Total due: 123.45\n")
result = client.files.upload_file(
    {"file": content, "filename": "note.txt", "session_id": session_id}
)
print(result["file_id"])
```

#### File name rules

- If `file` is a real file opened with `open(path, "rb")` (a `BufferedReader`), the SDK takes the name from the file's path and ignores `filename`, even if you set one. To store it under a different name, read it into `io.BytesIO` and pass `filename`.
- If `file` is an `io.BytesIO` (or another object that is not a `BufferedReader`), `filename` is required. Without it the call fails before anything is sent, with a missing-argument error (see [errors.md](errors.md)).
- The server removes special characters from the name. If the name has no extension, the server adds one from the detected content type.

#### Content type detection

The SDK reads the first 1,024 bytes of the file, detects its MIME type from the content with `libmagic` (the extension and `filename` are not consulted), then rewinds the file to the start and sends the whole thing. The detected type is sent with the file part. Files that `libmagic` cannot identify are sent as `application/octet-stream`. Alfred needs a content type for each upload and decides whether it can process the file based on it and the name.

Because the file is rewound, a file you have partly read is still sent in full.

#### Metadata

`metadata` is sent as a JSON string in a form field. Pass a dictionary of your own keys and values. Leaving the key out sends `{}`. Passing `None` explicitly sends the JSON text `null`, so omit the key instead. If you also set `propagate_metadata` on [`jobs.create`](jobs.md), the job's metadata is applied to the files too.

#### Size limit

Alfred refuses an upload that is too large with `413 Payload Too Large`. The public documentation states a limit of 250 MB per file. Your workspace may set a lower limit in its cloud settings, and Alfred then also answers `413`. The response body contains a `message` and `max_bytes`, the limit that applied. The SDK does not check the size before sending, so the whole file is transferred before you learn it was rejected. Check the size yourself with `os.path.getsize` when you can. See [errors.md](errors.md) for how a `413` reaches your code.

#### Other things to know

- The channel field that the public API accepts for `uploadfile` is not exposed by `upload_file`.
- `upload_file` is a `POST` and is not retried automatically. If it times out, the file may or may not have arrived: list or check the session before uploading again.
- The default request timeout is 5 seconds (see [Timeout](configuration.md#timeout)). Raise it for large files.
- With HMAC authentication this call fails (see [authentication.md](authentication.md#hmac)). Use an API key or OAuth.

Errors worth handling (see [errors.md](errors.md)): `400` when the session is unknown, closed or expired (the `message` says which; open a new session), `403` when your role may not upload, `409` when your company's storage is not set up, `413` for a file over the limit.

## See also

- [Sessions](sessions.md): open the session that `upload_file` needs
- [Jobs](jobs.md): submit a session, follow a job, find the files of a job
- [Data points](data-points.md): read what Alfred extracted from a file
- [Real-time events](realtime.md): be told when a file is done instead of polling `get`
- [Error handling](errors.md)
