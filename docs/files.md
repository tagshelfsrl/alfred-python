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

Returns the file as a dictionary. The SDK returns what Alfred sent, unchanged; the type is `FileDetailsResponse` in `alfred.rest.files`, and the tables below list every field of Alfred 1.130.0.

Text fields without a value are sent as an empty string. Identifiers, dates and `metadata` are left out when they have no value, so read those with `.get()`; the tables mark them "optional".

The fields most integrations use:

| Field | Type | Meaning |
| --- | --- | --- |
| `id` | string | The file's ID. |
| `file_name`, `file_name_without_extension` | string | The name the file was stored under. |
| `content_type` | string | The file's MIME type, for example `application/pdf`. |
| `file_size`, `size` | integer | Size in bytes (the same number under two names). |
| `status` | string | Where the file is in processing, for example `finished`. The values are listed in the public [File Status](https://docs.tagshelf.dev/endpoints/file/file-status) page. |
| `is_result_ready` | boolean | Whether the file has a result you can read. See [When a file's results are ready](#when-a-files-results-are-ready). New in Alfred 1.130.0. |
| `tag_id`, `tag_name` | string | The tag (document type) assigned to the file. `tag_id` is optional: it is present once the file has a tag. |
| `classification_score` | number | Confidence in the tag, from 0 to 1. |
| `channel` | string | How the file reached Alfred, for example `api`. |
| `metadata` | object | Optional. The metadata you attached when you uploaded the file. |
| `page_count`, `page_number` | integer | Number of pages; for a page split out of a larger document, its page number in the original. |
| `is_parent`, `parent_id` | boolean, string | `is_parent` is `true` for a document Alfred split into several files. `parent_id` (optional) is on each of those files and points at the original. |
| `deferred_session_id` | string | Optional. The session the file was uploaded into. |
| `is_duplicate`, `duplicate_origin_id` | boolean, string | Whether the file is an exact copy of one Alfred already processed, and (optional) which one. |
| `creation_date`, `update_date` | string | ISO 8601 timestamps in UTC. |

How the file relates to other files:

| Field | Type | Meaning |
| --- | --- | --- |
| `input_type` | string | `single_unit`: processed as it is. `primary`: an original that Alfred split into parts. `derived`: one of those parts. `virtual`: a document Alfred composed from several pages. |
| `group_role` | string | The file's part in a group of pages: `standalone` (not part of one, the usual case), `virtual` (the composed document, which has no stored file of its own and holds the classification and extraction for its pages) or `member` (a page whose extraction belongs to the `virtual` file of its group). New in Alfred 1.130.0. |
| `group_id` | string | Optional. Present when page grouping ran for the file. It does not by itself say the file belongs to a document of several pages: read `group_role` for that. New in Alfred 1.130.0. |
| `is_processing_unit` | boolean | Whether the file is classified and extracted in its own right. It is `false` for a parent that was split and for a `member` page. New in Alfred 1.130.0. |
| `job_order_index` | integer | The file's position in its job's processing order. |

Classification and review:

| Field | Type | Meaning |
| --- | --- | --- |
| `should_be_classified` | boolean | Whether Alfred is to classify the file. |
| `classifier` | string | The mechanism that classified the file. |
| `proposed_tag_id` | string | Optional. The tag the classifier proposed. |
| `proposed_tag_variance`, `classification_score_above_deviation` | number, boolean | Figures recorded when the file was classified: the variance of the proposed tag, and whether its score was above the standard deviation. |
| `manual_classification` | boolean | Whether the tag was set by hand. |
| `confirmed_tag_id`, `confirmed_by` | string | The tag confirmed for the file (optional) and who confirmed it. |
| `assigned_to`, `assignment_date` | string | The user the file is assigned to, and when (the date is optional). |
| `validation_date` | string | Optional. When the file was validated. |
| `exclude_from_classification_data` | boolean | Whether the file is kept out of the data sets used for classification. |

Extraction and duplicates by content:

| Field | Type | Meaning |
| --- | --- | --- |
| `extraction_type` | string | How the file's data points were extracted: `none` (not extracted, or its tag has no data points), `text`, `multimodal` (text and images) or `reused` (copied from another file without running extraction). |
| `is_data_duplicate` | boolean | Whether the file counts as a duplicate because its data points match another file's. |
| `is_duplicate_by_values` | boolean | Whether a validation rule found that some of its values repeat those of other files. |
| `effective_metadata` | string | The file's metadata merged with its job's. Unlike `metadata`, it is JSON text, so parse it with `json.loads`. |

Storage and ownership:

| Field | Type | Meaning |
| --- | --- | --- |
| `blob_name`, `blob_url` | string | Where Alfred stores the file. |
| `md5_hash` | string | The MD5 of the content, base64-encoded. |
| `user_name` | string | The user or application that uploaded the file. |
| `company_id` | string | The account the file belongs to. |
| `description` | string | A short description of the file. |

```python
file = client.files.get("559167cb-4c76-4e28-bf15-34cbf614119c")

print(file["status"], file["tag_name"], file["classification_score"])
```

Example response:

```json
{
  "id": "559167cb-4c76-4e28-bf15-34cbf614119c",
  "creation_date": "2026-11-24T13:05:11.300Z",
  "update_date": "2026-11-24T13:07:40.910Z",
  "file_name": "invoice-1042.pdf",
  "file_name_without_extension": "invoice-1042",
  "size": 182344,
  "file_size": 182344,
  "blob_name": "559167cb-4c76-4e28-bf15-34cbf614119c.pdf",
  "blob_url": "https://storage.example.com/files/559167cb-4c76-4e28-bf15-34cbf614119c.pdf",
  "user_name": "erp-integration",
  "md5_hash": "1B2M2Y8AsgTpgAmY7PhCfg==",
  "content_type": "application/pdf",
  "channel": "api",
  "description": "",
  "status": "finished",
  "input_type": "single_unit",
  "extraction_type": "text",
  "should_be_classified": true,
  "exclude_from_classification_data": false,
  "classifier": "",
  "classification_score": 0.97,
  "tag_id": "a3c7e2b1-58d4-4f0e-9c2a-6b1d7e8f9a03",
  "tag_name": "Invoice",
  "proposed_tag_id": "a3c7e2b1-58d4-4f0e-9c2a-6b1d7e8f9a03",
  "proposed_tag_variance": 0.0,
  "classification_score_above_deviation": true,
  "confirmed_by": "",
  "manual_classification": false,
  "is_duplicate": false,
  "is_data_duplicate": false,
  "is_duplicate_by_values": false,
  "is_parent": false,
  "group_role": "standalone",
  "is_processing_unit": true,
  "is_result_ready": true,
  "page_count": 1,
  "page_number": 0,
  "job_order_index": 0,
  "deferred_session_id": "0f767925-b464-4ffa-b621-1a0aeacac256",
  "company_id": "286e2ed0-3626-4faa-a745-8ebf3488fbd7",
  "metadata": { "customer": "ACME" },
  "effective_metadata": "{\"customer\": \"ACME\"}",
  "assigned_to": ""
}
```

#### When a file's results are ready

`is_result_ready` is `true` when Alfred has a result for the file that you can read with [`data_points.get_values`](data-points.md): the file is a processing unit (`is_processing_unit`) and its `status` is `finished`, `confirmation_required` or `pending_job_validation`. In the last two a person's review or a check across the job is still pending, so the values can change.

```python
file = client.files.get("559167cb-4c76-4e28-bf15-34cbf614119c")

if file["is_result_ready"]:
    values = client.data_points.get_values(file["id"])
elif not file["is_processing_unit"]:
    print("this file has no result of its own:", file["input_type"], file["group_role"])
else:
    print("not ready yet:", file["status"])
```

A file that is not a processing unit never becomes ready. That is a parent Alfred split into parts (read the parts instead) or a `member` page of a group (its extraction belongs to the group's `virtual` file). The files of a job carry the same four fields, so you can pick the ready ones from [`jobs.get`](jobs.md) with the full view without asking for each file.

`is_result_ready`, `is_processing_unit`, `group_role` and `group_id` are sent by Alfred 1.130.0 and later.

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
| `original_name` | string or `None` | The file name from the `Content-Disposition` response header, exactly as the server sent it. |
| `mime_type` | string | The `Content-Type` response header. |

```python
import re
from pathlib import Path

result = client.files.download("559167cb-4c76-4e28-bf15-34cbf614119c")

# The server chooses the name. Keep only what follows the last path separator
# or drive colon, so that it cannot point outside the directory you write to,
# and use a name of your own if nothing usable is left.
name = re.split(r"[\\/:]", result["original_name"] or "")[-1]
if name in ("", ".", ".."):
    name = "download.bin"

target_dir = Path("downloads")
target_dir.mkdir(exist_ok=True)
(target_dir / name).write_bytes(result["file"].getvalue())
```

Notes:

- The file is read fully into memory; there is no streaming. Keep that in mind for large files.
- `original_name` comes from the server, so do not pass it to `open` as it is: it could be an absolute path or contain `../`. The example keeps only the last component and writes inside a directory it chose. Two downloads can share a name; add the file ID to the name if you need them to be unique.
- If the response carries no file name (no `Content-Disposition` header, or one without a name), `original_name` is `None`. Alfred sets the header for downloads, so this appears only behind a proxy that strips it. When the header carries both a plain and an encoded name, the encoded one is used.
- A downloaded file whose `Content-Type` is `application/json` or `application/xml` is also run through the SDK's response parser (see [Response types](configuration.md#response-types)), and a file that does not parse as its declared type raises `AlfredResponseParseError` (a `ValueError`).

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
| `file_name`, `file_names` | `str`, `list[str]` | none | With `source` and `container`: the name(s) of the file(s) in that container. |
| `filename`, `filenames` | `str`, `list[str]` | none | Deprecated spellings of `file_name` and `file_names`. The API does not read them, so the SDK sends them under the names above; a value given under the API's own name wins. Use `file_name` and `file_names` in new code. |
| `channel` | `str` | none | The job's channel, for example `api`. |
| `correlation_id` | `str` | none | Your own identifier for the operation, at most 512 characters. See [correlation IDs](jobs.md#correlation-ids). |
| `merge` | `bool` | `false` | Merge all the files into one PDF. Only works when the files are images. |
| `metadata` | `dict` or `list[dict]` | none | Your own data. Send one object for a single file, or when `merge` or `propagate_metadata` is true. Otherwise send one object per file, in the same order as the URLs. |
| `propagate_metadata` | `bool` | `false` | Apply the single `metadata` object to every file. |
| `parent_file_prefix` | `str` | none | Virtual folder for the documents split out of each file (used when splitting). |
| `password` | `str` | none | Password for protected files. See [Password-protected files](#password-protected-files). |

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

- The result has a `job_id`, not a `file_id` (a `file_id` is what `upload_file` returns). To find the files of the job, use [`jobs.get`](jobs.md).
- Apart from the two deprecated names above, the SDK sends your dictionary to the server as is, without validating or filtering it. Fields that the public API accepts but the payload type does not list, such as `decompose`, `page_rotation` and `priority`, are forwarded and work at runtime; a type checker will flag them. See the public [Upload files from URLs](https://docs.tagshelf.dev/endpoints/file) reference for what they do.
- Retries: `upload` is a `POST` and is not retried automatically (see [Retries](configuration.md#retries)). If it fails with a timeout, check the job list before sending again, or you may create the job twice.

#### Password-protected files

Alfred 1.130.0 accepts a password for protected PDFs, zips (ZipCrypto or AES) and Office files (docx, xlsx, pptx). Add an optional top-level `password` string to the `upload` payload:

```python
result = client.files.upload(
    {
        "urls": ["https://files.example.com/statements/statement.pdf"],
        "password": "the file's password",
    }
)
print(result["job_id"])
```

- The password applies to every file of the request and to anything inside them: the entries of a protected zip, or a protected PDF inside a zip.
- It can be at most 256 bytes in UTF-8, and Alfred uses it exactly as sent (not trimmed or normalised). `None` or leaving it out means no password.
- Send it in the body, as shown. Alfred never reads a password from the query string or headers.
- Availability: the feature is switched on per environment. Where it is off, or for accounts on the legacy pipeline, Alfred refuses the request with `400` and a message saying so; it never accepts the request and silently ignores the password. Other `400` messages cover a password that is not a string, empty or too long.
- A protected file sent without a password, or with the wrong one, ends with the status "Password required".
- Inbound email and Drive or bucket sources cannot carry a password: their protected files also end as "Password required".
- For local files uploaded with `upload_file`, the password is sent when the session becomes a job instead (see [`upload_file`](#upload_file)).
- The SDK forwards the dictionary as is and does not keep the password. Its request log does not print JSON bodies (see [Logging](configuration.md#logging)), and error messages do not quote the request. An error raised for the call does carry the request it was sent with, password included, in its `request` attribute (see [errors.md](errors.md#what-an-api-error-carries)), so do not log that object whole.

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

`metadata` is sent as a JSON string in a form field. Pass a dictionary of your own keys and values. Leaving the key out, or passing `None`, sends `{}`. If you also set `propagate_metadata` on [`jobs.create`](jobs.md), the job's metadata is applied to the files too.

#### Size limit

Alfred refuses an upload that is too large with `413 Payload Too Large`. The public documentation states a limit of 250 MB per file. Your workspace may set a lower limit in its cloud settings, and Alfred then also answers `413`. The response body contains a `message` and `max_bytes`, the limit that applied. The SDK does not check the size before sending, so the whole file is transferred before you learn it was rejected. Check the size yourself with `os.path.getsize` when you can. See [errors.md](errors.md) for how a `413` reaches your code.

#### Passwords

`upload_file` has no password field. The password is not sent with each file: send it when the session becomes a job, as `client.jobs.create({"session_id": session_id, "password": "..."})`. See [jobs.md](jobs.md) for the job side and [Password-protected files](#password-protected-files) under `upload` for the rules.

#### Other things to know

- The channel field that the public API accepts for `uploadfile` is not exposed by `upload_file`.
- `upload_file` is a `POST` and is not retried automatically. If it times out, the file may or may not have arrived: list or check the session before uploading again.
- The default request timeout is 5 seconds (see [Timeout](configuration.md#timeout)). Raise it for large files.

Errors worth handling (see [errors.md](errors.md)): `400` when the session is unknown, closed or expired (the `message` says which; open a new session), `403` when your role may not upload, `409` when your company's storage is not set up, `413` for a file over the limit.

## See also

- [Sessions](sessions.md): open the session that `upload_file` needs
- [Jobs](jobs.md): submit a session, follow a job, find the files of a job
- [Data points](data-points.md): read what Alfred extracted from a file
- [Classification](classification.md): classify a text or file against criteria you send with the request
- [Real-time events](realtime.md): be told when a file is done instead of polling `get`
- [Error handling](errors.md)
