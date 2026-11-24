import unittest

from alfred.rest.data_points import DataPointsFactory
from alfred.rest.data_points.v1 import DataPoints


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
