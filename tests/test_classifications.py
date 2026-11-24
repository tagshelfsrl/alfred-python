import io
import json
import os
import tempfile
import unittest
import uuid
from unittest import mock

from alfred.base.exceptions import AlfredMissingArgument
from alfred.rest import AlfredClient
from alfred.rest.classifications import (
    ClassificationStatus,
    ClassificationsBase,
    ClassificationsFactory,
)
from alfred.rest.classifications.v1 import Classifications

JOB_ID = "6f1b2c3d-4e5f-4a6b-8c7d-9e0f1a2b3c4d"
TAGS = [
    {"name": "Invoice", "description": "A commercial invoice.", "threshold": 0.6},
    {"name": "Receipt", "description": "A point-of-sale receipt."},
]


class RecordingHttpClient:
    """Records every call and returns scripted (parsed, response) tuples."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def _record(self, method, uri, params, data, files):
        self.calls.append(
            {
                "method": method,
                "uri": uri,
                "params": params,
                "data": data,
                "files": files,
            }
        )
        return self.responses.pop(0) if self.responses else (None, None)

    def post(self, uri, params=None, data=None, headers=None, files=None, **_kw):
        return self._record("POST", uri, params, data, files)

    def get(self, uri, params=None, data=None, headers=None, files=None, **_kw):
        return self._record("GET", uri, params, data, files)


def queued():
    return {
        "id": JOB_ID,
        "file_id": "5a6b7c8d-9e0f-4a1b-8c2d-3e4f5a6b7c8d",
        "status": "queued",
        "created_at": "2026-11-12T13:00:00.123Z",
        "correlation_id": "order-42",
        "text_truncated": False,
    }


def domain(*responses):
    http = RecordingHttpClient(*responses)
    return Classifications(http), http


class TestCreate(unittest.TestCase):
    def test_posts_json_body_unchanged_and_returns_answer(self):
        payload = {
            "tags": TAGS,
            "text": "INVOICE 0001",
            "file_name": "invoice.txt",
            "correlation_id": "order-42",
        }
        answer = queued()
        classifications, http = domain((answer, object()))

        result = classifications.create(payload)

        self.assertIs(result, answer)
        self.assertEqual(
            http.calls,
            [
                {
                    "method": "POST",
                    "uri": "/api/classify",
                    "params": None,
                    "data": payload,
                    "files": None,
                }
            ],
        )

    def test_optional_keys_are_not_added(self):
        payload = {"tags": TAGS, "text": "hello"}
        classifications, http = domain((queued(), None))

        classifications.create(payload)

        self.assertEqual(http.calls[0]["data"], {"tags": TAGS, "text": "hello"})
        self.assertNotIn("file_name", http.calls[0]["data"])
        self.assertNotIn("correlation_id", http.calls[0]["data"])

    def test_each_call_sends_one_request(self):
        classifications, http = domain((queued(), None), (queued(), None))
        classifications.create({"tags": TAGS, "text": "a"})
        classifications.create({"tags": TAGS, "text": "a"})
        self.assertEqual(len(http.calls), 2)


@mock.patch("alfred.rest.classifications.v1.magic")
class TestCreateFromFile(unittest.TestCase):
    def test_bytesio_with_filename(self, magic):
        magic.from_buffer.return_value = "application/pdf"
        file = io.BytesIO(b"%PDF-1.7 content")
        answer = queued()
        classifications, http = domain((answer, None))

        result = classifications.create_from_file(
            {
                "file": file,
                "tags": TAGS,
                "filename": "invoice.pdf",
                "correlation_id": "trial-1",
            }
        )

        self.assertIs(result, answer)
        call = http.calls[0]
        self.assertEqual(call["method"], "POST")
        self.assertEqual(call["uri"], "/api/classify")
        self.assertIsNone(call["params"])
        self.assertEqual(
            set(call["data"]), {"tags", "correlation_id"}
        )
        self.assertEqual(call["data"]["correlation_id"], "trial-1")
        self.assertIsInstance(call["data"]["tags"], str)
        self.assertEqual(json.loads(call["data"]["tags"]), TAGS)
        self.assertEqual(
            call["files"], {"file": ("invoice.pdf", file, "application/pdf")}
        )

    def test_correlation_id_omitted_when_not_given_or_blank(self, magic):
        magic.from_buffer.return_value = "text/plain"
        for extra in ({}, {"correlation_id": ""}, {"correlation_id": None}):
            classifications, http = domain((queued(), None))
            payload = {"file": io.BytesIO(b"x"), "tags": TAGS, "filename": "a.txt"}
            payload.update(extra)
            classifications.create_from_file(payload)
            self.assertEqual(set(http.calls[0]["data"]), {"tags"})

    def test_real_file_opened_in_binary_mode_uses_its_basename(self, magic):
        magic.from_buffer.return_value = "image/png"
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "scan.png")
            with open(path, "wb") as handle:
                handle.write(b"\x89PNG data")
            classifications, http = domain((queued(), None))
            with open(path, "rb") as handle:
                classifications.create_from_file({"file": handle, "tags": TAGS})
                sent = http.calls[0]["files"]["file"]
                self.assertEqual(sent[0], "scan.png")
                self.assertIs(sent[1], handle)
                self.assertEqual(sent[2], "image/png")
                self.assertEqual(handle.tell(), 0)

    def test_explicit_filename_wins_over_opened_file_name(self, magic):
        magic.from_buffer.return_value = "application/pdf"
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "tmp12345")
            with open(path, "wb") as handle:
                handle.write(b"%PDF")
            classifications, http = domain((queued(), None))
            with open(path, "rb") as handle:
                classifications.create_from_file(
                    {"file": handle, "tags": TAGS, "filename": "contract.pdf"}
                )
            self.assertEqual(http.calls[0]["files"]["file"][0], "contract.pdf")

    def test_missing_filename_raises_before_any_request(self, magic):
        for payload_extra in ({}, {"filename": ""}, {"filename": None}):
            classifications, http = domain()
            payload = {"file": io.BytesIO(b"x"), "tags": TAGS}
            payload.update(payload_extra)
            with self.assertRaises(AlfredMissingArgument):
                classifications.create_from_file(payload)
            self.assertEqual(http.calls, [])

    def test_file_with_non_text_name_needs_filename(self, magic):
        class Numbered(io.BytesIO):
            name = 7  # like a file object opened from a descriptor

        classifications, http = domain()
        with self.assertRaises(AlfredMissingArgument):
            classifications.create_from_file({"file": Numbered(b"x"), "tags": TAGS})
        self.assertEqual(http.calls, [])

    def test_missing_file_raises_before_any_request(self, magic):
        for payload in ({"tags": TAGS, "filename": "a.pdf"}, {"file": None, "tags": TAGS}):
            classifications, http = domain()
            with self.assertRaises(AlfredMissingArgument):
                classifications.create_from_file(payload)
            self.assertEqual(http.calls, [])

    def test_mime_sniffs_first_1024_bytes_and_position_is_reset(self, magic):
        magic.from_buffer.return_value = "application/pdf"
        content = b"A" * 5000
        file = io.BytesIO(content)
        file.seek(3000)  # a caller that already read part of it
        classifications, _ = domain((queued(), None))

        classifications.create_from_file(
            {"file": file, "tags": TAGS, "filename": "a.pdf"}
        )

        magic.from_buffer.assert_called_once_with(content[:1024], mime=True)
        self.assertEqual(file.tell(), 0)
        self.assertEqual(file.read(), content)

    def test_detected_mime_type_is_the_one_sent(self, magic):
        magic.from_buffer.return_value = "image/webp"
        classifications, http = domain((queued(), None))
        classifications.create_from_file(
            {"file": io.BytesIO(b"RIFF"), "tags": TAGS, "filename": "a.webp"}
        )
        self.assertEqual(http.calls[0]["files"]["file"][2], "image/webp")

    def test_tags_json_round_trips_non_ascii(self, magic):
        magic.from_buffer.return_value = "text/plain"
        tags = [
            {"name": "Factura", "description": "Documento de cobro, año 2026."},
            {"name": "Recibo", "description": "Comprobante — pago", "threshold": 0},
        ]
        classifications, http = domain((queued(), None))
        classifications.create_from_file(
            {"file": io.BytesIO(b"x"), "tags": tags, "filename": "a.txt"}
        )
        self.assertEqual(json.loads(http.calls[0]["data"]["tags"]), tags)


class TestGet(unittest.TestCase):
    def test_get_with_str_id(self):
        answer = queued()
        classifications, http = domain((answer, None))

        result = classifications.get(JOB_ID)

        self.assertIs(result, answer)
        self.assertEqual(
            http.calls,
            [
                {
                    "method": "GET",
                    "uri": f"/api/classify/{JOB_ID}",
                    "params": None,
                    "data": None,
                    "files": None,
                }
            ],
        )

    def test_get_with_uuid_id(self):
        classifications, http = domain(({}, None))
        classifications.get(uuid.UUID(JOB_ID))
        self.assertEqual(http.calls[0]["uri"], f"/api/classify/{JOB_ID}")

    def test_blank_or_missing_id_raises_before_any_request(self):
        for value in (None, "", "   ", "\t\n"):
            classifications, http = domain()
            with self.assertRaises(ValueError):
                classifications.get(value)
            self.assertEqual(http.calls, [])

    def test_wrong_type_raises_before_any_request(self):
        for value in (123, 1.5, b"abc", ["a"], {"id": "a"}):
            classifications, http = domain()
            with self.assertRaises(TypeError):
                classifications.get(value)
            self.assertEqual(http.calls, [])

    def test_id_is_url_quoted(self):
        classifications, http = domain(({}, None))
        classifications.get("../jobs/x?y=1#z a")
        self.assertEqual(
            http.calls[0]["uri"], "/api/classify/..%2Fjobs%2Fx%3Fy%3D1%23z%20a"
        )

    def test_answers_are_returned_unchanged(self):
        answers = {
            "queued": queued(),
            "completed": {
                **queued(),
                "status": "completed",
                "completed_at": "2026-11-12T13:00:05.410Z",
                "result": {
                    "class": "Invoice",
                    "score": 0.91,
                    "below_threshold": False,
                    "predictions": [
                        {"class": "Invoice", "score": 0.91},
                        {"class": "Receipt", "score": 0.06},
                    ],
                    "model": "zero",
                    "reasoning": "Seller, buyer and a total.",
                },
                "input": {"pages": 2, "classified_pages": 2, "mode": "native_text"},
            },
            "no class": {
                **queued(),
                "status": "completed",
                "completed_at": "2026-11-12T13:00:05.410Z",
                "result": {
                    "class": "",
                    "score": 0,
                    "below_threshold": True,
                    "predictions": [],
                    "model": "zero",
                    "reason": "no_match",
                    "answered": "Memo",
                },
            },
            "failed": {
                **queued(),
                "status": "failed",
                "completed_at": "2026-11-12T13:00:05.410Z",
                "error": {"code": "classification_failed", "message": "boom"},
            },
        }
        for name, answer in answers.items():
            with self.subTest(name):
                snapshot = json.loads(json.dumps(answer))
                classifications, _ = domain((answer, None))
                result = classifications.get(JOB_ID)
                self.assertIs(result, answer)
                self.assertEqual(result, snapshot)

    def test_errors_propagate(self):
        class Boom(Exception):
            pass

        class Failing(RecordingHttpClient):
            def get(self, *_a, **_k):
                raise Boom()

            def post(self, *_a, **_k):
                raise Boom()

        classifications = Classifications(Failing())
        with self.assertRaises(Boom):
            classifications.get(JOB_ID)
        with self.assertRaises(Boom):
            classifications.create({"tags": TAGS, "text": "x"})
        with mock.patch("alfred.rest.classifications.v1.magic") as magic:
            magic.from_buffer.return_value = "text/plain"
            with self.assertRaises(Boom):
                classifications.create_from_file(
                    {"file": io.BytesIO(b"x"), "tags": TAGS, "filename": "a.txt"}
                )


class TestStatus(unittest.TestCase):
    def test_values(self):
        self.assertEqual(
            [s.value for s in ClassificationStatus], ["queued", "completed", "failed"]
        )
        self.assertEqual(ClassificationStatus("completed"), "completed")


class TestPayloadTypes(unittest.TestCase):
    """The payload types say which keys the API requires, so a type checker
    catches a missing one before the API answers 400."""

    def required_and_optional(self, typed_dict):
        required = getattr(typed_dict, "__required_keys__", None)
        if required is None:
            self.skipTest("TypedDict key totality is introspectable from Python 3.9")
        return set(required), set(typed_dict.__optional_keys__)

    def test_criterion_requires_name_and_description(self):
        from alfred.rest.classifications import ClassificationCriterion

        required, optional = self.required_and_optional(ClassificationCriterion)
        self.assertEqual(required, {"name", "description"})
        self.assertEqual(optional, {"threshold"})

    def test_text_payload_requires_tags_and_text(self):
        from alfred.rest.classifications import CreateClassificationPayload

        required, optional = self.required_and_optional(CreateClassificationPayload)
        self.assertEqual(required, {"tags", "text"})
        self.assertEqual(optional, {"file_name", "correlation_id"})

    def test_file_payload_requires_file_and_tags(self):
        from alfred.rest.classifications import CreateClassificationFilePayload

        required, optional = self.required_and_optional(CreateClassificationFilePayload)
        self.assertEqual(required, {"file", "tags"})
        self.assertEqual(optional, {"filename", "correlation_id"})


class TestResponseTypes(TestPayloadTypes):
    """The answer types say which keys the API always sends."""

    test_criterion_requires_name_and_description = None
    test_text_payload_requires_tags_and_text = None
    test_file_payload_requires_file_and_tags = None

    def test_answer_always_has_its_identity_and_status(self):
        from alfred.rest.classifications import ClassificationResponse

        required, optional = self.required_and_optional(ClassificationResponse)
        self.assertEqual(
            required,
            {"id", "file_id", "status", "created_at", "correlation_id", "text_truncated"},
        )
        self.assertEqual(optional, {"completed_at", "result", "error", "input"})

    def test_result_always_has_the_decision(self):
        from alfred.rest.classifications import ClassificationResult

        required, optional = self.required_and_optional(ClassificationResult)
        self.assertEqual(
            required, {"class", "score", "below_threshold", "predictions", "model"}
        )
        self.assertEqual(optional, {"reasoning", "reason", "answered"})

    def test_prediction_and_failure_have_no_optional_keys(self):
        from alfred.rest.classifications import ClassificationFailure, ClassificationPrediction

        for typed_dict, keys in (
            (ClassificationPrediction, {"class", "score"}),
            (ClassificationFailure, {"code", "message"}),
        ):
            with self.subTest(typed_dict=typed_dict.__name__):
                required, optional = self.required_and_optional(typed_dict)
                self.assertEqual(required, keys)
                self.assertEqual(optional, set())

    def test_input_block_keys_are_all_optional(self):
        from alfred.rest.classifications import ClassificationInput

        required, _ = self.required_and_optional(ClassificationInput)
        self.assertEqual(required, set())


class TestFactoryAndClient(unittest.TestCase):
    def test_factory_version_1(self):
        http = RecordingHttpClient()
        instance = ClassificationsFactory.create(1, http)
        self.assertIsInstance(instance, Classifications)
        self.assertIsInstance(instance, ClassificationsBase)
        self.assertIs(instance.http_client, http)

    def test_factory_unsupported_version(self):
        for version in (0, 2, None):
            with self.assertRaises(ValueError) as ctx:
                ClassificationsFactory.create(version, RecordingHttpClient())
            self.assertIn("Unsupported version", str(ctx.exception))

    def test_client_property_is_bound_and_cached(self):
        http = RecordingHttpClient()
        client = AlfredClient(
            config={"base_url": "https://example.test", "version": 1},
            auth_config={"api_key": "k"},
            http_client=http,
        )
        first = client.classifications
        self.assertIsInstance(first, Classifications)
        self.assertIs(first.http_client, http)
        self.assertIs(client.classifications, first)

    def test_client_with_unsupported_version(self):
        client = AlfredClient(
            config={"base_url": "https://example.test", "version": 9},
            auth_config={"api_key": "k"},
            http_client=RecordingHttpClient(),
        )
        with self.assertRaises(ValueError):
            client.classifications


if __name__ == "__main__":
    unittest.main()
