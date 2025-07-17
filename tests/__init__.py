import unittest
import json
from pathlib import Path
from alfred.base.config import Configuration
from alfred.http.typed import AuthConfiguration, HttpConfiguration
from alfred.http.http_client import HttpClient
from alfred.rest.files.typed import UploadLocalFilePayload
from alfred.rest.files.v1 import Files
from alfred.rest.jobs.typed import CreateJobDict
from alfred.rest.sessions import SessionsFactory
from alfred.rest.jobs.v1 import Jobs

class TestMain(unittest.TestCase):

    _alfred_api_key = "" # Insert your API key here    <--------------------
    _alfred_base_url = "http://localhost:18036" # Localhost URL for testing

    if not _alfred_api_key.strip():
        raise ValueError("ALFRED_API_KEY must be set for integration tests.")
    
    # Local test configuration
    _config = Configuration.v1({"base_url": _alfred_base_url})
    _auth_config = AuthConfiguration(
        api_key= _alfred_api_key
    )
    _http_config = HttpConfiguration({"timeout": 10})
    _http_client = HttpClient(_config.get("base_url"), _auth_config, _http_config)
    _session_factory = SessionsFactory.create(_config.get("version", 1), _http_client)

    """
    To run this test you can execute the following command:
    python -m unittest tests.TestMain.test_get_file
    """
    def test_get_file(self):
        """
        Test case for getting a file by ID.
        """
        file_id = "" # Insert your file ID here    <--------------------

        if not file_id.strip():
            raise ValueError("You must set a valid file_id to run this test.")
    
        file_service = Files(self._http_client)
        
        file_response = file_service.get(file_id)
        file_string_response = json.dumps(file_response, indent=2)

        print(f"File Response: \n{file_string_response}")

    """
    To run this test you can execute the following command:
    python -m unittest tests.TestMain.test_upload_file
    """
    def test_upload_file(self):
        """
        Test case for uploading a local file.
        """
        fileService = Files(self._http_client)
        raw_session = self._session_factory.create()
        session_id = raw_session.get("session_id")

        print(f"Session ID: {session_id}")

        file_path = Path(__file__).parent / "test_files" / "file-name.jpeg"
        with file_path.open("rb") as file:
            
            payload: UploadLocalFilePayload = {
                "file": file,
                "filename": "file-name",
                "session_id": session_id
            }
            
            upload_response = fileService.upload_file(payload)
            upload_string_response = json.dumps(upload_response, indent=2)
            print(f"File Upload Response: \n{upload_string_response}")

            job_service = Jobs(self._http_client)

            payload: CreateJobDict = {
                "session_id": session_id,
                "channel": "test"
            }

            job_response = job_service.create(payload)
            job_string_response = json.dumps(job_response, indent=2)
            print(f"Job Creation Response: \n{job_string_response}")

if __name__ == '__main__':
    unittest.main()

"""
Notes:
To run these tests locally, ensure you have the following:
1. A running Alfred server instance.
2. The `ALFRED_API_KEY` environment variable set with your API key.
3. Azurite as a local storage emulator if you're testing file uploads.
4. The test files located in the `tests/test_files` directory.
"""
