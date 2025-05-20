# Native imports
from typing import Text

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
        return parsed_resp

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
        return parsed_resp
