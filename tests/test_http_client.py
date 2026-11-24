import base64
import hashlib
import hmac as hmac_lib
import json
import logging
import os
import socket
import threading
import unittest
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.metadata import PackageNotFoundError
from unittest import mock
from urllib.parse import quote

import requests
from requests.adapters import BaseAdapter

import alfred.exceptions as errors
from alfred.base import ResponseType
from alfred.base.exceptions import AlfredMissingAuthException
from alfred.http.http_client import HttpClient
from alfred.http.typed import AuthMethod, HttpMethod
from tests.test_exceptions import make_response

BASE = "https://alfred.test"
API_KEY_AUTH = {"api_key": "KEYVALUE-123"}
OAUTH_AUTH = {"oauth": {"username": "someone@example.test", "password": "S3cretPass"}}
HMAC_SECRET_KEY = base64.b64encode(b"0123456789abcdef").decode()
HMAC_AUTH = {"hmac": {"api_key": HMAC_SECRET_KEY, "secret_key": "the-secret"}}


def ok(obj=None, status=200, headers=None):
    """A JSON response."""
    if obj is None:
        return make_response(status, headers=headers)
    return make_response(status, json_body=obj, headers=headers)


def token(value="T1"):
    return ok({"access_token": value, "token_type": "bearer"})


class StubAdapter(BaseAdapter):
    """Plays a script of responses/exceptions through the real session."""

    def __init__(self, script):
        super().__init__()
        self.script = list(script)
        self.sent = []
        self.kwargs = []

    def send(self, request, **kwargs):  # pylint: disable=arguments-differ
        self.sent.append(request.copy())
        self.kwargs.append(kwargs)
        if not self.script:
            raise AssertionError(f"Unexpected request: {request.method} {request.url}")
        item = self.script.pop(0)
        if isinstance(item, BaseException):
            raise item
        item.request = request
        item.url = request.url
        return item

    def close(self):
        pass


class ClientTestCase(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.dict(os.environ)
        patcher.start()
        self.addCleanup(patcher.stop)
        os.environ.pop("ALFRED_API_KEY", None)
        sleeper = mock.patch("alfred.http.http_client.sleep")
        self.sleep = sleeper.start()
        self.addCleanup(sleeper.stop)

    def make(self, script=(), auth=None, config=None):
        adapter = StubAdapter(script)
        client = HttpClient(BASE, auth or API_KEY_AUTH, {"retry_backoff_factor": 0, **(config or {})})
        client.session.mount("https://", adapter)
        client.session.mount("http://", adapter)
        return client, adapter


class TestStatusMapping(ClientTestCase):
    def test_every_status_raises_the_typed_error(self):
        cases = [
            (400, errors.AlfredBadRequestError),
            (401, errors.AlfredAuthenticationError),
            (403, errors.AlfredPermissionError),
            (404, errors.AlfredNotFoundError),
            (409, errors.AlfredConflictError),
            (413, errors.AlfredPayloadTooLargeError),
            (429, errors.AlfredRateLimitError),
            (500, errors.AlfredServerError),
            (502, errors.AlfredServerError),
            (503, errors.AlfredServerError),
            (504, errors.AlfredServerError),
            (418, errors.AlfredApiError),
            (422, errors.AlfredApiError),
        ]
        for status, cls in cases:
            for method in ("get", "post", "put", "delete"):
                with self.subTest(status=status, method=method):
                    client, _ = self.make([ok({"message": "nope"}, status)])
                    with self.assertRaises(errors.AlfredApiError) as ctx:
                        getattr(client, method)("/api/thing")
                    self.assertIs(type(ctx.exception), cls)
                    self.assertEqual(ctx.exception.status_code, status)
                    self.assertEqual(ctx.exception.message, "nope")
                    self.assertEqual(ctx.exception.method, method.upper())
                    self.assertEqual(ctx.exception.url, BASE + "/api/thing")

    def test_old_callers_catching_requests_httperror_still_work(self):
        client, _ = self.make([ok({"message": "gone"}, 404)])
        with self.assertRaises(requests.exceptions.HTTPError) as ctx:
            client.get("/api/job/detail/x")
        self.assertEqual(ctx.exception.response.status_code, 404)
        client, _ = self.make([ok({"message": "gone"}, 404)])
        with self.assertRaises(requests.exceptions.RequestException):
            client.get("/api/job/detail/x")

    def test_404_with_empty_body(self):
        client, _ = self.make([make_response(404, reason="Not Found")])
        with self.assertRaises(errors.AlfredNotFoundError) as ctx:
            client.get("/api/job/detail/abc")
        self.assertEqual(str(ctx.exception), f"404 Not Found for GET {BASE}/api/job/detail/abc")
        self.assertIsNone(ctx.exception.body)

    def test_403_full_view_without_role(self):
        message = "The full view needs the Account Admin role; an API key has it."
        client, _ = self.make([ok({"message": message}, 403)])
        with self.assertRaises(errors.AlfredPermissionError) as ctx:
            client.get("/api/job/detail/abc", params={"view": "full"})
        self.assertEqual(ctx.exception.message, message)
        self.assertNotIn("view=", str(ctx.exception))

    def test_409_bare_string_body(self):
        client, _ = self.make([make_response(409, body='"The file is busy, retry later."', headers={"Content-Type": "application/json"})])
        with self.assertRaises(errors.AlfredConflictError) as ctx:
            client.post("/api/file/reprocess")
        self.assertEqual(ctx.exception.message, "The file is busy, retry later.")

    def test_429_retry_after_and_plain_text(self):
        client, _ = self.make([make_response(429, body="Too many calls! We can only allow 2500 per Minute", headers={"Retry-After": "12", "Content-Type": "text/plain"})])
        with self.assertRaises(errors.AlfredRateLimitError) as ctx:
            client.get("/api/job/list")
        self.assertEqual(ctx.exception.retry_after, 12.0)
        self.assertIn("2500 per Minute", ctx.exception.message)

    def test_413_max_bytes(self):
        client, _ = self.make([ok({"message": "File too large", "max_bytes": 1000, "correlation_id": "abcdef012345"}, 413)])
        with self.assertRaises(errors.AlfredPayloadTooLargeError) as ctx:
            client.post("/api/file/upload")
        self.assertEqual(ctx.exception.max_bytes, 1000)
        self.assertEqual(ctx.exception.correlation_id, "abcdef012345")

    def test_gateway_html(self):
        page = "<html><head><title>502 Bad Gateway</title></head><body><center>nginx</center></body></html>"
        client, _ = self.make([make_response(502, body=page, headers={"Content-Type": "text/html"})])
        with self.assertRaises(errors.AlfredServerError) as ctx:
            client.get("/api/job/list")
        self.assertNotIn("<", ctx.exception.message)
        self.assertIn("502 Bad Gateway", ctx.exception.message)

    def test_redirect_and_success_statuses_do_not_raise(self):
        for status in (200, 201, 202, 204, 304):
            with self.subTest(status=status):
                client, _ = self.make([make_response(status)])
                parsed, response = client.get("/x")
                self.assertIsNone(parsed)
                self.assertEqual(response.status_code, status)


class TestTransportErrors(ClientTestCase):
    def check(self, raised, expected, also=()):
        client, _ = self.make([raised])
        with self.assertRaises(expected) as ctx:
            client.get("/api/job/list", params={"api_key": "SECRETKEY"})
        error = ctx.exception
        self.assertIs(error.__cause__, raised)
        self.assertIs(type(error), expected)
        for cls in also:
            self.assertIsInstance(error, cls)
        self.assertIsInstance(error, requests.exceptions.RequestException)
        self.assertIsInstance(error, errors.AlfredError)
        self.assertEqual(error.method, "GET")
        self.assertEqual(error.url, BASE + "/api/job/list")
        self.assertIsNotNone(error.request)
        self.assertNotIn("SECRETKEY", str(error))
        return error

    def test_read_timeout(self):
        error = self.check(requests.exceptions.ReadTimeout("read timed out"), errors.AlfredTimeoutError, (requests.exceptions.Timeout,))
        self.assertNotIsInstance(error, requests.exceptions.ConnectionError)
        self.assertIn("read timed out", str(error))

    def test_connect_timeout_is_both(self):
        self.check(
            requests.exceptions.ConnectTimeout("connect timed out"),
            errors.AlfredConnectTimeoutError,
            (errors.AlfredTimeoutError, errors.AlfredConnectionError, requests.exceptions.ConnectTimeout, requests.exceptions.ConnectionError),
        )

    def test_connection_error(self):
        self.check(requests.exceptions.ConnectionError("refused"), errors.AlfredConnectionError, (requests.exceptions.ConnectionError,))

    def test_ssl_error_is_a_connection_error(self):
        self.check(requests.exceptions.SSLError("bad cert"), errors.AlfredConnectionError)

    def test_other_requests_failures(self):
        for raised in (requests.exceptions.ChunkedEncodingError("cut"), requests.exceptions.RetryError("gave up"), requests.exceptions.ContentDecodingError("gzip")):
            with self.subTest(raised=type(raised).__name__):
                error = self.check(raised, errors.AlfredRequestError)
                self.assertNotIsInstance(error, errors.AlfredConnectionError)
                self.assertNotIsInstance(error, errors.AlfredTimeoutError)

    def test_query_string_is_removed_from_urllib3_style_messages(self):
        raised = requests.exceptions.ConnectionError(
            "HTTPSConnectionPool(host='alfred.test', port=443): Max retries exceeded with url: /api/job/list?api_key=SECRETKEY (Caused by ...)"
        )
        client, _ = self.make([raised])
        with self.assertRaises(errors.AlfredConnectionError) as ctx:
            client.get("/api/job/list", params={"api_key": "SECRETKEY"})
        self.assertIn("api_key=SECRETKEY", str(raised))
        self.assertNotIn("SECRETKEY", str(ctx.exception))
        self.assertIn("[query removed]", str(ctx.exception))

    def test_long_transport_message_is_capped(self):
        client, _ = self.make([requests.exceptions.ConnectionError("x" * 5000)])
        with self.assertRaises(errors.AlfredConnectionError) as ctx:
            client.get("/a")
        self.assertLess(len(ctx.exception.message), errors.MAX_MESSAGE_LENGTH + 50)
        self.assertTrue(ctx.exception.message.endswith("..."))

    def test_unrelated_exceptions_are_not_wrapped(self):
        client, _ = self.make([RuntimeError("bug")])
        with self.assertRaises(RuntimeError):
            client.get("/a")

    def test_backward_compatible_catch_of_connection_error(self):
        client, _ = self.make([requests.exceptions.ConnectionError("refused")])
        with self.assertRaises(requests.exceptions.ConnectionError):
            client.get("/a")


class TestParseResponse(ClientTestCase):
    def get(self, response, **config):
        client, _ = self.make([response], config=config or None)
        return client.get("/a")

    def test_json(self):
        parsed, response = self.get(ok({"a": 1}))
        self.assertEqual(parsed, {"a": 1})
        self.assertEqual(response.status_code, 200)

    def test_json_with_charset_and_case(self):
        parsed, _ = self.get(make_response(200, body='{"a": 1}', headers={"Content-Type": "Application/JSON; charset=utf-8"}))
        self.assertEqual(parsed, {"a": 1})

    def test_text(self):
        parsed, _ = self.get(make_response(200, body="hello", headers={"Content-Type": "text/plain"}))
        self.assertEqual(parsed, "hello")

    def test_unknown_content_type_is_text(self):
        parsed, _ = self.get(make_response(200, body="<b>x</b>", headers={"Content-Type": "text/html"}))
        self.assertEqual(parsed, "<b>x</b>")

    def test_xml(self):
        parsed, _ = self.get(make_response(200, body="<root><a>1</a></root>", headers={"Content-Type": "application/xml"}))
        self.assertEqual(parsed.tag, "root")

    def test_missing_content_type_is_text(self):
        response = make_response(200, body="plain")
        self.assertNotIn("Content-Type", response.headers)
        parsed, _ = self.get(response)
        self.assertEqual(parsed, "plain")

    def test_empty_body_is_none(self):
        parsed, response = self.get(make_response(200, headers={"Content-Type": "application/json"}))
        self.assertIsNone(parsed)
        self.assertEqual(response.status_code, 200)

    def test_204(self):
        parsed, _ = self.get(make_response(204))
        self.assertIsNone(parsed)

    def test_invalid_json_raises_parse_error(self):
        client, _ = self.make([make_response(200, body="{oops", headers={"Content-Type": "application/json"})])
        with self.assertRaises(errors.AlfredResponseParseError) as ctx:
            client.get("/a")
        self.assertIsInstance(ctx.exception, ValueError)
        self.assertIsInstance(ctx.exception, errors.AlfredError)
        self.assertEqual(ctx.exception.status_code, 200)
        self.assertIn("Failed to parse response", str(ctx.exception))
        self.assertIsNotNone(ctx.exception.__cause__)

    def test_invalid_xml_raises_parse_error(self):
        client, _ = self.make([make_response(200, body="<a>", headers={"Content-Type": "application/xml"})])
        with self.assertRaises(errors.AlfredResponseParseError):
            client.get("/a")

    def test_error_status_with_unparsable_body_raises_api_error_not_parse_error(self):
        client, _ = self.make([make_response(500, body="{oops", headers={"Content-Type": "application/json"})])
        with self.assertRaises(errors.AlfredServerError):
            client.get("/a")


class TestRequestShape(ClientTestCase):
    def test_get_post_put_delete(self):
        for method in ("get", "post", "put", "delete"):
            with self.subTest(method=method):
                client, adapter = self.make([ok({"ok": True})])
                parsed, response = getattr(client, method)("/api/x", params={"q": "1"}, data={"a": 1}, headers={"X-Custom": "yes"}, timeout=2.5)
                self.assertEqual(parsed, {"ok": True})
                self.assertIsInstance(response, requests.Response)
                sent = adapter.sent[0]
                self.assertEqual(sent.method, method.upper())
                self.assertEqual(sent.url, BASE + "/api/x?q=1")
                self.assertEqual(json.loads(sent.body), {"a": 1})
                self.assertEqual(sent.headers["X-Custom"], "yes")
                self.assertEqual(sent.headers["Content-Type"], "application/json")
                self.assertEqual(sent.headers["Accept"], "application/json")
                self.assertEqual(sent.headers["Accept-Charset"], "utf-8")
                self.assertEqual(sent.headers["X-TagshelfAPI-Key"], "KEYVALUE-123")
                self.assertEqual(adapter.kwargs[0]["timeout"], 2.5)

    def test_get_passes_files_and_uses_default_timeout(self):
        client, adapter = self.make([ok({})])
        client.get("/a", files={"f": ("a.txt", b"hi")})
        self.assertNotIn("application/json", adapter.sent[0].headers["Content-Type"])
        self.assertEqual(adapter.kwargs[0]["timeout"], 5)

    def test_form_data_when_content_type_is_overridden(self):
        client, adapter = self.make([ok({})])
        client.post("/a", data={"a": "1"}, headers={"Content-Type": "application/x-www-form-urlencoded"})
        self.assertEqual(adapter.sent[0].body, "a=1")

    def test_patch_via_request(self):
        client, adapter = self.make([ok({})])
        client.request(HttpMethod.PATCH, "/a", data={"x": 1})
        self.assertEqual(adapter.sent[0].method, "PATCH")

    def test_accept_header_follows_response_type(self):
        client, adapter = self.make([make_response(200, body="t", headers={"Content-Type": "text/plain"})], config={"response_type": ResponseType.TEXT})
        client.get("/a")
        self.assertEqual(adapter.sent[0].headers["Accept"], "text/plain")

    def test_invalid_request_timeout(self):
        client, adapter = self.make()
        for value in (0, -1):
            with self.assertRaises(ValueError):
                client.get("/a", timeout=value)
        self.assertEqual(adapter.sent, [])

    def test_user_agent_default_uses_package_version(self):
        with mock.patch("alfred.http.http_client.metadata.version", return_value="9.8.7") as version:
            client, adapter = self.make([ok({})])
        version.assert_called_once_with("alfred-python")
        client.get("/a")
        self.assertEqual(adapter.sent[0].headers["User-Agent"], "alfred-python/9.8.7")

    def test_user_agent_without_package_metadata(self):
        with mock.patch("alfred.http.http_client.metadata.version", side_effect=PackageNotFoundError):
            client, adapter = self.make([ok({})])
        client.get("/a")
        self.assertEqual(adapter.sent[0].headers["User-Agent"], "alfred-python")

    def test_user_agent_is_not_python_requests(self):
        client, adapter = self.make([ok({})])
        client.get("/a")
        self.assertTrue(adapter.sent[0].headers["User-Agent"].startswith("alfred-python"))

    def test_user_agent_can_be_overridden_per_request(self):
        client, adapter = self.make([ok({})])
        client.get("/a", headers={"User-Agent": "my-integration/2.0"})
        self.assertEqual(adapter.sent[0].headers["User-Agent"], "my-integration/2.0")


class TestConstructor(ClientTestCase):
    def build(self, auth=None, config=None):
        return HttpClient(BASE, API_KEY_AUTH if auth is None else auth, config)

    def test_defaults(self):
        client = self.build()
        self.assertEqual(client.max_retries, 3)
        self.assertEqual(client.timeout, 5)
        self.assertEqual(client.retry_backoff_factor, 1)
        self.assertEqual(client.throttle_delay, 1)
        self.assertEqual(client.throttle_threshold, 20)
        self.assertEqual(client.response_type, ResponseType.JSON)
        self.assertEqual(client.auth_method, AuthMethod.API_KEY)
        self.assertIsNone(client.rate_limit)

    def test_retry_strategy(self):
        client = self.build(config={"max_retries": 5, "retry_backoff_factor": 0.5})
        retry = client.session.get_adapter(BASE).max_retries
        self.assertEqual(retry.total, 5)
        self.assertEqual(retry.backoff_factor, 0.5)
        self.assertEqual(set(retry.status_forcelist), {429, 500, 502, 503, 504})
        self.assertFalse(retry.raise_on_status)
        self.assertTrue(retry.respect_retry_after_header)
        self.assertNotIn("POST", retry.allowed_methods)
        for method in ("GET", "PUT", "DELETE", "HEAD"):
            self.assertIn(method, retry.allowed_methods)
        self.assertIs(client.session.get_adapter("http://x.test").max_retries, retry)

    def test_zero_retries_allowed(self):
        client = self.build(config={"max_retries": 0})
        self.assertEqual(client.session.get_adapter(BASE).max_retries.total, 0)

    def test_invalid_values(self):
        for config in ({"max_retries": -1}, {"retry_backoff_factor": -0.1}, {"timeout": 0}, {"timeout": -2}, {"response_type": "yaml"}):
            with self.subTest(config=config):
                with self.assertRaises(ValueError):
                    self.build(config=config)

    def test_missing_auth(self):
        with self.assertRaises(AlfredMissingAuthException):
            self.build(auth={})

    def test_api_key_from_environment(self):
        os.environ["ALFRED_API_KEY"] = "ENVKEY"
        client = self.build(auth={})
        self.assertEqual(client.auth_method, AuthMethod.API_KEY)
        self.assertEqual(client.session.headers["X-TagshelfAPI-Key"], "ENVKEY")

    def test_auth_method_selection(self):
        self.assertEqual(self.build(auth=OAUTH_AUTH).auth_method, AuthMethod.OAUTH)
        self.assertEqual(self.build(auth=HMAC_AUTH).auth_method, AuthMethod.HMAC)
        self.assertEqual(self.build(auth={**OAUTH_AUTH, **HMAC_AUTH}).auth_method, AuthMethod.OAUTH)
        self.assertEqual(self.build(auth={**API_KEY_AUTH, **OAUTH_AUTH}).auth_method, AuthMethod.API_KEY)

    def test_pool_sizes(self):
        adapter = self.build().session.get_adapter(BASE)
        self.assertEqual(adapter._pool_maxsize, min(32, (os.cpu_count() or 1) + 4))
        adapter = self.build(config={"pool_connections": False}).session.get_adapter(BASE)
        self.assertEqual(adapter._pool_maxsize, 1)

    def test_cpu_count_may_be_none(self):
        with mock.patch("os.cpu_count", return_value=None):
            client = self.build()
        self.assertEqual(client.session.get_adapter(BASE)._pool_maxsize, 5)

    def test_throttle_settings(self):
        client = self.build(config={"throttle_delay": 3, "throttle_threshold": 50})
        self.assertEqual((client.throttle_delay, client.throttle_threshold), (3, 50))


class TestRateLimit(ClientTestCase):
    def headers(self, **values):
        return {f"X-RateLimit-{k}": str(v) for k, v in values.items()}

    def call(self, headers):
        client, _ = self.make([ok({}, headers=headers)])
        client.get("/a")
        return client

    def test_headers_present(self):
        client = self.call(self.headers(Limit=2500, Remaining=2400, Reset=1700000000))
        self.assertEqual(client.rate_limit["limit"], 2500)
        self.assertEqual(client.rate_limit["remaining"], 2400)
        self.assertEqual(client.rate_limit["reset_time"], datetime(2023, 11, 14, 22, 13, 20))
        self.assertIsNone(client.rate_limit["reset_time"].tzinfo)

    def test_headers_absent_mean_unknown(self):
        client = self.call({})
        self.assertIsNone(client.rate_limit)
        self.assertFalse(client.should_throttle())

    def test_garbage_headers_mean_unknown(self):
        client = self.call(self.headers(Limit="lots", Remaining="", Reset="soon"))
        self.assertIsNone(client.rate_limit)

    def test_partial_headers(self):
        client = self.call(self.headers(Remaining=5))
        self.assertEqual(client.rate_limit, {"limit": None, "remaining": 5, "reset_time": None})
        self.assertFalse(client.should_throttle())

    def test_out_of_range_reset(self):
        client = self.call(self.headers(Limit=10, Remaining=9, Reset="99999999999999999999"))
        self.assertIsNone(client.rate_limit["reset_time"])
        self.assertEqual(client.rate_limit["remaining"], 9)

    def test_headers_on_error_responses_are_recorded(self):
        client, _ = self.make([ok({"message": "x"}, 500, headers=self.headers(Limit=100, Remaining=3, Reset=1700000000))])
        with self.assertRaises(errors.AlfredServerError):
            client.get("/a")
        self.assertEqual(client.rate_limit["remaining"], 3)

    def test_missing_headers_do_not_slow_down_following_requests(self):
        client, _ = self.make([ok({}), ok({}), ok({}), ok({})])
        for _ in range(4):
            client.get("/a")
        self.sleep.assert_not_called()
        self.assertEqual(client.throttle_delay, 1)

    def test_unknown_headers_after_known_clear_the_state(self):
        client, _ = self.make([ok({}, headers=self.headers(Limit=100, Remaining=0, Reset=1)), ok({})])
        client.get("/a")
        self.assertTrue(client.should_throttle())
        with self.assertLogs("alfred-python", level="WARNING"):
            client.get("/a")
        self.sleep.assert_called_once()
        self.assertIsNone(client.rate_limit)
        self.assertFalse(client.should_throttle())

    def test_should_throttle_table(self):
        client, _ = self.make()
        cases = [
            # (rate_limit, threshold, expected)
            ({"limit": 100, "remaining": 10}, 20, True),
            ({"limit": 100, "remaining": 20}, 20, True),
            ({"limit": 100, "remaining": 21}, 20, False),
            ({"limit": 100, "remaining": 80}, 20, False),
            ({"limit": 100, "remaining": 0}, 20, True),
            ({"limit": 100, "remaining": -4}, 20, True),
            ({"limit": 0, "remaining": 0}, 20, False),
            ({"limit": 0, "remaining": 5}, 20, False),
            ({"limit": -1, "remaining": 5}, 20, False),
            ({"limit": None, "remaining": 5}, 20, False),
            ({"limit": None, "remaining": 0}, 20, True),
            ({"limit": 100, "remaining": None}, 20, False),
            ({"limit": 100, "remaining": 1}, 0, False),
            (None, 20, False),
            ({}, 20, False),
        ]
        for rate_limit, threshold, expected in cases:
            with self.subTest(rate_limit=rate_limit, threshold=threshold):
                client.rate_limit = rate_limit
                client.throttle_threshold = threshold
                self.assertIs(client.should_throttle(), expected)

    def test_delay_backs_off_to_the_maximum_and_resets(self):
        client, _ = self.make()
        client.rate_limit = {"limit": 100, "remaining": 0}
        delays = []
        for _ in range(8):
            client.should_throttle()
            delays.append(client.throttle_delay)
        self.assertEqual(delays, [2, 4, 8, 16, 32, 60, 60, 60])
        client.rate_limit = {"limit": 100, "remaining": 90}
        self.assertFalse(client.should_throttle())
        self.assertEqual(client.throttle_delay, 1)
        client.rate_limit = {"limit": 100, "remaining": 0}
        client.should_throttle()
        client.rate_limit = {"limit": 0, "remaining": 0}
        client.should_throttle()
        self.assertEqual(client.throttle_delay, 1)

    def test_custom_initial_delay_is_restored(self):
        client, _ = self.make(config={"throttle_delay": 3})
        client.rate_limit = {"limit": 100, "remaining": 0}
        client.should_throttle()
        self.assertEqual(client.throttle_delay, 6)
        client.rate_limit = {"limit": 100, "remaining": 99}
        client.should_throttle()
        self.assertEqual(client.throttle_delay, 3)

    def test_request_sleeps_when_close_to_the_limit(self):
        client, _ = self.make([ok({}, headers=self.headers(Limit=100, Remaining=5)), ok({})])
        client.get("/a")
        self.sleep.assert_not_called()
        with self.assertLogs("alfred-python", level="WARNING") as logs:
            client.get("/a")
        self.sleep.assert_called_once_with(1)
        self.assertIn("Throttling", logs.output[0])

    def test_throttle_warning_uses_the_client_logger_not_the_root_logger(self):
        client, _ = self.make()
        client.rate_limit = {"limit": 100, "remaining": 1}
        with mock.patch("logging.warning") as root_warning:
            with self.assertLogs("alfred-python", level="WARNING") as logs:
                client.throttle_request(0)
        root_warning.assert_not_called()
        self.assertEqual(logs.records[0].name, "alfred-python")

    def test_throttling_disabled(self):
        client, _ = self.make([ok({}, headers=self.headers(Limit=100, Remaining=0)), ok({})], config={"throttle_threshold": 0})
        client.get("/a")
        client.get("/a")
        self.sleep.assert_not_called()

    def test_no_sleep_when_not_throttled(self):
        client, _ = self.make()
        client.throttle_request(5)
        self.sleep.assert_not_called()


class TestHmac(ClientTestCase):
    def expected(self, sent, nonce="nonce-1", timestamp="1700000000"):
        body = sent.body
        if isinstance(body, str):
            body = body.encode("utf-8")
        content = base64.b64encode(hashlib.md5(body).digest()).decode() if body else ""
        raw = "the-secret" + sent.method + quote(sent.url, safe="").lower() + timestamp + nonce + content
        digest = hmac_lib.new(base64.b64decode(HMAC_SECRET_KEY), raw.encode(), hashlib.sha256).digest()
        return f"amx the-secret:{base64.b64encode(digest).decode()}:{nonce}:{timestamp}"

    def sign(self, **request):
        client, adapter = self.make([ok({})], auth=HMAC_AUTH)
        with mock.patch("alfred.http.http_client.uuid4", return_value="nonce-1"), mock.patch("alfred.http.http_client.time", return_value=1700000000.9):
            getattr(client, request.pop("method"))("/api/x", **request)
        return adapter.sent[0]

    def test_no_body(self):
        sent = self.sign(method="get", params={"a": "b"})
        self.assertIsNone(sent.body)
        self.assertEqual(sent.headers["Authorization"], self.expected(sent))

    def test_json_body_is_bytes(self):
        sent = self.sign(method="post", data={"a": "é"})
        self.assertIsInstance(sent.body, bytes)
        self.assertEqual(sent.headers["Authorization"], self.expected(sent))

    def test_form_body_is_str(self):
        sent = self.sign(method="post", data={"a": "1"}, headers={"Content-Type": "application/x-www-form-urlencoded"})
        self.assertIsInstance(sent.body, str)
        self.assertEqual(sent.headers["Authorization"], self.expected(sent))

    def test_multipart_upload_body_is_bytes(self):
        sent = self.sign(method="post", files={"file": ("a.bin", b"\x00\xff binary")})
        self.assertIsInstance(sent.body, bytes)
        self.assertEqual(sent.headers["Authorization"], self.expected(sent))

    def test_body_that_is_neither_text_nor_bytes_is_not_hashed(self):
        client, adapter = self.make([ok({})], auth=HMAC_AUTH)
        client.post("/a", data={"a": 1}, headers={"Content-Type": "application/x-www-form-urlencoded"})
        prepared = adapter.sent[0]
        prepared.body = iter([b"x"])
        client._HttpClient__auth_with_hmac(prepared)
        self.assertTrue(prepared.headers["Authorization"].startswith("amx the-secret:"))

    def test_header_sent_and_no_api_key_header(self):
        sent = self.sign(method="get")
        self.assertNotIn("X-TagshelfAPI-Key", sent.headers)

    def test_401_does_not_refresh_with_hmac(self):
        client, adapter = self.make([ok({"message": "no"}, 401)], auth=HMAC_AUTH)
        with self.assertRaises(errors.AlfredAuthenticationError):
            client.get("/a")
        self.assertEqual(len(adapter.sent), 1)


class TestOAuth(ClientTestCase):
    def make_oauth(self, script, **kwargs):
        return self.make(script, auth=OAUTH_AUTH, **kwargs)

    def bearer(self, prepared):
        return prepared.headers.get("Authorization")

    def test_token_is_fetched_once_and_used(self):
        client, adapter = self.make_oauth([token("T1"), ok({"n": 1}), ok({"n": 2})])
        client.get("/a")
        client.get("/b")
        self.assertEqual(len(adapter.sent), 3)
        token_request = adapter.sent[0]
        self.assertEqual(token_request.url, BASE + "/token")
        self.assertEqual(token_request.method, "POST")
        self.assertNotIn("Authorization", token_request.headers)
        self.assertIn("grant_type=password", token_request.body)
        self.assertEqual(self.bearer(adapter.sent[1]), "Bearer T1")
        self.assertEqual(self.bearer(adapter.sent[2]), "Bearer T1")

    def test_invalid_grant(self):
        body = {"error": "invalid_grant", "error_description": "The user name or password is incorrect."}
        client, adapter = self.make_oauth([ok(body, 400)])
        with self.assertRaises(errors.AlfredAuthenticationError) as ctx:
            client.get("/a")
        error = ctx.exception
        self.assertEqual(error.status_code, 400)
        self.assertEqual(error.message, "The user name or password is incorrect.")
        self.assertEqual(error.body, body)
        self.assertIsInstance(error, requests.exceptions.HTTPError)
        self.assertEqual(error.url, BASE + "/token")
        self.assertNotIn("S3cretPass", str(error))
        self.assertIsNone(client.token)
        self.assertEqual(len(adapter.sent), 1)

    def test_a_refused_token_request_is_an_authentication_error(self):
        for status in (400, 401, 403, 404, 422):
            with self.subTest(status=status):
                client, _ = self.make_oauth([ok({"error": "x"}, status)])
                with self.assertRaises(errors.AlfredAuthenticationError) as ctx:
                    client.get("/a")
                self.assertEqual(ctx.exception.status_code, status)

    def test_a_rate_limited_or_failing_token_endpoint_keeps_its_own_error(self):
        # Neither says anything about the credentials: the caller can retry.
        expected = {
            429: errors.AlfredRateLimitError,
            500: errors.AlfredServerError,
            503: errors.AlfredServerError,
        }
        for status, error_class in expected.items():
            with self.subTest(status=status):
                client, adapter = self.make_oauth([ok({"message": "later"}, status)])
                with self.assertRaises(error_class) as ctx:
                    client.get("/a")
                self.assertNotIsInstance(ctx.exception, errors.AlfredAuthenticationError)
                self.assertEqual(ctx.exception.status_code, status)
                self.assertIsNone(client.token)
                self.assertEqual(len(adapter.sent), 1)

    def test_token_401_does_not_loop(self):
        client, adapter = self.make_oauth([ok({"error": "x"}, 401)])
        with self.assertRaises(errors.AlfredAuthenticationError):
            client.get("/a")
        self.assertEqual(len(adapter.sent), 1)

    def test_token_response_without_access_token(self):
        for body in ({"token_type": "bearer"}, {"access_token": ""}, {"access_token": None}, {"access_token": 5}, ["x"], "text"):
            with self.subTest(body=body):
                client, adapter = self.make_oauth([ok(body)])
                with self.assertRaises(errors.AlfredAuthenticationError) as ctx:
                    client.get("/a")
                self.assertIn("access_token", str(ctx.exception))
                self.assertEqual(ctx.exception.status_code, 200)
                self.assertIsNone(client.token)
                # Nothing was sent with a "Bearer None" header.
                self.assertEqual(len(adapter.sent), 1)

    def test_token_response_not_json(self):
        client, _ = self.make_oauth([make_response(200, body="<html>login</html>", headers={"Content-Type": "text/html"})])
        with self.assertRaises(errors.AlfredAuthenticationError) as ctx:
            client.get("/a")
        self.assertIn("not valid JSON", str(ctx.exception))
        self.assertIsInstance(ctx.exception.__cause__, ValueError)

    def test_token_transport_failures_keep_their_transport_type(self):
        client, _ = self.make_oauth([requests.exceptions.ConnectionError("refused")])
        with self.assertRaises(errors.AlfredConnectionError):
            client.get("/a")
        client, _ = self.make_oauth([requests.exceptions.ReadTimeout("slow")])
        with self.assertRaises(errors.AlfredTimeoutError):
            client.get("/a")

    def test_refresh_after_401_resends_with_new_token_and_timeout(self):
        client, adapter = self.make_oauth([token("T1"), ok({"message": "expired"}, 401), token("T2"), ok({"done": True})])
        parsed, _ = client.get("/a", timeout=2.5)
        self.assertEqual(parsed, {"done": True})
        self.assertEqual([self.bearer(r) for r in adapter.sent], [None, "Bearer T1", None, "Bearer T2"])
        self.assertEqual(client.token, "T2")
        # The re-sent request must keep the caller's timeout (it used to have none).
        self.assertEqual([k["timeout"] for k in adapter.kwargs], [5, 2.5, 5, 2.5])

    def test_refresh_resend_uses_client_default_timeout(self):
        client, adapter = self.make_oauth([token("T1"), ok({}, 401), token("T2"), ok({})])
        client.get("/a")
        self.assertEqual(adapter.kwargs[3]["timeout"], 5)

    def test_refresh_still_401_raises_and_does_not_block_later_refreshes(self):
        client, adapter = self.make_oauth([token("T1"), ok({}, 401), token("T2"), ok({"message": "still no"}, 401)])
        with self.assertRaises(errors.AlfredAuthenticationError) as ctx:
            client.get("/a")
        self.assertEqual(ctx.exception.message, "still no")
        adapter.script.extend([ok({}, 401), token("T3"), ok({"ok": 1})])
        parsed, _ = client.get("/b")
        self.assertEqual(parsed, {"ok": 1})
        self.assertEqual(self.bearer(adapter.sent[-1]), "Bearer T3")

    def test_failed_refresh_does_not_block_later_refreshes(self):
        client, adapter = self.make_oauth([token("T1"), ok({}, 401), ok({"error": "invalid_grant"}, 400)])
        with self.assertRaises(errors.AlfredAuthenticationError) as ctx:
            client.get("/a")
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIsNone(client.token)
        adapter.script.extend([token("T2"), ok({"n": 2})])
        client.get("/b")
        self.assertEqual(client.token, "T2")
        # A later expiry is refreshed again.
        adapter.script.extend([ok({}, 401), token("T3"), ok({"n": 3})])
        parsed, _ = client.get("/c")
        self.assertEqual(parsed, {"n": 3})
        self.assertEqual(client.token, "T3")

    def test_transport_failure_on_resend_is_wrapped(self):
        client, _ = self.make_oauth([token("T1"), ok({}, 401), token("T2"), requests.exceptions.ReadTimeout("slow")])
        with self.assertRaises(errors.AlfredTimeoutError):
            client.get("/a")

    def test_401_with_api_key_is_not_retried(self):
        client, adapter = self.make([ok({"message": "bad key"}, 401)])
        with self.assertRaises(errors.AlfredAuthenticationError) as ctx:
            client.get("/a")
        self.assertEqual(ctx.exception.message, "bad key")
        self.assertEqual(len(adapter.sent), 1)


class TestLogging(ClientTestCase):
    def logged(self, logs):
        return [record.msg for record in logs.records if isinstance(record.msg, dict)]

    def test_token_request_body_is_never_logged(self):
        client, _ = self.make([token("T1"), ok({})], auth=OAUTH_AUTH)
        with self.assertLogs("alfred-python", level="DEBUG") as logs:
            client.get("/a")
        text = "\n".join(str(m) for m in self.logged(logs))
        self.assertNotIn("S3cretPass", text)
        self.assertNotIn("someone@example.test", text)
        self.assertNotIn("Bearer T1", text)
        token_entries = [m for m in self.logged(logs) if m["url"].endswith("/token")]
        self.assertEqual(len(token_entries), 1)
        self.assertEqual(token_entries[0]["body"], "[redacted]")

    def test_failed_token_request_is_logged_without_body(self):
        client, _ = self.make([ok({"error": "invalid_grant"}, 400)], auth=OAUTH_AUTH)
        with self.assertLogs("alfred-python", level="DEBUG") as logs:
            with self.assertRaises(errors.AlfredAuthenticationError):
                client.get("/a")
        self.assertNotIn("S3cretPass", "\n".join(str(m) for m in self.logged(logs)))
        self.assertTrue(any(m["message"] == "HTTP response details." for m in self.logged(logs)))

    def test_auth_headers_are_redacted(self):
        for auth, header in ((API_KEY_AUTH, "X-TagshelfAPI-Key"), (HMAC_AUTH, "Authorization"), (OAUTH_AUTH, "Authorization")):
            with self.subTest(header=header):
                script = [token("T1"), ok({})] if auth is OAUTH_AUTH else [ok({})]
                client, adapter = self.make(script, auth=auth)
                with self.assertLogs("alfred-python", level="DEBUG") as logs:
                    client.get("/a", headers={"Cookie": "session=abc", "Proxy-Authorization": "Basic zzz"})
                self.assertIn(header, adapter.sent[-1].headers)
                text = "\n".join(str(m) for m in self.logged(logs))
                for needle in ("KEYVALUE-123", "amx the-secret", "Bearer T1", "session=abc", "Basic zzz"):
                    self.assertNotIn(needle, text)
                entries = self.logged(logs)
                self.assertNotIn(header, entries[-1]["headers"])
                self.assertIn("Accept", entries[-1]["headers"])

    def test_text_body_is_logged_and_bytes_body_is_not(self):
        client, _ = self.make([ok({}), ok({})])
        with self.assertLogs("alfred-python", level="DEBUG") as logs:
            client.post("/a", data={"a": "1"}, headers={"Content-Type": "application/x-www-form-urlencoded"})
            client.post("/a", data={"a": "2"})
        entries = self.logged(logs)
        self.assertEqual(entries[0]["body"], "a=1")
        self.assertEqual(entries[1]["body"], "")

    def test_error_response_is_logged(self):
        client, _ = self.make([ok({"message": "bad"}, 400)])
        with self.assertLogs("alfred-python", level="DEBUG") as logs:
            with self.assertRaises(errors.AlfredBadRequestError):
                client.get("/a")
        details = [m for m in self.logged(logs) if m["message"] == "HTTP response details."]
        self.assertEqual(details[0]["status_code"], 400)
        self.assertIn("bad", details[0]["body"])

    def test_success_response_body_is_not_logged(self):
        client, _ = self.make([ok({"secret": "value"})])
        with self.assertLogs("alfred-python", level="DEBUG") as logs:
            client.get("/a")
        self.assertEqual([m["message"] for m in self.logged(logs)], ["HTTP request details."])

    def test_logger_state_is_untouched(self):
        logger = logging.getLogger("alfred-python")
        before = (logger.level, list(logger.handlers), logger.propagate)
        client, _ = self.make([ok({})])
        client.get("/a")
        self.assertEqual((logger.level, list(logger.handlers), logger.propagate), before)


class ScriptedServer:
    """A loopback HTTP server answering a scripted sequence of responses."""

    def __init__(self, script):
        self.script = list(script)
        self.requests = []
        self.release = threading.Event()
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def handle_any(self):
                length = int(self.headers.get("Content-Length") or 0)
                if length:
                    self.rfile.read(length)
                outer.requests.append((self.command, self.path))
                item = outer.script.pop(0) if outer.script else (500, {}, "script exhausted")
                if item == "hang":
                    outer.release.wait(10)
                    return
                status, headers, body = item
                payload = body if isinstance(body, bytes) else body.encode("utf-8")
                self.send_response(status)
                for name, value in headers.items():
                    self.send_header(name, value)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            do_GET = do_POST = do_PUT = do_DELETE = handle_any

            def log_message(self, *args):
                pass

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.httpd.daemon_threads = True
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        self.thread = threading.Thread(target=self.httpd.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True)
        self.thread.start()

    def close(self):
        self.release.set()
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(5)

    @property
    def methods(self):
        return [method for method, _ in self.requests]


def json_item(status, obj, **headers):
    return (status, {"Content-Type": "application/json", **headers}, json.dumps(obj))


class TestRetriesEndToEnd(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.dict(os.environ)
        patcher.start()
        self.addCleanup(patcher.stop)
        os.environ.pop("ALFRED_API_KEY", None)

    def start(self, script, **config):
        server = ScriptedServer(script)
        self.addCleanup(server.close)
        client = HttpClient(server.url, API_KEY_AUTH, {"retry_backoff_factor": 0, "timeout": 5, **config})
        client.session.trust_env = False
        return server, client

    def test_get_is_retried_on_every_listed_status_until_success(self):
        for status in (429, 500, 502, 503, 504):
            with self.subTest(status=status):
                server, client = self.start([json_item(status, {"message": "later"}), json_item(200, {"ok": True})])
                parsed, _ = client.get("/api/x")
                self.assertEqual(parsed, {"ok": True})
                self.assertEqual(server.methods, ["GET", "GET"])

    def test_idempotent_methods_are_retried_on_status(self):
        for method in ("get", "put", "delete"):
            with self.subTest(method=method):
                server, client = self.start([json_item(503, {"message": "later"}), json_item(200, {"ok": True})])
                getattr(client, method)("/api/x")
                self.assertEqual(len(server.requests), 2)

    def test_post_is_never_retried_on_status(self):
        for status in (429, 500, 502, 503, 504):
            with self.subTest(status=status):
                server, client = self.start([json_item(status, {"message": "x"}), json_item(200, {})])
                with self.assertRaises(errors.AlfredApiError) as ctx:
                    client.post("/api/x", data={"a": 1})
                self.assertEqual(ctx.exception.status_code, status)
                self.assertEqual(len(server.requests), 1)

    def test_exhausted_retries_raise_the_typed_error_with_the_real_body(self):
        server, client = self.start([json_item(503, {"message": "down for maintenance", "correlation_id": "abcdef012345"})] * 4)
        with self.assertRaises(errors.AlfredServerError) as ctx:
            client.get("/api/x")
        self.assertNotIsInstance(ctx.exception, requests.exceptions.RetryError)
        self.assertEqual(ctx.exception.message, "down for maintenance")
        self.assertEqual(ctx.exception.correlation_id, "abcdef012345")
        self.assertEqual(len(server.requests), 4)  # one call plus three retries

    def test_exhausted_429_carries_retry_after(self):
        server, client = self.start([(429, {"Retry-After": "0", "Content-Type": "application/json"}, '"Too many calls! We can only allow 2500 per Minute"')] * 4)
        with self.assertRaises(errors.AlfredRateLimitError) as ctx:
            client.get("/api/x")
        self.assertEqual(ctx.exception.retry_after, 0.0)
        self.assertIn("2500 per Minute", ctx.exception.message)
        self.assertEqual(len(server.requests), 4)

    def test_max_retries_zero_sends_once(self):
        server, client = self.start([json_item(503, {"message": "x"}), json_item(200, {})], max_retries=0)
        with self.assertRaises(errors.AlfredServerError):
            client.get("/api/x")
        self.assertEqual(len(server.requests), 1)

    def test_custom_max_retries(self):
        server, client = self.start([json_item(500, {"message": "x"})] * 10, max_retries=1)
        with self.assertRaises(errors.AlfredServerError):
            client.get("/api/x")
        self.assertEqual(len(server.requests), 2)

    def test_client_errors_are_not_retried(self):
        for status in (400, 401, 403, 404, 409, 413, 422):
            with self.subTest(status=status):
                server, client = self.start([json_item(status, {"message": "x"}), json_item(200, {})])
                with self.assertRaises(errors.AlfredApiError):
                    client.get("/api/x")
                self.assertEqual(len(server.requests), 1)

    def test_501_is_not_retried(self):
        server, client = self.start([json_item(501, {"message": "x"}), json_item(200, {})])
        with self.assertRaises(errors.AlfredServerError):
            client.get("/api/x")
        self.assertEqual(len(server.requests), 1)

    def test_retry_after_is_respected(self):
        with mock.patch("urllib3.util.retry.time.sleep") as sleep:
            server, client = self.start([(429, {"Retry-After": "2"}, '"slow down"'), json_item(200, {"ok": True})])
            client.get("/api/x")
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [2])
        self.assertEqual(len(server.requests), 2)

    def test_backoff_factor_is_used_without_retry_after(self):
        with mock.patch("urllib3.util.retry.time.sleep") as sleep:
            server, client = self.start([json_item(500, {"message": "x"})] * 3 + [json_item(200, {})], retry_backoff_factor=0.5)
            client.get("/api/x")
        self.assertEqual(len(server.requests), 4)
        # urllib3 does not wait before the first retry, then 0.5 * 2 ** (n - 1).
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [1.0, 2.0])

    def test_no_sleep_with_zero_backoff(self):
        with mock.patch("urllib3.util.retry.time.sleep") as sleep:
            server, client = self.start([json_item(500, {"message": "x"}), json_item(200, {})])
            client.get("/api/x")
        sleep.assert_not_called()

    def test_gateway_html_after_retries(self):
        page = ("<html><title>503 Service Unavailable</title><body>gateway</body></html>")
        server, client = self.start([(503, {"Content-Type": "text/html"}, page)] * 4)
        with self.assertRaises(errors.AlfredServerError) as ctx:
            client.get("/api/x")
        self.assertIn("503 Service Unavailable", ctx.exception.message)
        self.assertEqual(ctx.exception.body, page)

    def test_empty_gateway_body(self):
        server, client = self.start([(502, {}, "")] * 4)
        with self.assertRaises(errors.AlfredServerError) as ctx:
            client.get("/api/x")
        self.assertEqual(ctx.exception.message, "Bad Gateway")

    def test_404_empty_body(self):
        server, client = self.start([(404, {}, "")])
        with self.assertRaises(errors.AlfredNotFoundError) as ctx:
            client.get("/api/job/detail/abc")
        self.assertEqual(str(ctx.exception), f"404 Not Found for GET {server.url}/api/job/detail/abc")

    def test_success_with_empty_body(self):
        server, client = self.start([(204, {}, "")])
        parsed, response = client.delete("/api/x")
        self.assertIsNone(parsed)
        self.assertEqual(response.status_code, 204)

    def test_read_timeout_is_typed(self):
        server, client = self.start(["hang"], max_retries=0, timeout=0.3)
        with self.assertRaises(errors.AlfredTimeoutError) as ctx:
            client.get("/api/x")
        self.assertIsInstance(ctx.exception, requests.exceptions.Timeout)
        self.assertNotIsInstance(ctx.exception, errors.AlfredConnectionError)

    def test_post_read_timeout_is_not_retried(self):
        server, client = self.start(["hang", json_item(200, {})], timeout=0.3)
        with self.assertRaises(errors.AlfredTimeoutError):
            client.post("/api/x", data={})
        self.assertEqual(len(server.requests), 1)

    def test_get_read_timeout_is_retried(self):
        server, client = self.start(["hang", json_item(200, {"ok": 1})], timeout=0.3)
        parsed, _ = client.get("/api/x")
        self.assertEqual(parsed, {"ok": 1})
        self.assertEqual(len(server.requests), 2)

    def test_connection_refused_is_typed_and_hides_query(self):
        probe = socket.socket()
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
        probe.close()
        client = HttpClient(f"http://127.0.0.1:{port}", API_KEY_AUTH, {"max_retries": 0})
        client.session.trust_env = False
        with self.assertRaises(errors.AlfredConnectionError) as ctx:
            client.get("/api/x", params={"api_key": "SECRETKEY"})
        self.assertIsInstance(ctx.exception, requests.exceptions.ConnectionError)
        self.assertIsInstance(ctx.exception.__cause__, requests.exceptions.ConnectionError)
        self.assertIn("SECRETKEY", str(ctx.exception.__cause__))
        self.assertNotIn("SECRETKEY", str(ctx.exception))

    def test_connection_failures_are_retried_for_every_method(self):
        for method in ("get", "post"):
            with self.subTest(method=method):
                client = HttpClient("http://127.0.0.1:9", API_KEY_AUTH, {"max_retries": 2, "retry_backoff_factor": 0})
                client.session.trust_env = False
                with mock.patch("urllib3.util.connection.create_connection", side_effect=OSError("refused")) as connect:
                    with self.assertRaises(errors.AlfredConnectionError):
                        getattr(client, method)("/api/x")
                self.assertEqual(connect.call_count, 3)

    def test_connect_timeout_is_typed(self):
        client = HttpClient("http://127.0.0.1:9", API_KEY_AUTH, {"max_retries": 0})
        client.session.trust_env = False
        with mock.patch("urllib3.util.connection.create_connection", side_effect=socket.timeout("timed out")):
            with self.assertRaises(errors.AlfredConnectTimeoutError) as ctx:
                client.get("/api/x")
        self.assertIsInstance(ctx.exception, requests.exceptions.ConnectionError)
        self.assertIsInstance(ctx.exception, requests.exceptions.Timeout)

    def test_oauth_token_failure_end_to_end(self):
        server = ScriptedServer([json_item(400, {"error": "invalid_grant", "error_description": "The user is locked."})])
        self.addCleanup(server.close)
        client = HttpClient(server.url, OAUTH_AUTH, {"retry_backoff_factor": 0})
        client.session.trust_env = False
        with self.assertRaises(errors.AlfredAuthenticationError) as ctx:
            client.get("/api/x")
        self.assertEqual(ctx.exception.message, "The user is locked.")
        self.assertEqual(server.methods, ["POST"])

    def test_user_agent_reaches_the_server(self):
        seen = []

        class Echo(BaseHTTPRequestHandler):
            def do_GET(self):  # pylint: disable=invalid-name
                seen.append(self.headers.get("User-Agent"))
                self.send_response(200)
                self.send_header("Content-Length", "0")
                self.end_headers()

            def log_message(self, *args):
                pass

        httpd = ThreadingHTTPServer(("127.0.0.1", 0), Echo)
        thread = threading.Thread(target=httpd.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True)
        thread.start()

        def stop():
            httpd.shutdown()
            httpd.server_close()
            thread.join(5)

        self.addCleanup(stop)
        client = HttpClient(f"http://127.0.0.1:{httpd.server_address[1]}", API_KEY_AUTH)
        client.session.trust_env = False
        client.get("/x")
        self.assertTrue(seen[0].startswith("alfred-python"), seen)
        self.assertNotIn("python-requests", seen[0])


if __name__ == "__main__":
    unittest.main()
