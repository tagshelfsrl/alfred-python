# Getting started

This page takes you from installation to extracted data: you open a session, upload local files into it, create a job from the session, wait for the job and read the results. Every step says why it is needed.

## Install

```bash
pip install alfred-python
```

The SDK identifies local files with `python-magic`, which needs the `libmagic` system library on Linux and macOS (`apt-get install libmagic1`, `brew install libmagic`). On Windows the SDK installs `python-magic-bin`, which bundles it. A missing library shows up as an import error when you import `alfred.rest`. Supported Python versions are listed in [compatibility.md](compatibility.md).

## Create a client

You need an API key for your Alfred workspace. Other methods are described in [authentication.md](authentication.md).

```python
from alfred.base.config import Configuration
from alfred.http.typed import AuthConfiguration
from alfred.rest import AlfredClient

client = AlfredClient(
    config=Configuration.v1(),
    auth_config=AuthConfiguration({"api_key": "YOUR_API_KEY"}),
)
```

`Configuration.v1()` points at `https://app.tagshelf.com`. To use another environment, pass `Configuration.v1({"base_url": "https://..."})` (see [configuration.md](configuration.md)). The client exposes five domains: `client.sessions`, `client.files`, `client.jobs`, `client.data_points` and `client.classifications`. This page uses the first four; [classification.md](classification.md) covers the fifth.

## The flow

Alfred processes documents as jobs. A job groups one or more files. For files on your machine, the flow has four steps:

1. open a deferred session, a container that collects uploads;
2. upload each file into the session;
3. create a job from the session, which closes it and starts processing;
4. wait for the job, then read the results.

Why a session? A job is created once, with all its files. A session lets you upload files one at a time, or from different processes, before that happens. If your files are at public URLs instead, skip the session and use [`files.upload`](files.md#upload).

### 1. Create a session

```python
session_id = client.sessions.create()["session_id"]
```

The session ID ties the uploads and the job together. See [sessions.md](sessions.md).

### 2. Upload the files

```python
uploaded = []

for path in ["invoice-1042.pdf", "invoice-1043.pdf"]:
    with open(path, "rb") as local_file:
        result = client.files.upload_file(
            {
                "file": local_file,
                "session_id": session_id,
                "metadata": {"source": "getting-started"},
            }
        )
    uploaded.append((path, result["file_id"]))

print(uploaded)
```

Each call returns the `file_id` of the uploaded file. Keep these IDs: you use them to read details and values later. The file name is taken from the path you opened, and the file type is detected from its content. The optional `metadata` is your own data; Alfred stores it with the file and returns it in the file's details. More in [files.md](files.md#upload_file).

Uploaded files are stored but not processed yet. Alfred waits for you to submit the session.

### 3. Create the job

```python
job = client.jobs.create({"session_id": session_id})
job_id = job["job_id"]
print(job_id)
```

Submitting the session closes it and starts processing. After this you cannot upload more files into that session; open a new one for the next batch. If any of the files is a password-protected PDF, zip or Office file, send the password here, as `"password": "..."` in the same dictionary, because a session's files are uploaded without one (see [jobs.md](jobs.md)). The other options of `jobs.create` (merging, decomposing, channel, metadata for the whole job) are described in [jobs.md](jobs.md).

### 4. Wait for the job

Processing is asynchronous. The simplest way to wait is to poll the job's `stage`:

```python
import time

STOPPED = {"completed", "failed", "invalid", "canceled", "expired"}

deadline = time.monotonic() + 15 * 60
while True:
    stage = client.jobs.get(job_id)["stage"]
    print("stage:", stage)
    if stage in STOPPED:
        break
    if time.monotonic() > deadline:
        raise TimeoutError(f"Job {job_id} did not finish in time (stage: {stage})")
    time.sleep(5)
```

`STOPPED` lists the stages after which the job does no more work. The authoritative list of stages and what each means is in [jobs.md](jobs.md); check it before relying on this set.

Polling costs a request per check and counts against your rate limit, so keep the interval at a few seconds or more. The better option is the real-time client, which tells you the moment the job ends (`alfred_event_job_finished`, `alfred_event_job_failed` and the other closing events), with no polling. See [realtime.md](realtime.md), which has a complete example of submitting a job and waiting for the event.

### 5. Read the file details

When the job has ended, look at each file:

```python
for path, file_id in uploaded:
    file = client.files.get(file_id)
    print(path, file["status"], file.get("tag_name"), file.get("classification_score"))
```

`status` is where the file ended (`finished` means the results are ready), `tag_name` is the document type Alfred assigned and `classification_score` is its confidence between 0 and 1. A document that Alfred split into several files produces more files than you uploaded; each has a `parent_id` pointing at the original. See [files.md](files.md#get).

### 6. Read the data points

```python
for path, file_id in uploaded:
    values = client.data_points.get_values(file_id)
    print(path, {item["field_key"]: item["value"] for item in values})
```

Each item is one extracted value, keyed by a stable `field_key`, with Alfred's confidence in it (`classification_score`) and, when the data point has validators, what they found. A file with no tag, or whose tag has no data points, has no values, and the call fails with a not found error. See [data-points.md](data-points.md).

To keep the original, `client.files.download(file_id)` returns the bytes and the original name ([files.md](files.md#download)).

## The whole script

```python
import time

from alfred.base.config import Configuration
from alfred.http.typed import AuthConfiguration
from alfred.rest import AlfredClient

client = AlfredClient(
    config=Configuration.v1(),
    auth_config=AuthConfiguration({"api_key": "YOUR_API_KEY"}),
)

session_id = client.sessions.create()["session_id"]

uploaded = []
for path in ["invoice-1042.pdf", "invoice-1043.pdf"]:
    with open(path, "rb") as local_file:
        file_id = client.files.upload_file(
            {"file": local_file, "session_id": session_id}
        )["file_id"]
    uploaded.append((path, file_id))

job_id = client.jobs.create({"session_id": session_id})["job_id"]

STOPPED = {"completed", "failed", "invalid", "canceled", "expired"}
while client.jobs.get(job_id)["stage"] not in STOPPED:
    time.sleep(5)

for path, file_id in uploaded:
    file = client.files.get(file_id)
    print(path, file["status"], file.get("tag_name"))
    if file["status"] == "finished":
        values = client.data_points.get_values(file_id)
        print({item["field_key"]: item["value"] for item in values})
```

## When things go wrong

- A bad key is answered with `401` on the first call.
- Uploads and job creation are `POST` requests and are not retried by the SDK. If one times out, check what arrived before repeating it, or you may create duplicates.
- The default timeout is 5 seconds; raise it in [configuration.md](configuration.md#timeout) if large uploads time out.
- Error handling in general: [errors.md](errors.md).

## Next steps

- [Real-time events](realtime.md): replace polling with pushed events
- [Files](files.md), [Sessions](sessions.md), [Jobs](jobs.md), [Data points](data-points.md): each domain in full
- [Classification](classification.md): classify a text or file against criteria you send, without setting up document types first
- [Authentication](authentication.md) and [Configuration](configuration.md)
