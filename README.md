# alfred-python

`alfred-python` is the Python client for the Alfred (TagShelf) REST API and its real-time event stream. It wraps the endpoints for sessions, files, jobs, data points and standalone classification, handles authentication, retries and rate-limit throttling, and can push job and file events to your code as they happen.

## Install

```bash
pip install alfred-python
```

The SDK detects the type of every local file you upload with `python-magic`, which needs the `libmagic` system library. The SDK loads it when you import `alfred.rest`, so a missing library shows up as an import error:

- Debian and Ubuntu: `apt-get install libmagic1`
- macOS: `brew install libmagic`
- Windows: nothing to install. The SDK depends on `python-magic-bin`, which bundles the library.

Supported Python versions are listed in [docs/compatibility.md](https://github.com/tagshelfsrl/alfred-python/blob/master/docs/compatibility.md).

## Quickstart

Upload a local file, process it as a job and read the extracted data points. You need an API key (see [authentication](https://github.com/tagshelfsrl/alfred-python/blob/master/docs/authentication.md)).

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

with open("invoice.pdf", "rb") as local_file:
    file_id = client.files.upload_file(
        {"file": local_file, "session_id": session_id}
    )["file_id"]

job_id = client.jobs.create({"session_id": session_id})["job_id"]

stopped = ("completed", "failed", "invalid", "canceled", "expired")
while client.jobs.get(job_id)["stage"] not in stopped:
    time.sleep(5)

print(client.data_points.get_values(file_id))
```

Polling is the simplest way to wait. To be notified instead, use the [real-time client](https://github.com/tagshelfsrl/alfred-python/blob/master/docs/realtime.md). [Getting started](https://github.com/tagshelfsrl/alfred-python/blob/master/docs/getting-started.md) explains each step.

## Documentation

Every page stands on its own. Start at the [documentation index](https://github.com/tagshelfsrl/alfred-python/blob/master/docs/README.md).

| Page | What it covers |
| --- | --- |
| [Getting started](https://github.com/tagshelfsrl/alfred-python/blob/master/docs/getting-started.md) | Install, create a client, and an end-to-end walkthrough from session to results. |
| [Authentication](https://github.com/tagshelfsrl/alfred-python/blob/master/docs/authentication.md) | API key, OAuth (username and password) and HMAC; the `ALFRED_API_KEY` environment variable. |
| [Configuration](https://github.com/tagshelfsrl/alfred-python/blob/master/docs/configuration.md) | Base URLs, HTTP settings (timeout, retries, throttling), response types, logging and custom HTTP clients. |
| [Files](https://github.com/tagshelfsrl/alfred-python/blob/master/docs/files.md) | Upload local files and remote URLs, read file details, download the original. |
| [Sessions](https://github.com/tagshelfsrl/alfred-python/blob/master/docs/sessions.md) | Deferred sessions: group several uploads into one job. |
| [Jobs](https://github.com/tagshelfsrl/alfred-python/blob/master/docs/jobs.md) | Create jobs, read their status, list them, and cancel, restart or check the sources of a job. |
| [Data points](https://github.com/tagshelfsrl/alfred-python/blob/master/docs/data-points.md) | Read the values Alfred extracted from a file, with their confidence and validation results. |
| [Classification](https://github.com/tagshelfsrl/alfred-python/blob/master/docs/classification.md) | Standalone classification: classify a text or a file against criteria you send with the request, without setting up document types first. |
| [Real-time events](https://github.com/tagshelfsrl/alfred-python/blob/master/docs/realtime.md) | Subscribe to job and file events over a socket; the full event catalogue. |
| [Error handling](https://github.com/tagshelfsrl/alfred-python/blob/master/docs/errors.md) | What the SDK raises and how to handle it. |
| [Compatibility](https://github.com/tagshelfsrl/alfred-python/blob/master/docs/compatibility.md) | Supported Python versions and dependency policy. |

## Development

Install the pinned dependencies, then run the tests:

```bash
pip install -r requirements.txt
python -m unittest
```

The unit tests (`tests/test_*.py`) need no credentials and never leave your machine. `tests/__init__.py` holds integration tests that call a real Alfred environment. They create a session and a job, so point them at a test tenant. They are skipped unless `ALFRED_API_KEY` is set. The variables they read:

| Variable | Default | Meaning |
| --- | --- | --- |
| `ALFRED_API_KEY` | none | API key. Without it the integration tests are skipped. |
| `ALFRED_BASE_URL` | `https://app.tagshelf.com` | Alfred environment to call. |
| `ALFRED_TEST_FILE_ID` | none | A file ID for `test_get_file`. The test is skipped when unset. |
| `ALFRED_TEST_UPLOAD_FILE` | none | Path of a local file for `test_upload_file`. The test is skipped when unset. |

Run one integration test with, for example, `python -m unittest tests.TestMain.test_get_file`.

Build the source distribution and wheel into `dist/` with `make build` (it runs `python -m build`). `make test` runs the unit tests and `make clean` removes build output.

## Contributing

- Pull requests target the `development` branch. `master` holds reviewed releases, which are published from it.
- Pull request titles are checked for a semantic prefix: `chore`, `docs`, `fix`, `feat`, `misc`, `test` or `release`, for example `fix(files): keep the original file name`.
- The test suite runs on every pull request. Add or update tests with your change, and update the matching page in `docs/` when behaviour changes.

## License

MIT. See [LICENSE](https://github.com/tagshelfsrl/alfred-python/blob/master/LICENSE).
