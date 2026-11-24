import unittest

from alfred.rest.sessions import SessionsFactory
from alfred.rest.sessions.v1 import Sessions


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


class TestSessions(unittest.TestCase):
    def test_create_posts_to_deferred_create_route(self):
        client = RecordingHttpClient(post_result=({"session_id": "s1"}, None))

        Sessions(client).create()

        self.assertEqual(client.post_calls, [("/api/deferred/create", None, None, None, None)])

    def test_create_returns_parsed_body(self):
        client = RecordingHttpClient(post_result=({"session_id": "s1"}, None))

        result = Sessions(client).create()

        self.assertEqual(result, {"session_id": "s1"})

    def test_get_requests_deferred_detail_route_with_session_id(self):
        client = RecordingHttpClient(get_result=({"id": "s1"}, None))

        Sessions(client).get("s1")

        self.assertEqual(client.get_calls, [("/api/deferred/detail/s1", None, None, None, None)])
        self.assertEqual(client.post_calls, [])

    def test_get_returns_parsed_body(self):
        client = RecordingHttpClient(get_result=({"id": "s1", "status": "open"}, None))

        result = Sessions(client).get("s1")

        self.assertEqual(result, {"id": "s1", "status": "open"})


class TestSessionsFactory(unittest.TestCase):
    def test_create_version_1_returns_sessions_bound_to_http_client(self):
        client = RecordingHttpClient()

        result = SessionsFactory.create(1, client)

        self.assertIsInstance(result, Sessions)
        self.assertIs(result.http_client, client)

    def test_create_unsupported_version_raises_plain_exception(self):
        with self.assertRaises(Exception) as ctx:
            SessionsFactory.create(2, RecordingHttpClient())

        self.assertIs(type(ctx.exception), Exception)
        self.assertEqual(str(ctx.exception), "Unsupported version for the specified domain.")


if __name__ == "__main__":
    unittest.main()
