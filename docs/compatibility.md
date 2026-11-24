# Compatibility and dependencies

This page lists the Python versions the SDK supports, the packages it depends on, and how those dependencies are kept free of known vulnerabilities.

## Supported Python versions

The SDK requires Python 3.10 or newer. CI runs the test suite on Python 3.10, 3.11, 3.12, 3.13 and 3.14.

The minimum is 3.10 because the patched releases of two core dependencies no longer support older interpreters. `requests` 2.33.0 and `urllib3` 2.8.0 are the first releases that fix their known vulnerabilities, and both require Python 3.10 or newer. No patched release exists for Python 3.8 or 3.9, which are also past end of life.

On Python 3.9 or older, installing from a checkout (`pip install .`) fails with `Package 'alfred-python' requires a different Python: 3.9.x not in '>=3.10'`. When installing from PyPI, pip skips releases whose `Requires-Python` does not match and installs the newest older release your interpreter allows. Those older releases are not patched, so upgrade Python instead.

## Runtime dependencies

The minimum versions below are the first releases that fix a known vulnerability. They are declared in `pyproject.toml` and apply to every install.

| Package | Minimum | Used for |
|---|---|---|
| `requests` | 2.33.0 | HTTP calls to the REST API. |
| `urllib3` | 2.8.0 | Connection pooling and retry policy for the HTTP client. |
| `python-socketio` | 5.16.2 | Realtime events over Socket.IO. |
| `websocket-client` | 1.8 | WebSocket transport for the realtime client. |
| `python-magic` | 0.4.27 (pinned) | Detecting the MIME type of files before upload. |
| `python-magic-bin` | 0.4.14 (pinned, Windows only) | Bundled libmagic for Windows. |
| `certifi` | 2026.10.18 | Security floor for a transitive dependency of `requests`. CA bundle for TLS. |
| `idna` | 3.15 | Security floor for a transitive dependency of `requests`. Internationalised domain names. |

`python-engineio` (the Engine.IO transport layer under `python-socketio`) has no entry of its own: `python-socketio` 5.16.2 requires `python-engineio` 4.13.2 or newer, so the floor on `python-socketio` already forces a patched release.

## System requirements for python-magic

`python-magic` wraps the native `libmagic` library, which pip does not install.

- Debian and Ubuntu: `sudo apt-get install libmagic1`
- macOS: `brew install libmagic`
- Windows: nothing to install. The SDK depends on `python-magic-bin`, which ships libmagic.

In a slim Docker image, install `libmagic1` before importing `alfred`:

```dockerfile
FROM python:3.12-slim
RUN apt-get update && apt-get install -y libmagic1 && rm -rf /var/lib/apt/lists/*
RUN pip install alfred-python
```

## Dependency policy

- Every dependency has a lower bound at the first release that fixes its known vulnerabilities. Newer releases are allowed.
- There are no upper caps and no exact pins, so the SDK installs next to your own dependencies. The only exceptions are the two `python-magic` packages, which are pinned.
- Transitive packages with a known vulnerability get an explicit lower bound in `pyproject.toml`, with a comment marking it as a security floor, when the bounds of the direct dependencies do not already force a patched release.
- `requirements.txt` is a fully pinned snapshot used by CI and for development. It is not what users install: `pip install alfred-python` resolves the bounds in `pyproject.toml`.

## Automated audit

The pull request workflow (`.github/workflows/on-pr.yml`) has a `Dependency audit` job. It runs `pip-audit` against `requirements.txt` and fails the pull request when any pinned package has a known vulnerability. Platform markers are removed first, so the Windows-only `python-magic-bin` is audited too, even though the job runs on Linux. It needs no secrets: only package names and versions are sent to the vulnerability database.

To run the same check locally:

```bash
python -m venv .venv
. .venv/bin/activate
pip install pip-audit==2.10.1
sed -E 's/[[:space:]]*;.*$//' requirements.txt > /tmp/audit-requirements.txt
pip-audit -r /tmp/audit-requirements.txt --no-deps --disable-pip
```

To check what a fresh install of the SDK resolves, rather than the pinned set:

```bash
python -m venv /tmp/fresh
/tmp/fresh/bin/pip install .
/tmp/fresh/bin/pip freeze --exclude alfred-python > /tmp/fresh.txt
pip-audit -r /tmp/fresh.txt --no-deps --disable-pip
```

## When the audit fails

1. Read the report. It names the package, the installed version and the first fixed version.
2. Raise the pin in `requirements.txt` to the fixed release or later. Regenerate the file from a clean environment instead of editing it by hand: install the package and `build` in a fresh virtual environment, then run `pip freeze`.
3. If the vulnerable package is declared in `pyproject.toml`, raise its lower bound to the fixed release. If it is only transitive, add it as a security floor with a comment, unless a direct dependency already requires a patched version.
4. If the fixed release needs a newer Python than the SDK supports, raise `requires-python` and say so in the pull request. Do not ignore the advisory.
5. Run `python -m unittest` and `python -m build`, then open a pull request. The audit job must pass before merging.

## See also

- [Documentation index](README.md)
- [Getting started](getting-started.md)
- [Errors](errors.md)
