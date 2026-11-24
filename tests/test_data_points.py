import copy
import unittest

import alfred.rest.data_points as data_points_package
from alfred.rest.data_points import (
    DataPointsFactory,
    DataPointValidation,
    DataPointValidationSummary,
    DataPointValidatorOutcome,
    DataPointValidatorResult,
    DataPointValue,
)
from alfred.rest.data_points.v1 import DataPoints

# A row of GET /api/values/file/{id} as Alfred 1.117.0 and later sends it, with
# the validation run in its object form (PascalCase, as stored).
VALUE_WITH_VALIDATION_OBJECT = {
    "id": "5b0d1c52-3a4e-4a61-9d0e-0c7e0a9d11aa",
    "file_log_id": "559167cb-4c76-4e28-bf15-34cbf614119c",
    "metadata_id": "8c1f6e0d-7a2b-4b8e-b0a4-2f6d3c9e5a10",
    "metadata_name": "Total",
    "field_key": "total",
    "value": "100.00",
    "classification_score": 0.93,
    "extracted_value": "RD$ 100",
    "normalized_value": "100.00",
    "validation": {
        "Status": "passed",
        "ExecutedAt": "2026-08-11T17:20:22.9238048Z",
        "DurationMs": 1843,
        "Results": [
            {
                "ValidatorId": "v_2yy94x",
                "Type": "required",
                "Passed": True,
                "Skipped": False,
                "Severity": 1,
                "BlocksCompletion": False,
                "DurationMs": 0,
            },
            {
                "ValidatorId": "v_6snzhu",
                "Type": "custom",
                "Passed": True,
                "Skipped": False,
                "Severity": 1,
                "BlocksCompletion": False,
                "Message": "Validated against the registry.",
                "Metadata": {"matches": True, "api_code": 200},
                "DurationMs": 1842,
                "Runtime": "python",
            },
        ],
        "Summary": {"Total": 2, "Passed": 2, "Failed": 0, "Skipped": 0, "HasBlockingFailures": False},
        "MustPassValidation": True,
    },
}

# The same block in its list form: the per-validator results themselves.
VALUE_WITH_VALIDATION_LIST = {
    "id": "6c1e2d63-4b5f-4b72-8e1f-1d8f1b0e22bb",
    "file_log_id": "559167cb-4c76-4e28-bf15-34cbf614119c",
    "metadata_id": "9d2a7f1e-8b3c-4c9f-a1b5-3a7e4d0f6b21",
    "metadata_name": "Tax ID",
    "field_key": "tax_id",
    "value": "402-1912052-0",
    "classification_score": 0.42,
    "validation": [
        {
            "validator_id": "v_2yy94x",
            "type": "required",
            "passed": True,
            "severity": "warning",
            "blocks_completion": False,
            "message": None,
            "metadata": None,
        },
        {
            "validator_id": "v_9k1q0d",
            "type": "checksum",
            "passed": False,
            "severity": "error",
            "blocks_completion": True,
            "message": "The check digit does not match.",
            "metadata": {"expected": "1", "actual": "0"},
        },
        {
            "validator_id": "v_6snzhu",
            "type": "custom",
            "passed": True,
            "severity": "warning",
            "blocks_completion": False,
            "message": None,
            "metadata": None,
            "skipped": True,
            "reason": "custom validator did not run",
        },
    ],
}

# A value with nothing more to report: no formatting change, no validation.
PLAIN_VALUE = {
    "id": "7d2f3e74-5c6a-4c83-9f2a-2e9a2c1f33cc",
    "file_log_id": "559167cb-4c76-4e28-bf15-34cbf614119c",
    "metadata_id": "ae3b8a2f-9c4d-4daa-b2c6-4b8f5e1a7c32",
    "metadata_name": "Customer",
    "field_key": "customer",
    "value": "",
    "classification_score": 0.0,
}


class RecordingHttpClient:
    """
    Records every get/post call as (uri, params, data, files, headers)
    and answers with a scripted (parsed, response) tuple.
    """

    def __init__(self, get_result=(None, None), post_result=(None, None)):
        self.get_result = get_result
        self.post_result = post_result
        self.get_calls = []
        self.post_calls = []

    def get(self, uri, params=None, data=None, headers=None, files=None, timeout=None):
        self.get_calls.append((uri, params, data, files, headers))
        return self.get_result

    def post(self, uri, params=None, data=None, headers=None, files=None, timeout=None):
        self.post_calls.append((uri, params, data, files, headers))
        return self.post_result


class TestDataPoints(unittest.TestCase):
    def test_get_values_requests_values_route_for_file(self):
        client = RecordingHttpClient(get_result=([], None))

        DataPoints(client).get_values("f1")

        self.assertEqual(client.get_calls, [("/api/values/file/f1", None, None, None, None)])
        self.assertEqual(client.post_calls, [])

    def test_get_values_returns_parsed_body(self):
        values = [{"name": "invoice_number", "value": "A-1"}]
        client = RecordingHttpClient(get_result=(values, None))

        result = DataPoints(client).get_values("f1")

        self.assertEqual(result, values)

    def test_get_values_returns_the_list_object_the_http_client_parsed(self):
        values = [dict(PLAIN_VALUE)]
        client = RecordingHttpClient(get_result=(values, None))

        result = DataPoints(client).get_values("f1")

        self.assertIs(result, values)

    def test_get_values_keeps_confidence_and_the_fields_added_in_alfred_1_117(self):
        sent = [VALUE_WITH_VALIDATION_OBJECT, VALUE_WITH_VALIDATION_LIST, PLAIN_VALUE]
        client = RecordingHttpClient(get_result=(copy.deepcopy(sent), None))

        result = DataPoints(client).get_values("f1")

        self.assertEqual(result, sent)
        self.assertEqual(result[0]["classification_score"], 0.93)
        self.assertEqual(result[0]["field_key"], "total")
        self.assertEqual(result[0]["extracted_value"], "RD$ 100")
        self.assertEqual(result[0]["normalized_value"], "100.00")

    def test_get_values_keeps_the_object_form_of_validation_with_its_pascal_case_keys(self):
        client = RecordingHttpClient(
            get_result=([copy.deepcopy(VALUE_WITH_VALIDATION_OBJECT)], None)
        )

        validation = DataPoints(client).get_values("f1")[0]["validation"]

        self.assertEqual(validation, VALUE_WITH_VALIDATION_OBJECT["validation"])
        self.assertEqual(validation["Status"], "passed")
        self.assertEqual(validation["Results"][1]["Metadata"], {"matches": True, "api_code": 200})
        self.assertEqual(validation["Summary"]["Failed"], 0)

    def test_get_values_keeps_the_list_form_of_validation_with_its_snake_case_keys(self):
        client = RecordingHttpClient(
            get_result=([copy.deepcopy(VALUE_WITH_VALIDATION_LIST)], None)
        )

        validation = DataPoints(client).get_values("f1")[0]["validation"]

        self.assertEqual(validation, VALUE_WITH_VALIDATION_LIST["validation"])
        self.assertEqual([entry["passed"] for entry in validation], [True, False, True])
        self.assertTrue(validation[2]["skipped"])

    def test_get_values_keeps_a_validation_record_sent_as_text(self):
        value = dict(PLAIN_VALUE, validation="{not json")
        client = RecordingHttpClient(get_result=([value], None))

        result = DataPoints(client).get_values("f1")

        self.assertEqual(result[0]["validation"], "{not json")

    def test_get_values_does_not_add_the_optional_keys_alfred_left_out(self):
        client = RecordingHttpClient(get_result=([dict(PLAIN_VALUE)], None))

        result = DataPoints(client).get_values("f1")

        self.assertEqual(set(result[0]), set(PLAIN_VALUE))
        for key in ("extracted_value", "normalized_value", "validation"):
            self.assertNotIn(key, result[0])

    def test_get_values_returns_none_when_the_api_answers_with_no_content(self):
        client = RecordingHttpClient(get_result=(None, None))

        self.assertIsNone(DataPoints(client).get_values("f1"))


class TestDataPointTypes(unittest.TestCase):
    def required_and_optional(self, typed_dict):
        return set(typed_dict.__required_keys__), set(typed_dict.__optional_keys__)

    def test_value_requires_the_keys_alfred_always_sends(self):
        required, optional = self.required_and_optional(DataPointValue)

        self.assertEqual(
            required,
            {
                "id",
                "file_log_id",
                "metadata_id",
                "metadata_name",
                "field_key",
                "value",
                "classification_score",
            },
        )
        self.assertEqual(optional, {"extracted_value", "normalized_value", "validation"})

    def test_sample_rows_have_every_required_key_and_no_unknown_one(self):
        required, optional = self.required_and_optional(DataPointValue)

        for row in (VALUE_WITH_VALIDATION_OBJECT, VALUE_WITH_VALIDATION_LIST, PLAIN_VALUE):
            with self.subTest(field_key=row["field_key"]):
                self.assertTrue(required <= set(row))
                self.assertTrue(set(row) <= required | optional)

    def test_object_form_of_validation_is_typed_with_the_keys_alfred_stores(self):
        cases = (
            (
                DataPointValidation,
                {"Status", "ExecutedAt", "DurationMs", "Results", "Summary", "Reason", "MustPassValidation"},
            ),
            (
                DataPointValidatorResult,
                {
                    "ValidatorId",
                    "Type",
                    "Passed",
                    "Skipped",
                    "Severity",
                    "BlocksCompletion",
                    "Message",
                    "Metadata",
                    "DurationMs",
                    "ScriptName",
                    "Runtime",
                },
            ),
            (
                DataPointValidationSummary,
                {"Total", "Passed", "Failed", "Skipped", "HighestSeverityFailed", "HasBlockingFailures"},
            ),
        )
        for typed_dict, keys in cases:
            with self.subTest(typed_dict=typed_dict.__name__):
                required, optional = self.required_and_optional(typed_dict)
                self.assertEqual(required, set())
                self.assertEqual(optional, keys)

    def test_list_form_of_validation_is_typed_with_snake_case_keys(self):
        required, optional = self.required_and_optional(DataPointValidatorOutcome)

        self.assertEqual(required, set())
        self.assertEqual(
            optional,
            {
                "validator_id",
                "type",
                "passed",
                "skipped",
                "severity",
                "blocks_completion",
                "message",
                "metadata",
                "reason",
            },
        )

    def test_sample_validation_blocks_use_only_typed_keys(self):
        run = VALUE_WITH_VALIDATION_OBJECT["validation"]
        self.assertTrue(set(run) <= set(DataPointValidation.__optional_keys__))
        self.assertTrue(set(run["Summary"]) <= set(DataPointValidationSummary.__optional_keys__))
        for entry in run["Results"]:
            self.assertTrue(set(entry) <= set(DataPointValidatorResult.__optional_keys__))
        for entry in VALUE_WITH_VALIDATION_LIST["validation"]:
            self.assertTrue(set(entry) <= set(DataPointValidatorOutcome.__optional_keys__))

    def test_package_exports_the_value_types_and_nothing_from_typing(self):
        self.assertEqual(
            sorted(data_points_package.typed.__all__),
            [
                "DataPointValidation",
                "DataPointValidationSummary",
                "DataPointValidatorOutcome",
                "DataPointValidatorResult",
                "DataPointValue",
            ],
        )
        for name in data_points_package.typed.__all__:
            self.assertTrue(hasattr(data_points_package, name), name)
        self.assertFalse(hasattr(data_points_package, "TypedDict"))


class TestDataPointsFactory(unittest.TestCase):
    def test_create_version_1_returns_data_points_bound_to_http_client(self):
        client = RecordingHttpClient()

        result = DataPointsFactory.create(1, client)

        self.assertIsInstance(result, DataPoints)
        self.assertIs(result.http_client, client)

    def test_create_unsupported_version_raises_plain_exception(self):
        with self.assertRaises(Exception) as ctx:
            DataPointsFactory.create(2, RecordingHttpClient())

        self.assertIs(type(ctx.exception), Exception)
        self.assertEqual(str(ctx.exception), "Unsupported version for the specified domain.")


if __name__ == "__main__":
    unittest.main()
