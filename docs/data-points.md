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

Returns a list of dictionaries, one per data point of the file's tag (the type is `DataPointValue`, see [Types](#types)). The SDK returns the rows exactly as Alfred sends them. Each has:

| Field | Type | Meaning |
| --- | --- | --- |
| `id` | string | The ID of this value. |
| `file_log_id` | string | The file the value belongs to. |
| `metadata_id` | string | The data point definition (stable for the tag). |
| `metadata_name` | string | The data point's display name. It can be renamed in the console. |
| `field_key` | string | A stable machine key for the data point. Use it, not the name, to look values up in your code. |
| `value` | string | The value, after any formatting configured for the data point. An empty string when nothing was extracted. |
| `classification_score` | number | How sure Alfred is of this value, from 0 to 1. See [Confidence](#confidence). |
| `extracted_value` | string | Optional. The extractor's original output, present only when formatting changed it. See [Formatting and normalisation](#formatting-and-normalisation). |
| `normalized_value` | string | Optional. The value after type normalisation, when one was computed. |
| `validation` | object or list | Optional. What the data point's validators found for this value. Present only when validation ran. See [Validation results](#validation-results). |

The first seven fields are always there. The three optional ones are left out when there is nothing to report, so read them with `.get()`.

`field_key`, `extracted_value`, `normalized_value` and `validation` are sent by Alfred 1.117.0 and later.

```python
values = client.data_points.get_values("559167cb-4c76-4e28-bf15-34cbf614119c")

by_key = {item["field_key"]: item["value"] for item in values}
print(by_key.get("total"))
```

Example response, with one value that has nothing more to report and one that was formatted and validated:

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
  },
  {
    "id": "6c1e2d63-4b5f-4b72-8e1f-1d8f1b0e22bb",
    "file_log_id": "559167cb-4c76-4e28-bf15-34cbf614119c",
    "metadata_id": "9d2a7f1e-8b3c-4c9f-a1b5-3a7e4d0f6b21",
    "metadata_name": "Tax ID",
    "field_key": "tax_id",
    "value": "402-1912052-0",
    "classification_score": 0.88,
    "extracted_value": "402 1912052 0",
    "normalized_value": "402-1912052-0",
    "validation": {
      "Status": "passed",
      "ExecutedAt": "2026-08-11T17:20:22.9238048Z",
      "DurationMs": 1843,
      "Results": [
        {
          "ValidatorId": "v_2yy94x",
          "Type": "required",
          "Passed": true,
          "Skipped": false,
          "Severity": 1,
          "BlocksCompletion": false,
          "DurationMs": 0
        },
        {
          "ValidatorId": "v_6snzhu",
          "Type": "custom",
          "Passed": true,
          "Skipped": false,
          "Severity": 1,
          "BlocksCompletion": false,
          "Message": "Validated against the registry.",
          "Metadata": { "matches": true, "api_code": 200 },
          "DurationMs": 1842,
          "Runtime": "python"
        }
      ],
      "Summary": { "Total": 2, "Passed": 2, "Failed": 0, "Skipped": 0, "HasBlockingFailures": false },
      "MustPassValidation": true
    }
  }
]
```

Values are strings, whatever the data point's type.

#### Confidence

`classification_score` is how sure Alfred's extractor was of this value, from 0 to 1. The name is historical: it is about the value, not about the file's classification, whose score is the `classification_score` of [`files.get`](files.md#get).

- Alfred 1.117.0 and later ask the extractor for its confidence on every value. Values extracted by an earlier version carry a placeholder instead, so do not compare old files with new ones.
- A score of `0` or `0.01` is that placeholder: the extractor reported no confidence. Read it as "unknown", not as "1% sure".
- The API returns the number as it is. What counts as too low for your process is yours to decide.

```python
REVIEW_BELOW = 0.8  # your own threshold

values = client.data_points.get_values("559167cb-4c76-4e28-bf15-34cbf614119c") or []
to_review = [
    item["field_key"]
    for item in values
    if item["classification_score"] < REVIEW_BELOW
]
print(to_review)
```

#### Formatting and normalisation

A data point can have formatters, rules that rewrite what the extractor read: change its case, trim spaces, replace text by a pattern, or run a script.

- `value` is the result after the formatters ran. This is the field to use.
- `extracted_value` is what the extractor read, and it is present only when a formatter changed it. When it is absent, `value` is what the extractor read.
- `normalized_value` is the value in the standard form of the data point's type, when Alfred computed one.

#### Validation results

A data point can also have validators, rules that check the value (required, a pattern, a check digit, a script of your own and so on). `validation` reports what they found for this value.

`validation` is absent when validation did not run for the value. That is not the same as passing: a value that passed has a `validation` block that says so.

Alfred returns the record as it stored it, and it stores it in one of two forms, depending on the pipeline that processed the file. Check which one you have before reading it.

**Object form: the whole run.** Its keys are PascalCase, unlike the rest of the row.

| Key | Type | Meaning |
| --- | --- | --- |
| `Status` | string | `passed`, `failed` or `skipped`. |
| `ExecutedAt` | string | When the validators ran (UTC). |
| `DurationMs` | number | How long the run took, in milliseconds. |
| `Results` | list | One entry per validator, in the order they ran (see below). |
| `Summary` | object | Counts: `Total`, `Passed`, `Failed`, `Skipped`, plus `HasBlockingFailures` and, when something failed, `HighestSeverityFailed`. |
| `Reason` | string | Why the run was skipped, when `Status` is `skipped`. |
| `MustPassValidation` | boolean | Whether the data point is set so that its value must pass validation. |

Each entry of `Results`:

| Key | Type | Meaning |
| --- | --- | --- |
| `ValidatorId` | string | The validator's ID in the data point's configuration. |
| `Type` | string | The kind of validator, such as `required`, `regex`, `checksum` or `custom`. |
| `Passed` | boolean | Whether the value passed. Only meaningful when `Skipped` is `false`. |
| `Skipped` | boolean | `true` when the validator did not run. That is neither a pass nor a failure. |
| `Severity` | number | `0` information, `1` warning, `2` error. |
| `BlocksCompletion` | boolean | Whether a failure of this validator keeps the file from completing. |
| `Message` | string | A message from the validator, when it has one. |
| `Metadata` | object | Details that depend on the validator, such as the values it compared. |
| `DurationMs` | number | How long this validator took, in milliseconds. |
| `ScriptName`, `Runtime` | string | For `custom` validators: the script that ran and its runtime. |

A key without a value is left out.

**List form: the validators' results on their own.** `validation` is then a list, with one entry per validator and snake_case keys. There is no overall status: the value failed if any entry failed.

| Key | Type | Meaning |
| --- | --- | --- |
| `validator_id` | string | The validator's ID in the data point's configuration. |
| `type` | string | The kind of validator, such as `required`, `regex`, `checksum` or `custom`. |
| `passed` | boolean | Whether the value passed. Ignore it when `skipped` is `true`. |
| `skipped` | boolean | Present and `true` when the validator did not run; `reason` says why. |
| `severity` | number or string | The severity configured for the validator. |
| `blocks_completion` | boolean | Whether a failure of this validator keeps the file from completing. |
| `message` | string or `null` | Why the value failed; `null` when it passed. |
| `metadata` | object or `null` | Details that depend on the validator; `null` when it passed. |

```json
[
  {
    "validator_id": "v_9k1q0d",
    "type": "checksum",
    "passed": false,
    "severity": "error",
    "blocks_completion": true,
    "message": "The check digit does not match.",
    "metadata": { "expected": "1", "actual": "0" }
  }
]
```

If the stored record cannot be read as JSON, Alfred sends it as the stored text, so `validation` can also be a string.

This function lists the validators that failed for one value, whichever form it has:

```python
def failed_validators(item):
    validation = item.get("validation")
    if isinstance(validation, dict):  # object form
        return [
            result
            for result in validation.get("Results", [])
            if not result.get("Skipped") and not result.get("Passed")
        ]
    if isinstance(validation, list):  # list form
        return [
            result
            for result in validation
            if not result.get("skipped") and not result.get("passed")
        ]
    return []  # validation did not run, or the record is not readable


values = client.data_points.get_values("559167cb-4c76-4e28-bf15-34cbf614119c") or []
for item in values:
    for result in failed_validators(item):
        print(item["field_key"], "failed", result.get("Type") or result.get("type"))
```

The rules themselves (which formatters and validators a data point has) are part of the data point's definition in Alfred, not of its values, and the SDK has no method for them.

#### Types

`alfred.rest.data_points` exports typed dictionaries for these rows, for editors and type checkers. They describe the data; the SDK does not convert or check it.

| Type | Describes |
| --- | --- |
| `DataPointValue` | One row of `get_values`. |
| `DataPointValidation` | The object form of `validation`. |
| `DataPointValidatorResult` | One entry of its `Results`. |
| `DataPointValidationSummary` | Its `Summary`. |
| `DataPointValidatorOutcome` | One entry of the list form of `validation`. |

```python
from typing import List, Optional

from alfred.rest.data_points import DataPointValue

values: Optional[List[DataPointValue]] = client.data_points.get_values(
    "559167cb-4c76-4e28-bf15-34cbf614119c"
)
```

#### When to call it, and what can go wrong

Call it after the file has finished processing. Values read earlier can be missing or incomplete. Check the file's `status` with [`files.get`](files.md#get), or wait for the job (see [jobs.md](jobs.md) or [real-time events](realtime.md)). A file that Alfred holds for human review (status `confirmation_required`) has values that a reviewer may still change.

Situations to handle (see [errors.md](errors.md)):

- `404`: the file does not exist, or its tag has no data points to extract (the body says so), or the lookup failed. Treat it as "no values for this file".
- `401`: your credentials are not allowed to read this file.
- No content (`204`): the server can answer with no body when it has nothing for the file, and `get_values` then returns `None` instead of a list. Treat it as "no values for this file" (see [errors.md](errors.md#responses-that-cannot-be-parsed)).

## Connections to other domains

- The file ID comes from [`files.upload_file`](files.md#upload_file) (it returns `file_id`), or from the files of a job ([`jobs`](jobs.md)).
- The data points of a file depend on the tag shown in [`files.get`](files.md#get) (`tag_id`, `tag_name`). A file with no tag has no data points.
- If Alfred splits a document into several files, each page or part is a separate file with its own values. See `parent_id` in [`files.get`](files.md#get).

## See also

- [Files](files.md): file details, including the tag and status
- [Jobs](jobs.md): find a job's files
- [Real-time events](realtime.md): be told when a file is done (`alfred_event_file_done` on the file event stream)
- [Error handling](errors.md)
