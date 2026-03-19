import json
import os
import unittest
from pathlib import Path

from alfred.base.config import Configuration
from alfred.http.http_client import HttpClient
from alfred.http.typed import AuthConfiguration, HttpConfiguration
from alfred.rest.files.typed import UploadLocalFilePayload
from alfred.rest.files.v1 import Files
from alfred.rest.jobs.typed import CreateJobDict
from alfred.rest.jobs.v1 import Jobs
from alfred.rest.sessions import SessionsFactory


class TestMain(unittest.TestCase):
    _alfred_api_key = os.getenv("ALFRED_API_KEY", "").strip()
    _alfred_base_url = os.getenv("ALFRED_BASE_URL", "https://app.tagshelf.com").strip()
    _alfred_test_file_id = os.getenv("ALFRED_TEST_FILE_ID", "").strip()
    _alfred_test_upload_file = os.getenv("ALFRED_TEST_UPLOAD_FILE", "").strip()

    @classmethod
    def setUpClass(cls):
        if not cls._alfred_api_key:
            raise unittest.SkipTest(
                "Set ALFRED_API_KEY to run integration tests."
            )

        cls._config = Configuration.v1({"base_url": cls._alfred_base_url})
        cls._auth_config = AuthConfiguration(api_key=cls._alfred_api_key)
        cls._http_config = HttpConfiguration({"timeout": 10})
        cls._http_client = HttpClient(
            cls._config.get("base_url"), cls._auth_config, cls._http_config
        )
        cls._session_factory = SessionsFactory.create(
            cls._config.get("version", 1), cls._http_client
        )

    def test_get_file(self):
        """
        Run with:
        python -m unittest tests.TestMain.test_get_file
        """
        if not self._alfred_test_file_id:
            self.skipTest("Set ALFRED_TEST_FILE_ID to run this test.")

        file_service = Files(self._http_client)
        file_response = file_service.get(self._alfred_test_file_id)
        file_string_response = json.dumps(file_response, indent=2)

        print(f"File Response: \n{file_string_response}")

    def test_upload_file(self):
        """
        Run with:
        python -m unittest tests.TestMain.test_upload_file
        """
        if not self._alfred_test_upload_file:
            self.skipTest("Set ALFRED_TEST_UPLOAD_FILE to run this test.")

        file_path = Path(self._alfred_test_upload_file)
        if not file_path.exists():
            self.skipTest(f"Upload file does not exist: {file_path}")

        file_service = Files(self._http_client)
        raw_session = self._session_factory.create()
        session_id = raw_session.get("session_id")

        print(f"Session ID: {session_id}")

        with file_path.open("rb") as file:
            payload: UploadLocalFilePayload = {
                "file": file,
                "filename": file_path.name,
                "session_id": session_id,
            }

            upload_response = file_service.upload_file(payload)
            upload_string_response = json.dumps(upload_response, indent=2)
            print(f"File Upload Response: \n{upload_string_response}")

            job_service = Jobs(self._http_client)
            payload: CreateJobDict = {
                "session_id": session_id,
                "channel": "test",
            }

            job_response = job_service.create(payload)
            job_string_response = json.dumps(job_response, indent=2)
            print(f"Job Creation Response: \n{job_string_response}")


if __name__ == "__main__":
    unittest.main()
