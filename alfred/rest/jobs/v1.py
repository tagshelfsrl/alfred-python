# Native imports
import json
from typing import Any, Dict, Text

# Project imports
from alfred.rest.jobs.typed import CreateJobDict
from alfred.http.http_client import HttpClient
from alfred.rest.jobs.base import JobsBase


class Jobs(JobsBase):
    def __init__(self, http_client: HttpClient):
        self.http_client = http_client

    def create(self, job: CreateJobDict):
        """
        Creates a new Job.

        Args:
        - job: Job creation parameters.
        """
        parsed_resp, _ = self.http_client.post("/api/job/create", data=job)
        return parsed_resp

    def get(self, job_id: Text):
        """
        Fetches a Job by its ID.

        Args:
        - job_id: Unique identifier of the Job.
        """
        parsed_resp, _ = self.http_client.get(f"/api/job/detail/{job_id}")
        return self.__normalize_job_response(parsed_resp)

    def get_all(self, page_size: int = None, current_page: int = None):
        """
        Fetches all jobs for a company

        Args:
        - page_size: Number of jobs to fetch per page.
        - current_page: Page number to fetch.
        """
        params = {}
        if page_size:
            params["pageSize"] = page_size
        if current_page:
            params["currentPage"] = current_page
        parsed_resp, _ = self.http_client.get("/api/job/all", params=params)
        return self.__normalize_job_response(parsed_resp)

    def __normalize_job_response(self, payload: Any):
        """
        Normalize job payloads returned by job endpoints.

        Supports direct job objects as well as wrapped responses where jobs
        are returned under a `result` key.
        """
        if isinstance(payload, list):
            return [self.__normalize_job(item) for item in payload]

        if not isinstance(payload, dict):
            return payload

        response = dict(payload)
        result = response.get("result")

        if isinstance(result, list):
            response["result"] = [self.__normalize_job(item) for item in result]
            return response

        if isinstance(result, dict):
            response["result"] = self.__normalize_job(result)
            return response

        return self.__normalize_job(response)

    def __normalize_job(self, job: Any):
        """
        Normalize a single job object and coerce its metadata to a dictionary.
        """
        if not isinstance(job, dict):
            return job

        normalized_job = dict(job)
        normalized_job["metadata"] = self.__normalize_metadata(
            normalized_job.get("metadata")
        )
        return normalized_job

    @staticmethod
    def __normalize_metadata(metadata: Any) -> Dict[str, Any]:
        """
        Convert upstream job metadata into a dictionary when possible.

        Metadata may arrive as a JSON-encoded string, an already parsed
        dictionary, or an empty/invalid value. Non-dictionary results are
        normalized to an empty dictionary.
        """
        if isinstance(metadata, dict):
            return metadata

        if not metadata or not isinstance(metadata, str):
            return {}

        try:
            parsed_metadata = json.loads(metadata)
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}

        if isinstance(parsed_metadata, dict):
            return parsed_metadata

        return {}
