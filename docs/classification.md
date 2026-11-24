# Standalone classification

Standalone classification decides which of a caller's own document types a document belongs to. The request carries the criteria (a name and a description per document type) and the document's text or one file, and the answer is a zero-shot decision that is polled for. It is different from classifying against the document types configured in the account: no document type has to exist beforehand.

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

The domain is `client.classifications`.

## Things to know first

- **Each request is a billed job.** A request creates a real job with one file, listed and billed like any other job. The `id` of the answer is the id of that job, so it also works with the jobs domain (see [jobs.md](jobs.md)).
- **No idempotency.** Sending the same POST twice creates, classifies and bills two jobs. `correlation_id` is stored and echoed back, never used to remove duplicates. Do not retry `create` or `create_from_file` blindly after a timeout. If an id was received, call `get` with it first.
- **Availability.** The feature is switched on per environment and per company. Where it is off for the account, the API answers 403.
- **The criteria** (the server enforces these and answers 400 or 413; the SDK does not check them):
  - 2 to 50 criteria.
  - `name`: required, at most 350 characters, unique ignoring case and surrounding spaces.
  - `description`: required, at most 1,000 characters. A zero-shot classifier has nothing else to go on.
  - `threshold`: optional, a number from 0 to 1. The default 0 always picks the best criterion.
  - Any other key on a criterion is ignored.
- **Text or file, never both.** A request carries either `text` or one file.

## Statuses

| `status` | Meaning |
|---|---|
| `queued` | The decision is on its way or being applied. Keep polling. |
| `completed` | The decision is in `result`, and `completed_at` is set. |
| `failed` | The request failed or was cancelled. `error` has the reason, and `completed_at` is set. |

`ClassificationStatus` (in `alfred.rest.classifications`) holds the three values as a string enum.

### create

Starts a classification of a text. Not safe to retry blindly (see above).

```python
answer = client.classifications.create(payload)
```

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `payload["tags"]` | list of criteria | required | The criteria: dicts with `name`, `description` and an optional `threshold`. |
| `payload["text"]` | `str` | required | The document's text. Up to 200,000 characters are accepted and the first 32,000 are classified. |
| `payload["file_name"]` | `str` | none | Name for the stored text, at most 250 characters. `.txt` is added when missing. Without it the server uses `classify.txt`. |
| `payload["correlation_id"]` | `str` | none | The caller's own reference, at most 512 characters. Stored on the job and echoed back. |

The payload is sent as the JSON body unchanged.

Returns the 202 answer:

| Field | Type | Meaning |
|---|---|---|
| `id` | `str` | Id of the job. Use it with `get`. |
| `file_id` | `str` | Id of the job's one file. |
| `status` | `str` | `queued`. |
| `created_at` | `str` | Creation time, ISO 8601. |
| `correlation_id` | `str` | The value sent, `""` when none. |
| `text_truncated` | `bool` | `true` when the text is longer than the 32,000 characters classified. |

```json
{
  "id": "6f1b2c3d-4e5f-4a6b-8c7d-9e0f1a2b3c4d",
  "file_id": "5a6b7c8d-9e0f-4a1b-8c2d-3e4f5a6b7c8d",
  "status": "queued",
  "created_at": "2026-11-12T13:00:00.123Z",
  "correlation_id": "order-42",
  "text_truncated": false
}
```

Example:

```python
answer = client.classifications.create(
    {
        "tags": [
            {
                "name": "Invoice",
                "description": "A commercial invoice: seller, buyer, line items, totals, tax id.",
                "threshold": 0.6,
            },
            {"name": "Receipt", "description": "A point-of-sale receipt."},
        ],
        "text": "INVOICE 0001 ... ACME S.R.L. ... Total 1,250.00",
        "correlation_id": "order-42",
    }
)
print(answer["id"], answer["status"])
```

Errors worth handling: 400 (bad criteria or text), 403 (feature off), 413 (over a limit), 503 (see the [refusals](#refusals)).

### create_from_file

Starts a classification of one file. Not safe to retry blindly.

```python
answer = client.classifications.create_from_file(payload)
```

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `payload["file"]` | binary file object (`BufferedReader` or `BytesIO`) | required | The file. Its first 1,024 bytes are sniffed for the MIME type and the read position is reset to the start before sending. |
| `payload["tags"]` | list of criteria | required | The same criteria as `create`. Sent as a JSON string in the `tags` multipart field. |
| `payload["filename"]` | `str` | name of the opened file | Name sent with the file. |
| `payload["correlation_id"]` | `str` | none | Sent only when given and not empty. |

File name rule: an explicit `filename` wins over the name of an opened file. When `filename` is not given, the base name of an opened file is used. A `BytesIO` has no name, so `filename` is required and its absence raises `AlfredMissingArgument` before any request. A missing `file` also raises `AlfredMissingArgument`. This differs from `files.upload_file`, where the opened file's name always wins. The reason is that the server decides the file type from the extension of the name, not from the MIME type. A name therefore needs a supported extension (`.pdf`, `.png`, `.jpg`, `.jpeg`, `.webp`, `.tif`, `.tiff`, `.gif`, `.txt`, or one of the other JPEG names `.jfif`, `.jfi`, `.jif`, `.jpe`, `.pjpeg`, `.pjp`), and a caller whose file has a temporary or extensionless name can pass a correct one.

File rules of the server:

- Formats: PDF, PNG, JPEG, WebP, TIFF, GIF and UTF-8 text.
- At most 20 MB per file. The whole multipart body is bounded at 22 MB.
- Only the first ten pages (or image frames) and the first 32,000 characters of text are classified. One file produces one result, never one per page.
- Corrupt, encrypted or unreadable content is not refused at upload: the request later ends with `status` `failed`.

Returns the same 202 answer as `create`. In the answer of `get`, a file request also carries an `input` block (see [get](#get)).

Example:

```python
with open("invoice.pdf", "rb") as handle:
    answer = client.classifications.create_from_file(
        {
            "file": handle,
            "tags": [
                {"name": "Invoice", "description": "A bill for goods or services."},
                {"name": "Other", "description": "Any other type of document."},
            ],
            "correlation_id": "invoice-trial-42",
        }
    )
print(answer["id"])
```

Errors worth handling: `AlfredMissingArgument` (no file, or no name), 400 (unsupported name, empty file, bad criteria), 403, 413 (file over 20 MB), 503.

### get

Fetches a classification by the `id` of the answer to `create` or `create_from_file`.

```python
answer = client.classifications.get(classification_id)
```

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `classification_id` | `str` or `uuid.UUID` | required | The job id. `None` or a blank string raises `ValueError` and any other type raises `TypeError`, both before any request. The id is URL-quoted into the path. |

Returns the parsed answer unchanged:

| Field | Type | Meaning |
|---|---|---|
| `id`, `file_id`, `status`, `created_at`, `correlation_id`, `text_truncated` | | As in the 202 answer. |
| `completed_at` | `str` | Present when `completed` or `failed`. |
| `result` | object | Present when `completed`. |
| `error` | object | Present when `failed`. |
| `input` | object | Present for file requests once the result is available. |

JSON dialect: names are snake_case, a null string arrives as `""`, and any other null is left out, so keys such as `completed_at`, `result` and `error` exist only when they have a value.

`result`:

| Field | Type | Meaning |
|---|---|---|
| `class` | `str` | Name of the criterion picked, as spelled in the request. `""` when no criterion matched. |
| `score` | `float` | Score of that criterion. |
| `below_threshold` | `bool` | `true` when the score is under the criterion's threshold. `class` is still the best guess, so the caller decides what to do. |
| `predictions` | list | Every criterion's score as the classifier gave it, highest first, as `{"class", "score"}`. Empty when no call was made. |
| `model` | `str` | `zero`, the zero-shot classifier. |
| `reasoning` | `str` | The classifier's explanation. Left out when there is none. |
| `reason` | `str` | Only when `class` is `""`: why. Left out otherwise. |
| `answered` | `str` | With `no_match`: the raw label the classifier gave, when it gave one. |

No-class reasons (a completed answer, not a failure):

| `reason` | Meaning |
|---|---|
| `no_match` | The classifier answered with none of the criteria. |
| `no_text` | No text was found to classify. |
| `no_candidates` | No criterion was offered to the classifier. |

`error`: `code` is `classification_failed` (the worker failed, its answer could not be applied, or the request never reached it), `canceled` (the job was cancelled or expired first) or `failed` (any other failure). `message` is the newest error recorded.

`input` (file requests): `pages`, `classified_pages`, `pages_truncated`, `text_truncated`, `bytes` and `mode` (`native_text` or `ocr_text`). Worker builds that read the file first also report `ocr_pages`, `native_pages` and, when OCR was used, `ocr_provider`. A key can be absent. For file requests the top-level `text_truncated` repeats `input.text_truncated`.

Completed example:

```json
{
  "id": "6f1b2c3d-4e5f-4a6b-8c7d-9e0f1a2b3c4d",
  "file_id": "5a6b7c8d-9e0f-4a1b-8c2d-3e4f5a6b7c8d",
  "status": "completed",
  "created_at": "2026-11-12T13:00:00.123Z",
  "completed_at": "2026-11-12T13:00:05.410Z",
  "correlation_id": "order-42",
  "text_truncated": false,
  "result": {
    "class": "Invoice",
    "score": 0.91,
    "below_threshold": false,
    "predictions": [
      {"class": "Invoice", "score": 0.91},
      {"class": "Receipt", "score": 0.06}
    ],
    "model": "zero",
    "reasoning": "Seller, buyer, line items and a total."
  }
}
```

Failed example:

```json
{
  "id": "6f1b2c3d-4e5f-4a6b-8c7d-9e0f1a2b3c4d",
  "file_id": "5a6b7c8d-9e0f-4a1b-8c2d-3e4f5a6b7c8d",
  "status": "failed",
  "created_at": "2026-11-12T13:00:00.123Z",
  "completed_at": "2026-11-12T13:00:09.002Z",
  "correlation_id": "",
  "text_truncated": false,
  "error": {"code": "classification_failed", "message": "The classifier could not read the file."}
}
```

Errors worth handling: 404 (not a classification job of the account), 403, 500.

#### Polling

The server recommends polling every 1 to 2 seconds. On staging the zero-shot call alone takes about 4.8 seconds at the median and 8.4 seconds at the 95th percentile. A polling loop with a timeout:

```python
import time

def wait_for_classification(client, classification_id, timeout=60.0, interval=1.5):
    deadline = time.monotonic() + timeout
    while True:
        answer = client.classifications.get(classification_id)
        if answer["status"] in ("completed", "failed"):
            return answer
        if time.monotonic() >= deadline:
            raise TimeoutError(f"Classification {classification_id} is still queued.")
        time.sleep(interval)


answer = client.classifications.create(
    {
        "tags": [
            {"name": "Invoice", "description": "A commercial invoice."},
            {"name": "Receipt", "description": "A point-of-sale receipt."},
        ],
        "text": "INVOICE 0001 ... Total 1,250.00",
    }
)
final = wait_for_classification(client, answer["id"])

if final["status"] == "failed":
    print("failed:", final["error"]["code"], final["error"]["message"])
else:
    result = final["result"]
    if result["class"] == "":
        print("no class:", result.get("reason"))
    elif result["below_threshold"]:
        print("best guess below threshold:", result["class"], result["score"])
    else:
        print(result["class"], result["score"])
```

A `TimeoutError` in this loop does not mean the request failed. The job is still running and billed, so call `get` again later with the same id instead of calling `create` again.

## Refusals

| Status | Body | Cause |
|---|---|---|
| 400 | `{"errors": [...]}` | A bad body: the reasons are a list of strings under `errors`. Also when the workspace has no settings or no storage account. |
| 403 | `{"message": "..."}` | Standalone classification is not enabled for the account, or the caller belongs to no company. |
| 404 | `{"message": "..."}` | `get` of an id that is not a classification job of the caller's company. |
| 413 | `{"message": "..."}` | Over a limit: a body over 2 MB, a file over 20 MB, more than 50 criteria, a description over 1,000 characters, a text over 200,000 characters. |
| 500 | `{"message": "..."}` | Alfred could not store or read the request. Nothing was created or sent. |
| 503 | `{"message": "..."}` | The classifier is off, processing is on hold for the workspace, or the request could not be sent. |

A 400 answer carries its reasons as a list under `errors`, for example:

```json
{"errors": ["tags needs at least 2 criteria; it has 1."]}
```

The SDK does not translate or catch these answers. How they surface as exceptions is described in [errors.md](errors.md).

## See also

- [jobs.md](jobs.md): the job each request creates.
- [files.md](files.md): the file of that job.
- [errors.md](errors.md): how HTTP errors surface in the SDK.
- [authentication.md](authentication.md) and [configuration.md](configuration.md): client setup.
