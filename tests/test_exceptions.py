import json
import pickle
import unittest
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime

import requests

import alfred.exceptions as errors
from alfred.base import exceptions as base_exceptions

URL = "https://app.example.test/api/job/detail/abc-123"


def make_response(status=400, body=None, headers=None, reason=None, method="GET", url=URL, json_body=None):
    """Build a requests.Response the way an adapter would."""
    response = requests.Response()
    response.status_code = status
    response.reason = reason
    response.url = url
    if json_body is not None:
        body = json.dumps(json_body)
        headers = {"Content-Type": "application/json; charset=utf-8", **(headers or {})}
    if body is not None:
        response._content = body.encode("utf-8") if isinstance(body, str) else body
    else:
        response._content = b""
    response.headers.update(headers or {})
    response.request = requests.Request(method, url).prepare()
    return response


class TestHierarchy(unittest.TestCase):
    def test_tree(self):
        expected = {
            errors.AlfredMissingAuthException: (errors.AlfredError,),
            errors.AlfredMissingArgument: (errors.AlfredError,),
            errors.ConnectionError: (errors.AlfredError,),
            errors.AlfredRequestError: (errors.AlfredError, requests.exceptions.RequestException),
            errors.AlfredConnectionError: (errors.AlfredRequestError, requests.exceptions.ConnectionError),
            errors.AlfredTimeoutError: (errors.AlfredRequestError, requests.exceptions.Timeout),
            errors.AlfredConnectTimeoutError: (
                errors.AlfredTimeoutError,
                errors.AlfredConnectionError,
                requests.exceptions.ConnectTimeout,
            ),
            errors.AlfredResponseParseError: (errors.AlfredError, ValueError),
            errors.AlfredApiError: (errors.AlfredError, requests.exceptions.HTTPError),
            errors.AlfredBadRequestError: (errors.AlfredApiError,),
            errors.AlfredAuthenticationError: (errors.AlfredApiError,),
            errors.AlfredPermissionError: (errors.AlfredApiError,),
            errors.AlfredNotFoundError: (errors.AlfredApiError,),
            errors.AlfredConflictError: (errors.AlfredApiError,),
            errors.AlfredPayloadTooLargeError: (errors.AlfredApiError,),
            errors.AlfredRateLimitError: (errors.AlfredApiError,),
            errors.AlfredServerError: (errors.AlfredApiError,),
        }
        for cls, parents in expected.items():
            for parent in parents:
                self.assertTrue(issubclass(cls, parent), f"{cls.__name__} should be a {parent.__name__}")

    def test_api_error_is_not_a_transport_error(self):
        self.assertFalse(issubclass(errors.AlfredApiError, errors.AlfredRequestError))
        self.assertFalse(issubclass(errors.AlfredRequestError, errors.AlfredApiError))

    def test_legacy_import_paths_return_same_classes(self):
        self.assertIs(base_exceptions.AlfredMissingAuthException, errors.AlfredMissingAuthException)
        self.assertIs(base_exceptions.AlfredMissingArgument, errors.AlfredMissingArgument)
        from alfred.base import AlfredMissingAuthException  # pylint: disable=import-outside-toplevel

        self.assertIs(AlfredMissingAuthException, errors.AlfredMissingAuthException)

    def test_realtime_connection_error_keeps_message(self):
        self.assertEqual(errors.ConnectionError().message, "A connection error occurred")
        error = errors.ConnectionError("no socket")
        self.assertEqual(error.message, "no socket")
        self.assertEqual(str(error), "no socket")
        self.assertNotIsInstance(error, OSError)

    def test_all_names_exist(self):
        for name in errors.__all__:
            self.assertTrue(hasattr(errors, name), name)


class TestStatusMapping(unittest.TestCase):
    def test_mapped_statuses(self):
        cases = {
            400: errors.AlfredBadRequestError,
            401: errors.AlfredAuthenticationError,
            403: errors.AlfredPermissionError,
            404: errors.AlfredNotFoundError,
            409: errors.AlfredConflictError,
            413: errors.AlfredPayloadTooLargeError,
            429: errors.AlfredRateLimitError,
            500: errors.AlfredServerError,
            501: errors.AlfredServerError,
            502: errors.AlfredServerError,
            503: errors.AlfredServerError,
            504: errors.AlfredServerError,
            599: errors.AlfredServerError,
        }
        for status, cls in cases.items():
            with self.subTest(status=status):
                error = errors.AlfredApiError.from_response(make_response(status))
                self.assertIs(type(error), cls)
                self.assertEqual(error.status_code, status)
                self.assertIsInstance(error, requests.exceptions.HTTPError)

    def test_unmapped_statuses_are_plain_api_errors(self):
        for status in (402, 405, 408, 410, 412, 415, 418, 422, 423, 451, 600):
            with self.subTest(status=status):
                error = errors.AlfredApiError.from_response(make_response(status))
                self.assertIs(type(error), errors.AlfredApiError)

    def test_subclass_forces_its_class(self):
        error = errors.AlfredAuthenticationError.from_response(make_response(500))
        self.assertIs(type(error), errors.AlfredAuthenticationError)
        self.assertEqual(error.status_code, 500)

    def test_httperror_compatibility(self):
        response = make_response(404)
        try:
            raise errors.AlfredApiError.from_response(response)
        except requests.exceptions.HTTPError as exc:
            self.assertEqual(exc.response.status_code, 404)
            self.assertIs(exc.response, response)
            self.assertIs(exc.request, response.request)
        try:
            raise errors.AlfredApiError.from_response(response)
        except requests.exceptions.RequestException as exc:
            self.assertEqual(exc.response.status_code, 404)


class TestBodyShapes(unittest.TestCase):
    def build(self, status=400, **kwargs):
        return errors.AlfredApiError.from_response(make_response(status, **kwargs))

    def test_message_key(self):
        error = self.build(json_body={"message": "bad thing"})
        self.assertEqual(error.message, "bad thing")
        self.assertEqual(error.body, {"message": "bad thing"})
        self.assertIsNone(error.reason)
        self.assertIsNone(error.correlation_id)

    def test_capitalised_message_key(self):
        self.assertEqual(self.build(json_body={"Message": "Capital"}).message, "Capital")

    def test_message_with_correlation_id(self):
        error = self.build(500, json_body={"message": "boom", "correlation_id": "0123456789ab"})
        self.assertEqual(error.correlation_id, "0123456789ab")
        self.assertEqual(error.message, "boom")

    def test_camel_case_correlation_id(self):
        self.assertEqual(self.build(json_body={"message": "x", "correlationId": "abc"}).correlation_id, "abc")

    def test_job_list_validation_shape(self):
        error = self.build(json_body={"error": "page must be positive", "statusCode": 400})
        self.assertEqual(error.message, "page must be positive")

    def test_oauth_shape_prefers_description(self):
        error = self.build(json_body={"error": "invalid_grant", "error_description": "The user name or password is incorrect."})
        self.assertEqual(error.message, "The user name or password is incorrect.")

    def test_detail_key(self):
        self.assertEqual(self.build(json_body={"detail": "only detail"}).message, "only detail")

    def test_nested_error_object(self):
        self.assertEqual(self.build(json_body={"error": {"message": "nested"}}).message, "nested")

    def test_non_string_message_values_are_skipped(self):
        error = self.build(json_body={"message": ["a"], "error": 5, "detail": "usable"})
        self.assertEqual(error.message, "usable")

    def test_object_without_a_message_falls_back_to_reason_phrase(self):
        error = self.build(500, json_body={"unexpected": "shape", "message": ["not text"]})
        self.assertEqual(error.message, "Internal Server Error")
        self.assertEqual(error.body["unexpected"], "shape")

    def test_blank_message_falls_through(self):
        self.assertEqual(self.build(json_body={"message": "   ", "detail": "d"}).message, "d")

    def test_restart_refusal_shape(self):
        body = {
            "restarted": False,
            "refused": True,
            "reason": "sources-missing",
            "message": "The job cannot restart.",
            "detail": "Sources were deleted.",
        }
        error = self.build(409, json_body=body)
        self.assertIsInstance(error, errors.AlfredConflictError)
        self.assertEqual(error.reason, "sources-missing")
        self.assertEqual(error.message, "The job cannot restart.")
        self.assertEqual(error.body, body)

    def test_bare_json_string(self):
        error = self.build(409, body='"The file is busy, try again later."', headers={"Content-Type": "application/json"})
        self.assertEqual(error.message, "The file is busy, try again later.")
        self.assertEqual(error.body, "The file is busy, try again later.")

    def test_bare_json_string_without_content_type(self):
        self.assertEqual(self.build(body='"quoted"').message, "quoted")

    def test_json_list_falls_back_to_reason_phrase(self):
        error = self.build(404, json_body=["a", "b"])
        self.assertEqual(error.message, "Not Found")
        self.assertEqual(error.body, ["a", "b"])

    def test_json_null_and_number(self):
        for body in ("null", "12"):
            with self.subTest(body=body):
                error = self.build(500, body=body, headers={"Content-Type": "application/json"})
                self.assertEqual(error.message, "Internal Server Error")

    def test_plain_text(self):
        error = self.build(429, body="  Too many calls! We can only allow 2500 per Minute \n", headers={"Content-Type": "text/plain"})
        self.assertEqual(error.message, "Too many calls! We can only allow 2500 per Minute")
        self.assertIsInstance(error, errors.AlfredRateLimitError)

    def test_invalid_json_with_json_content_type(self):
        error = self.build(500, body="{not json", headers={"Content-Type": "application/json"})
        self.assertEqual(error.message, "{not json")
        self.assertEqual(error.body, "{not json")

    def test_invalid_json_without_content_type(self):
        self.assertEqual(self.build(500, body='["broken').body, '["broken')

    def test_empty_body_uses_reason_phrase(self):
        error = self.build(404, reason="Not Found")
        self.assertEqual(error.message, "Not Found")
        self.assertIsNone(error.body)

    def test_whitespace_body_is_empty(self):
        error = self.build(404, body="  \n ")
        self.assertIsNone(error.body)
        self.assertEqual(error.message, "Not Found")

    def test_missing_reason_uses_status_phrase(self):
        self.assertEqual(self.build(503, reason=None).message, "Service Unavailable")

    def test_unknown_status_phrase(self):
        self.assertEqual(self.build(499).message, "Error")

    def test_server_reason_phrase_wins_over_table(self):
        self.assertEqual(self.build(404, reason="Gone Fishing").message, "Gone Fishing")

    def test_html_page_is_reduced_and_capped(self):
        page = (
            "<html><head><title>502 Bad Gateway</title><style>body{x:y}</style></head>"
            "<body><script>alert(1)</script><h1>502 Bad &amp; Gateway</h1>" + "<p>filler</p>" * 200 + "</body></html>"
        )
        error = self.build(502, body=page, headers={"Content-Type": "text/html"})
        self.assertLessEqual(len(error.message), errors.MAX_MESSAGE_LENGTH)
        self.assertTrue(error.message.startswith("502 Bad Gateway 502 Bad & Gateway"))
        self.assertNotIn("<", error.message)
        self.assertNotIn("alert", error.message)
        self.assertEqual(error.body, page)

    def test_markup_without_text_falls_back_to_phrase(self):
        self.assertEqual(self.build(503, body="<html><body></body></html>").message, "Service Unavailable")

    def test_long_message_is_capped(self):
        error = self.build(400, json_body={"message": "word " * 500})
        self.assertEqual(len(error.message), errors.MAX_MESSAGE_LENGTH)
        self.assertTrue(error.message.endswith("..."))

    def test_message_whitespace_collapsed(self):
        self.assertEqual(self.build(json_body={"message": "a\n\n  b\tc"}).message, "a b c")

    def test_undecodable_text_does_not_raise(self):
        class Broken(requests.Response):
            @property
            def text(self):
                raise RuntimeError("cannot decode")

        response = Broken()
        response.status_code = 500
        response._content = b"\xff"
        response.request = requests.Request("GET", URL).prepare()
        error = errors.AlfredApiError.from_response(response)
        self.assertIsNone(error.body)
        self.assertEqual(error.message, "Internal Server Error")

    def test_reason_must_be_string(self):
        self.assertIsNone(self.build(json_body={"message": "m", "reason": 5}).reason)

    def test_max_bytes(self):
        cases = [(1048576, 1048576), ("2048", 2048), (True, None), ("big", None), (None, None), (1.5, None)]
        for raw, expected in cases:
            with self.subTest(raw=raw):
                error = self.build(413, json_body={"message": "too big", "max_bytes": raw})
                self.assertIsInstance(error, errors.AlfredPayloadTooLargeError)
                self.assertEqual(error.max_bytes, expected)

    def test_max_bytes_absent_or_body_not_object(self):
        self.assertIsNone(self.build(413, json_body={"message": "x"}).max_bytes)
        self.assertIsNone(self.build(413, body="too large").max_bytes)

    def test_413_with_correlation_id(self):
        error = self.build(413, json_body={"message": "x", "max_bytes": 10, "correlation_id": "abcdef012345"})
        self.assertEqual((error.max_bytes, error.correlation_id), (10, "abcdef012345"))


class TestRetryAfter(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(errors.parse_retry_after("30"), 30.0)
        self.assertEqual(errors.parse_retry_after(" 0 "), 0.0)
        self.assertEqual(errors.parse_retry_after("1.5"), 1.5)

    def test_unusable_values(self):
        for value in (None, "", "soon", "-5", "nan", "inf", "12abc", "Mon, 99 Foo 2020"):
            with self.subTest(value=value):
                self.assertIsNone(errors.parse_retry_after(value))

    def test_http_date_in_the_future(self):
        when = datetime.now(timezone.utc) + timedelta(seconds=120)
        seconds = errors.parse_retry_after(format_datetime(when, usegmt=True))
        self.assertTrue(100 <= seconds <= 120, seconds)

    def test_http_date_in_the_past_is_zero(self):
        when = datetime.now(timezone.utc) - timedelta(hours=1)
        self.assertEqual(errors.parse_retry_after(format_datetime(when, usegmt=True)), 0.0)

    def test_http_date_without_zone_is_utc(self):
        when = datetime.now(timezone.utc) + timedelta(seconds=300)
        seconds = errors.parse_retry_after(when.strftime("%a, %d %b %Y %H:%M:%S -0000"))
        self.assertTrue(250 <= seconds <= 300, seconds)

    def test_rate_limit_error_carries_retry_after(self):
        error = errors.AlfredApiError.from_response(make_response(429, body='"slow down"', headers={"Retry-After": "7"}))
        self.assertEqual(error.retry_after, 7.0)

    def test_rate_limit_without_header(self):
        self.assertIsNone(errors.AlfredApiError.from_response(make_response(429)).retry_after)

    def test_rate_limit_with_garbage_header(self):
        error = errors.AlfredApiError.from_response(make_response(429, headers={"Retry-After": "whenever"}))
        self.assertIsNone(error.retry_after)

    def test_server_error_carries_retry_after(self):
        error = errors.AlfredApiError.from_response(make_response(503, headers={"Retry-After": "11"}))
        self.assertEqual(error.retry_after, 11.0)

    def test_other_errors_have_no_retry_after_attribute(self):
        error = errors.AlfredApiError.from_response(make_response(404, headers={"Retry-After": "11"}))
        self.assertFalse(hasattr(error, "retry_after"))


class TestAttributesAndString(unittest.TestCase):
    def test_all_attributes(self):
        response = make_response(
            403,
            json_body={"message": "Needs the Account Admin role.", "reason": "role", "correlation_id": "abc123abc123"},
            reason="Forbidden",
        )
        error = errors.AlfredApiError.from_response(response)
        self.assertIs(type(error), errors.AlfredPermissionError)
        self.assertEqual(error.status_code, 403)
        self.assertEqual(error.message, "Needs the Account Admin role.")
        self.assertEqual(error.reason, "role")
        self.assertEqual(error.correlation_id, "abc123abc123")
        self.assertEqual(error.body["reason"], "role")
        self.assertIs(error.response, response)
        self.assertIs(error.request, response.request)
        self.assertEqual(error.method, "GET")
        self.assertEqual(error.url, URL)

    def test_str(self):
        error = errors.AlfredApiError.from_response(make_response(403, json_body={"message": "No role."}, reason="Forbidden"))
        self.assertEqual(str(error), f"403 Forbidden for GET {URL}: No role.")

    def test_str_when_message_is_the_reason_phrase(self):
        error = errors.AlfredApiError.from_response(make_response(404, reason="Not Found"))
        self.assertEqual(str(error), f"404 Not Found for GET {URL}")

    def test_str_has_no_query_string_or_credentials(self):
        secret_url = "https://user:hunter2@app.example.test/api/job/list?api_key=SECRET&token=ALSO#frag"
        response = make_response(500, json_body={"message": "boom"}, url=secret_url)
        error = errors.AlfredApiError.from_response(response)
        text = str(error) + repr(error) + error.url
        for needle in ("SECRET", "ALSO", "hunter2", "user:", "api_key", "frag"):
            self.assertNotIn(needle, text)
        self.assertEqual(error.url, "https://app.example.test/api/job/list")

    def test_str_never_includes_request_headers(self):
        response = make_response(401, json_body={"message": "no"})
        response.request.headers["Authorization"] = "Bearer SECRET-TOKEN"
        response.request.headers["X-TagshelfAPI-Key"] = "SECRET-KEY"
        error = errors.AlfredApiError.from_response(response)
        self.assertNotIn("SECRET", str(error) + repr(error))

    def test_response_without_request_uses_response_url(self):
        response = make_response(404)
        response.request = None
        error = errors.AlfredApiError.from_response(response)
        self.assertIsNone(error.method)
        self.assertEqual(error.url, URL)
        self.assertEqual(str(error), f"404 Not Found for {URL}")

    def test_bare_construction(self):
        error = errors.AlfredApiError()
        self.assertEqual(str(error), "Error")
        self.assertEqual(error.message, "Error")
        self.assertIsNone(error.status_code)
        error = errors.AlfredApiError("custom", status_code=499)
        self.assertEqual(str(error), "499 Error: custom")
        self.assertEqual(str(errors.AlfredApiError("only text")), "Error: only text")
        self.assertEqual(str(errors.AlfredApiError(method="GET")), "Error for GET")

    def test_unparsable_url_is_dropped(self):
        error = errors.AlfredApiError("m", status_code=500, url="http://[bad")
        self.assertIsNone(error.url)

    def test_empty_url(self):
        self.assertIsNone(errors.AlfredApiError("m", status_code=500, url="").url)

    def test_request_error_attributes(self):
        prepared = requests.Request("GET", "https://h.test/p?key=SECRET").prepare()
        error = errors.AlfredTimeoutError("took too long", method="GET", url=prepared.url, request=prepared)
        self.assertEqual(str(error), "GET https://h.test/p: took too long")
        self.assertEqual(error.message, "took too long")
        self.assertIs(error.request, prepared)
        self.assertEqual(error.url, "https://h.test/p")
        self.assertNotIn("SECRET", str(error))

    def test_request_error_defaults(self):
        error = errors.AlfredRequestError()
        self.assertEqual(str(error), "The request failed")
        self.assertIsNone(error.url)

    def test_parse_error_attributes(self):
        response = make_response(200, body="x")
        error = errors.AlfredResponseParseError("bad body", response=response)
        self.assertIs(error.response, response)
        self.assertEqual(error.status_code, 200)
        self.assertEqual(str(error), "bad body")
        self.assertIsNone(errors.AlfredResponseParseError("x").status_code)


class TestPickle(unittest.TestCase):
    def roundtrip(self, error):
        return pickle.loads(pickle.dumps(error))

    def test_api_error_survives_pickling_without_response(self):
        response = make_response(429, json_body={"message": "slow", "correlation_id": "c0ffee000000"}, headers={"Retry-After": "3"})
        # Make the request unpicklable, like a prepared request with session hooks.
        response.request.hooks["response"].append(lambda r, **kw: r)
        error = errors.AlfredApiError.from_response(response)
        clone = self.roundtrip(error)
        self.assertIs(type(clone), errors.AlfredRateLimitError)
        self.assertEqual(str(clone), str(error))
        self.assertEqual(clone.status_code, 429)
        self.assertEqual(clone.retry_after, 3.0)
        self.assertEqual(clone.correlation_id, "c0ffee000000")
        self.assertIsNone(clone.response)
        self.assertIsNone(clone.request)

    def test_other_errors_pickle(self):
        for error in (
            errors.AlfredMissingAuthException("x"),
            errors.ConnectionError("down"),
            errors.AlfredTimeoutError("t", method="GET", url="https://h.test/x"),
            errors.AlfredResponseParseError("p"),
            errors.AlfredPayloadTooLargeError("m", status_code=413, max_bytes=5),
        ):
            with self.subTest(error=type(error).__name__):
                clone = self.roundtrip(error)
                self.assertIs(type(clone), type(error))
                self.assertEqual(str(clone), str(error))
                self.assertEqual(clone.__dict__.keys(), error.__dict__.keys())


if __name__ == "__main__":
    unittest.main()
