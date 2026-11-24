import datetime
import unittest
import uuid

from alfred.rest.jobs import JobsFactory, JobsBase, JobView, V1
from alfred.rest.jobs.v1 import Jobs

JOB_ID = "11111111-2222-3333-4444-555555555555"


class RecordingHttpClient:
    """Records each call and returns scripted (parsed, response) tuples."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def _call(self, method, uri, params=None, data=None):
        self.calls.append(
            {"method": method, "uri": uri, "params": params, "data": data}
        )
        if self.responses:
            return self.responses.pop(0), None
        return None, None

    def get(self, uri, params=None, data=None, **_kwargs):
        return self._call("GET", uri, params, data)

    def post(self, uri, params=None, data=None, **_kwargs):
        return self._call("POST", uri, params, data)

    @property
    def last(self):
        return self.calls[-1]


def make(*responses):
    client = RecordingHttpClient(*responses)
    return Jobs(client), client


class TestFactory(unittest.TestCase):
    def test_version_one_returns_jobs(self):
        client = RecordingHttpClient()
        jobs = JobsFactory.create(1, client)
        self.assertIsInstance(jobs, V1)
        self.assertIsInstance(jobs, JobsBase)
        self.assertIs(jobs.http_client, client)

    def test_unsupported_version(self):
        with self.assertRaises(ValueError) as ctx:
            JobsFactory.create(2, RecordingHttpClient())
        self.assertIn("Unsupported version: 2", str(ctx.exception))

    def test_abstract_methods_have_docs_and_cannot_be_instantiated(self):
        with self.assertRaises(TypeError):
            JobsBase()
        # Calling the abstract bodies through a subclass reaches the docstrings.
        names = ["create", "get", "get_all", "cancel", "restart", "check_sources"]

        class Impl(JobsBase):
            pass

        for name in names:
            setattr(Impl, name, getattr(JobsBase, name))
        Impl.__abstractmethods__ = frozenset()
        impl = Impl()
        self.assertIsNone(impl.create({}))
        self.assertIsNone(impl.get("x"))
        self.assertIsNone(impl.get_all())
        self.assertIsNone(impl.cancel("x"))
        self.assertIsNone(impl.restart("x"))
        self.assertIsNone(impl.check_sources("x"))

    def test_job_view_values(self):
        self.assertEqual(JobView.SUMMARY.value, "summary")
        self.assertEqual(JobView.FULL.value, "full")


class TestCreate(unittest.TestCase):
    def test_create_posts_payload_and_returns_response(self):
        jobs, client = make({"job_id": "j", "correlation_id": "erp:1"})
        payload = {"channel": "api", "correlation_id": "erp:1"}
        result = jobs.create(payload)
        self.assertEqual(result, {"job_id": "j", "correlation_id": "erp:1"})
        self.assertEqual(
            client.last,
            {
                "method": "POST",
                "uri": "/api/job/create",
                "params": None,
                "data": payload,
            },
        )

    def test_create_response_is_not_normalized(self):
        jobs, _ = make({"job_id": "j", "metadata": "x"})
        self.assertEqual(jobs.create({}), {"job_id": "j", "metadata": "x"})


class TestGetRequest(unittest.TestCase):
    def test_default_sends_no_params(self):
        jobs, client = make({"id": JOB_ID})
        jobs.get(JOB_ID)
        self.assertEqual(client.last["method"], "GET")
        self.assertEqual(client.last["uri"], f"/api/job/detail/{JOB_ID}")
        self.assertEqual(client.last["params"], {})
        self.assertIsNone(client.last["data"])

    def test_view_enum_and_string(self):
        for view, expected in [
            (JobView.FULL, "full"),
            (JobView.SUMMARY, "summary"),
            ("full", "full"),
            ("FULL", "FULL"),
            ("bogus", "bogus"),
        ]:
            jobs, client = make({"id": JOB_ID})
            jobs.get(JOB_ID, view)
            self.assertEqual(client.last["params"], {"view": expected})

    def test_view_keyword(self):
        jobs, client = make({"id": JOB_ID})
        jobs.get(JOB_ID, view=JobView.FULL)
        self.assertEqual(client.last["params"], {"view": "full"})

    def test_exclude_forms(self):
        cases = [
            ("files,metadata", "files,metadata"),
            ("files, metadata ,", "files,metadata"),
            (["files", "fileUrls"], "files,fileUrls"),
            (("errorMessages",), "errorMessages"),
            ({"files"}, "files"),
            (iter(["files", " ", "metadata"]), "files,metadata"),
        ]
        for exclude, expected in cases:
            jobs, client = make({"id": JOB_ID})
            jobs.get(JOB_ID, "full", exclude)
            self.assertEqual(client.last["params"]["exclude"], expected)

    def test_empty_exclude_is_not_sent(self):
        for exclude in (None, "", " , ", [], [""]):
            jobs, client = make({"id": JOB_ID})
            jobs.get(JOB_ID, "full", exclude)
            self.assertEqual(client.last["params"], {"view": "full"})

    def test_exclude_without_view_is_still_sent(self):
        jobs, client = make({"id": JOB_ID})
        jobs.get(JOB_ID, exclude="files")
        self.assertEqual(client.last["params"], {"exclude": "files"})

    def test_uuid_job_id(self):
        jobs, client = make({"id": JOB_ID})
        jobs.get(uuid.UUID(JOB_ID))
        self.assertEqual(client.last["uri"], f"/api/job/detail/{JOB_ID}")

    def test_job_id_is_stripped_and_quoted(self):
        jobs, client = make({})
        jobs.get("  a/b c?d#e%f  ")
        self.assertEqual(client.last["uri"], "/api/job/detail/a%2Fb%20c%3Fd%23e%25f")

    def test_missing_or_blank_job_id_raises_before_any_request(self):
        for bad in (None, "", "   "):
            jobs, client = make()
            with self.assertRaises(ValueError):
                jobs.get(bad)
            self.assertEqual(client.calls, [])

    def test_wrong_type_job_id(self):
        jobs, client = make()
        with self.assertRaises(TypeError):
            jobs.get(123)
        self.assertEqual(client.calls, [])


class TestGetMetadata(unittest.TestCase):
    def test_summary_gets_no_invented_metadata(self):
        summary = {"id": JOB_ID, "stage": "in_progress"}
        for view in (None, "summary", JobView.SUMMARY):
            jobs, _ = make(dict(summary))
            self.assertEqual(jobs.get(JOB_ID, view), summary)
            self.assertNotIn("metadata", jobs.get(JOB_ID, view) or {})

    def test_summary_response_object_is_returned_unchanged(self):
        summary = {"id": JOB_ID}
        jobs, _ = make(summary)
        self.assertIs(jobs.get(JOB_ID), summary)

    def test_full_view_parses_metadata_string(self):
        jobs, _ = make({"id": JOB_ID, "metadata": '{"a": "b", "l": [1, 2]}'})
        self.assertEqual(
            jobs.get(JOB_ID, "full")["metadata"], {"a": "b", "l": [1, 2]}
        )

    def test_full_view_without_metadata_gets_empty_dict(self):
        for view in ("full", "FULL", " Full ", JobView.FULL):
            jobs, _ = make({"id": JOB_ID})
            self.assertEqual(jobs.get(JOB_ID, view), {"id": JOB_ID, "metadata": {}})

    def test_full_view_with_other_exclusions_still_guarantees_metadata(self):
        jobs, _ = make({"id": JOB_ID})
        result = jobs.get(JOB_ID, "full", "files,fileUrls")
        self.assertEqual(result["metadata"], {})

    def test_excluded_metadata_is_not_invented(self):
        for exclude in ("metadata", ["Files", " METADATA "], "files,metadata"):
            jobs, _ = make({"id": JOB_ID})
            result = jobs.get(JOB_ID, "full", exclude)
            self.assertEqual(result, {"id": JOB_ID})

    def test_excluded_metadata_sent_as_empty_string_becomes_dict(self):
        # The server sends "" for a null string; the existing rule applies.
        jobs, _ = make({"id": JOB_ID, "metadata": ""})
        self.assertEqual(jobs.get(JOB_ID, "full", "metadata")["metadata"], {})

    def test_legacy_full_shape_without_view_is_parsed(self):
        # Alfred older than 1.130.0 ignores view and answers with the full shape.
        jobs, _ = make({"id": JOB_ID, "metadata": '{"k": "v"}'})
        self.assertEqual(jobs.get(JOB_ID)["metadata"], {"k": "v"})

    def test_invalid_and_empty_metadata_become_empty_dict(self):
        for raw in ("not-json", "", None, "[1, 2]", '"text"', "12", "null", 5, [1]):
            jobs, _ = make({"id": JOB_ID, "metadata": raw})
            self.assertEqual(jobs.get(JOB_ID, "full")["metadata"], {}, raw)

    def test_dict_metadata_is_kept(self):
        meta = {"records": [{"a": 1}, {"a": 2}], "o": {"x": ["y"]}, "s": "t"}
        jobs, _ = make({"id": JOB_ID, "metadata": meta})
        self.assertEqual(jobs.get(JOB_ID, "full")["metadata"], meta)

    def test_list_of_records_values_inside_string_metadata(self):
        jobs, _ = make(
            {"id": JOB_ID, "metadata": '{"lines": [{"sku": "a"}, {"sku": "b"}]}'}
        )
        self.assertEqual(
            jobs.get(JOB_ID, "full")["metadata"],
            {"lines": [{"sku": "a"}, {"sku": "b"}]},
        )

    def test_wrapped_job_is_normalized(self):
        jobs, _ = make({"result": {"id": JOB_ID, "metadata": '{"k": 1}'}, "x": 1})
        self.assertEqual(
            jobs.get(JOB_ID),
            {"result": {"id": JOB_ID, "metadata": {"k": 1}}, "x": 1},
        )

    def test_non_dict_payloads_pass_through(self):
        for payload in (None, "text", 5, [{"metadata": "x"}]):
            jobs, _ = make(payload)
            self.assertEqual(jobs.get(JOB_ID, "full"), payload)

    def test_input_payload_is_not_mutated(self):
        payload = {"id": JOB_ID, "metadata": '{"k": 1}'}
        jobs, _ = make(payload)
        jobs.get(JOB_ID)
        self.assertEqual(payload["metadata"], '{"k": 1}')


class TestGetAllRequest(unittest.TestCase):
    def setUp(self):
        self.jobs, self.client = make({"items": []})

    def test_no_arguments_sends_nothing(self):
        self.jobs.get_all()
        self.assertEqual(self.client.last["method"], "GET")
        self.assertEqual(self.client.last["uri"], "/api/job/all")
        self.assertEqual(self.client.last["params"], {})
        self.assertIsNone(self.client.last["data"])

    def test_positional_order_is_page_size_then_current_page(self):
        self.jobs.get_all(25, 3)
        self.assertEqual(
            self.client.last["params"],
            {"page": 3, "currentPage": 3, "page_size": 25, "pageSize": 25},
        )

    def test_page_size_only(self):
        self.jobs.get_all(page_size=50)
        self.assertEqual(
            self.client.last["params"], {"page_size": 50, "pageSize": 50}
        )

    def test_current_page_only(self):
        self.jobs.get_all(current_page=2)
        self.assertEqual(self.client.last["params"], {"page": 2, "currentPage": 2})

    def test_page_keyword(self):
        self.jobs.get_all(page=4)
        self.assertEqual(self.client.last["params"], {"page": 4, "currentPage": 4})

    def test_page_and_current_page_equal_is_fine(self):
        self.jobs.get_all(current_page=4, page=4)
        self.assertEqual(self.client.last["params"], {"page": 4, "currentPage": 4})

    def test_page_conflict_raises_before_request(self):
        with self.assertRaises(ValueError):
            self.jobs.get_all(current_page=1, page=2)
        self.assertEqual(self.client.calls, [])

    def test_zero_values_are_sent_so_the_server_can_reject_them(self):
        self.jobs.get_all(0, 0)
        self.assertEqual(
            self.client.last["params"],
            {"page": 0, "currentPage": 0, "page_size": 0, "pageSize": 0},
        )

    def test_page_arguments_after_page_size_are_keyword_only(self):
        with self.assertRaises(TypeError):
            self.jobs.get_all(10, 1, 2)

    def test_filters(self):
        self.jobs.get_all(
            sort_direction="ASC",
            correlation_id="Erp:1",
            channel="api",
            view=JobView.FULL,
        )
        self.assertEqual(
            self.client.last["params"],
            {
                "sortDirection": "ASC",
                "correlation_id": "Erp:1",
                "channel": "api",
                "view": "full",
            },
        )

    def test_view_string(self):
        self.jobs.get_all(view="summary")
        self.assertEqual(self.client.last["params"], {"view": "summary"})

    def test_dates(self):
        self.jobs.get_all(
            start_date=datetime.date(2026, 1, 5),
            end_date=datetime.datetime(2026, 2, 6, 23, 59, 59),
        )
        self.assertEqual(
            self.client.last["params"],
            {"startDate": "2026-01-05", "endDate": "2026-02-06"},
        )

    def test_date_strings_are_sent_as_given(self):
        self.jobs.get_all(start_date="2026-01-05", end_date="whatever")
        self.assertEqual(
            self.client.last["params"],
            {"startDate": "2026-01-05", "endDate": "whatever"},
        )

    def test_bad_date_type(self):
        for kwargs in ({"start_date": 20260105}, {"end_date": 1.5}):
            with self.assertRaises(TypeError):
                self.jobs.get_all(**kwargs)
        self.assertEqual(self.client.calls, [])


class TestGetAllResponse(unittest.TestCase):
    def test_new_envelope_passes_through(self):
        payload = {
            "items": [{"id": "a"}, {"id": "b"}],
            "page": 2,
            "page_size": 25,
            "total": 412,
            "has_more": True,
        }
        jobs, _ = make(dict(payload))
        self.assertEqual(jobs.get_all(25, 2), payload)

    def test_new_envelope_keeps_extra_keys_and_server_values(self):
        jobs, _ = make(
            {"items": [], "page": 9, "page_size": 10, "total": 1, "has_more": False,
             "extra": {"k": 1}}
        )
        result = jobs.get_all(25, 2)
        self.assertEqual(result["extra"], {"k": 1})
        self.assertEqual(result["page"], 9)
        self.assertEqual(result["page_size"], 10)

    def test_new_envelope_null_items(self):
        jobs, _ = make({"items": None, "page": 1, "page_size": 10, "total": 0,
                        "has_more": False})
        self.assertEqual(jobs.get_all()["items"], [])

    def test_new_envelope_non_list_items(self):
        jobs, _ = make({"items": "oops", "total": 0})
        self.assertEqual(jobs.get_all()["items"], [])

    def test_empty_dict_payload_becomes_empty_envelope_items(self):
        jobs, _ = make({})
        self.assertEqual(jobs.get_all(), {"items": []})

    def test_legacy_envelope_is_converted(self):
        jobs, _ = make({"result": [{"id": "a"}], "total": 42, "is_empty": False})
        self.assertEqual(
            jobs.get_all(10, 2),
            {
                "items": [{"id": "a"}],
                "page": 2,
                "page_size": 10,
                "total": 42,
                "has_more": True,
            },
        )

    def test_legacy_defaults_when_nothing_requested(self):
        jobs, _ = make({"result": [], "total": 5, "is_empty": True})
        self.assertEqual(
            jobs.get_all(),
            {"items": [], "page": 1, "page_size": 10, "total": 5, "has_more": False},
        )

    def test_legacy_has_more_boundary(self):
        for page, total, expected in [(2, 20, False), (2, 21, True), (1, 10, False)]:
            jobs, _ = make({"result": [], "total": total})
            self.assertEqual(
                jobs.get_all(10, page)["has_more"], expected, (page, total)
            )

    def test_legacy_uses_page_keyword_and_keeps_extra_keys(self):
        jobs, _ = make({"result": [], "total": 100, "is_empty": True, "x": 1})
        result = jobs.get_all(page_size=20, page=3)
        self.assertEqual(result["page"], 3)
        self.assertEqual(result["page_size"], 20)
        self.assertEqual(result["x"], 1)
        self.assertNotIn("result", result)
        self.assertNotIn("is_empty", result)

    def test_legacy_null_result_and_missing_total(self):
        jobs, _ = make({"result": None})
        self.assertEqual(
            jobs.get_all(),
            {"items": [], "page": 1, "page_size": 10, "total": 0, "has_more": False},
        )

    def test_non_dict_payloads_pass_through(self):
        for payload in (None, [1, 2], "x"):
            jobs, _ = make(payload)
            self.assertEqual(jobs.get_all(), payload)

    def test_summary_items_get_no_invented_metadata(self):
        jobs, _ = make({"items": [{"id": "a"}, {"id": "b"}], "total": 2})
        self.assertEqual(jobs.get_all()["items"], [{"id": "a"}, {"id": "b"}])

    def test_full_items_are_guaranteed_a_metadata_dict(self):
        jobs, _ = make(
            {
                "items": [
                    {"id": "a", "metadata": '{"k": "v"}'},
                    {"id": "b", "metadata": ""},
                    {"id": "c"},
                    {"id": "d", "metadata": {"already": ["dict"]}},
                    {"id": "e", "metadata": "[1]"},
                    "not-a-job",
                ]
            }
        )
        items = jobs.get_all(view="full")["items"]
        self.assertEqual(
            items,
            [
                {"id": "a", "metadata": {"k": "v"}},
                {"id": "b", "metadata": {}},
                {"id": "c", "metadata": {}},
                {"id": "d", "metadata": {"already": ["dict"]}},
                {"id": "e", "metadata": {}},
                "not-a-job",
            ],
        )

    def test_summary_view_items_with_metadata_key_are_parsed(self):
        jobs, _ = make({"result": [{"id": "a", "metadata": '{"k": 1}'}, {"id": "b"}]})
        self.assertEqual(
            jobs.get_all()["items"],
            [{"id": "a", "metadata": {"k": 1}}, {"id": "b"}],
        )

    def test_legacy_full_items_get_metadata(self):
        jobs, _ = make({"result": [{"id": "b"}], "total": 1})
        self.assertEqual(
            jobs.get_all(view=JobView.FULL)["items"], [{"id": "b", "metadata": {}}]
        )


class TestActions(unittest.TestCase):
    def test_cancel(self):
        jobs, client = make({"canceled": True})
        self.assertEqual(jobs.cancel(JOB_ID), {"canceled": True})
        self.assertEqual(
            client.last,
            {
                "method": "POST",
                "uri": "/api/job/cancel",
                "params": {"jobId": JOB_ID},
                "data": None,
            },
        )

    def test_cancel_uuid(self):
        jobs, client = make({"canceled": False})
        jobs.cancel(uuid.UUID(JOB_ID))
        self.assertEqual(client.last["params"], {"jobId": JOB_ID})

    def test_restart_default(self):
        jobs, client = make({"restarted": True})
        self.assertEqual(jobs.restart(JOB_ID), {"restarted": True})
        self.assertEqual(
            client.last,
            {
                "method": "POST",
                "uri": "/api/job/restart",
                "params": {"jobId": JOB_ID, "redownloadRemoteFiles": "false"},
                "data": None,
            },
        )

    def test_restart_redownload(self):
        jobs, client = make({"restarted": True})
        jobs.restart(JOB_ID, redownload_remote_files=True)
        self.assertEqual(
            client.last["params"],
            {"jobId": JOB_ID, "redownloadRemoteFiles": "true"},
        )
        jobs.restart(JOB_ID, True)
        self.assertEqual(client.last["params"]["redownloadRemoteFiles"], "true")

    def test_check_sources(self):
        response = {"available": False, "unavailable_urls": ["https://x/y.pdf"]}
        jobs, client = make(response)
        self.assertEqual(jobs.check_sources(JOB_ID), response)
        self.assertEqual(
            client.last,
            {
                "method": "POST",
                "uri": "/api/job/check-sources",
                "params": {"jobId": JOB_ID},
                "data": None,
            },
        )

    def test_blank_ids_raise_before_any_request(self):
        for method in ("cancel", "restart", "check_sources"):
            for bad in (None, "", "  "):
                jobs, client = make()
                with self.assertRaises(ValueError):
                    getattr(jobs, method)(bad)
                self.assertEqual(client.calls, [])

    def test_wrong_type_id(self):
        jobs, client = make()
        with self.assertRaises(TypeError):
            jobs.cancel(7)
        self.assertEqual(client.calls, [])

    def test_http_errors_propagate(self):
        class Boom(Exception):
            pass

        class Failing(RecordingHttpClient):
            def _call(self, *args, **kwargs):
                raise Boom()

        jobs = Jobs(Failing())
        for call in (
            lambda: jobs.get(JOB_ID),
            lambda: jobs.get_all(),
            lambda: jobs.create({}),
            lambda: jobs.cancel(JOB_ID),
            lambda: jobs.restart(JOB_ID),
            lambda: jobs.check_sources(JOB_ID),
        ):
            with self.assertRaises(Boom):
                call()


if __name__ == "__main__":
    unittest.main()
