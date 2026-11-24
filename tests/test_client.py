import unittest
from unittest.mock import patch

from alfred.base.config import Configuration
from alfred.rest import AlfredClient
from alfred.rest.data_points.v1 import DataPoints
from alfred.rest.files.v1 import Files
from alfred.rest.jobs.v1 import Jobs
from alfred.rest.sessions.v1 import Sessions

DEFAULT_HTTP_CONFIG = {"max_retries": 3, "pool_connections": True, "timeout": 5}


class RecordingHttpClient:
    """
    Records every get/post call as (uri, params, data, files, headers)
    and answers with a scripted (parsed, response) tuple.
    """

    def __init__(self):
        self.get_calls = []
        self.post_calls = []

    def get(self, uri, params=None, data=None, headers=None, files=None, timeout=None):
        self.get_calls.append((uri, params, data, files, headers))
        return None, None

    def post(self, uri, params=None, data=None, headers=None, files=None, timeout=None):
        self.post_calls.append((uri, params, data, files, headers))
        return None, None


def _unsupported_version_config():
    config = Configuration.v1()
    config["version"] = 2
    return config


class TestAlfredClientDomains(unittest.TestCase):
    def setUp(self):
        self.http_client = RecordingHttpClient()
        self.client = AlfredClient(
            Configuration.v1(), {"api_key": "key-1"}, http_client=self.http_client
        )

    def test_jobs_property_returns_v1_jobs_bound_to_supplied_http_client(self):
        jobs = self.client.jobs

        self.assertIsInstance(jobs, Jobs)
        self.assertIs(jobs.http_client, self.http_client)

    def test_jobs_property_returns_same_instance_on_second_access(self):
        self.assertIs(self.client.jobs, self.client.jobs)

    def test_files_property_returns_v1_files_bound_to_supplied_http_client(self):
        files = self.client.files

        self.assertIsInstance(files, Files)
        self.assertIs(files.http_client, self.http_client)

    def test_files_property_returns_same_instance_on_second_access(self):
        self.assertIs(self.client.files, self.client.files)

    def test_sessions_property_returns_v1_sessions_bound_to_supplied_http_client(self):
        sessions = self.client.sessions

        self.assertIsInstance(sessions, Sessions)
        self.assertIs(sessions.http_client, self.http_client)

    def test_sessions_property_returns_same_instance_on_second_access(self):
        self.assertIs(self.client.sessions, self.client.sessions)

    def test_data_points_property_returns_v1_data_points_bound_to_supplied_http_client(self):
        data_points = self.client.data_points

        self.assertIsInstance(data_points, DataPoints)
        self.assertIs(data_points.http_client, self.http_client)

    def test_data_points_property_returns_same_instance_on_second_access(self):
        self.assertIs(self.client.data_points, self.client.data_points)

    def test_domain_properties_do_not_issue_http_requests(self):
        self.client.jobs
        self.client.files
        self.client.sessions
        self.client.data_points

        self.assertEqual(self.http_client.get_calls, [])
        self.assertEqual(self.http_client.post_calls, [])


class TestAlfredClientUnsupportedVersion(unittest.TestCase):
    def setUp(self):
        self.client = AlfredClient(
            _unsupported_version_config(),
            {"api_key": "key-1"},
            http_client=RecordingHttpClient(),
        )

    def test_jobs_with_unsupported_version_raises_value_error(self):
        with self.assertRaises(ValueError) as ctx:
            self.client.jobs

        self.assertEqual(str(ctx.exception), "Unsupported version: 2")

    def test_files_with_unsupported_version_raises_value_error(self):
        with self.assertRaises(ValueError) as ctx:
            self.client.files

        self.assertEqual(str(ctx.exception), "Unsupported version: 2")

    def test_sessions_with_unsupported_version_raises_plain_exception(self):
        with self.assertRaises(Exception) as ctx:
            self.client.sessions

        self.assertIs(type(ctx.exception), Exception)

    def test_data_points_with_unsupported_version_raises_plain_exception(self):
        with self.assertRaises(Exception) as ctx:
            self.client.data_points

        self.assertIs(type(ctx.exception), Exception)


class TestAlfredClientHttpClientConstruction(unittest.TestCase):
    def test_builds_http_client_from_config_base_url_auth_and_default_http_config(self):
        auth_config = {"api_key": "key-1"}
        with patch("alfred.rest.HttpClient") as http_client_cls:
            client = AlfredClient(Configuration.v1(), auth_config)

        http_client_cls.assert_called_once_with(
            "https://app.tagshelf.com", auth_config, DEFAULT_HTTP_CONFIG
        )
        self.assertIs(client.http_client, http_client_cls.return_value)

    def test_builds_http_client_against_overridden_base_url(self):
        auth_config = {"api_key": "key-1"}
        config = Configuration.v1({"base_url": "https://staging.example.test"})
        with patch("alfred.rest.HttpClient") as http_client_cls:
            AlfredClient(config, auth_config)

        http_client_cls.assert_called_once_with(
            "https://staging.example.test", auth_config, DEFAULT_HTTP_CONFIG
        )

    def test_supplied_http_config_replaces_default_http_config(self):
        auth_config = {"api_key": "key-1"}
        custom_http_config = {"timeout": 30, "max_retries": 1}
        with patch("alfred.rest.HttpClient") as http_client_cls:
            AlfredClient(Configuration.v1(), auth_config, http_config=custom_http_config)

        http_client_cls.assert_called_once_with(
            "https://app.tagshelf.com", auth_config, custom_http_config
        )

    def test_supplied_http_client_skips_building_a_new_one(self):
        supplied = RecordingHttpClient()
        with patch("alfred.rest.HttpClient") as http_client_cls:
            client = AlfredClient(Configuration.v1(), {"api_key": "key-1"}, http_client=supplied)

        http_client_cls.assert_not_called()
        self.assertIs(client.http_client, supplied)


if __name__ == "__main__":
    unittest.main()
