# Native imports
from typing import Any, Text

# Project imports
from src.alfred.rest.jobs.typed import CreateJobDict
from src.alfred.http.http_client import HttpClient
from src.alfred.rest.jobs.base import JobsBase


class Jobs(JobsBase):
    def __init__(self, http_client: HttpClient):
        self.http_client = http_client

    def create(self, job: CreateJobDict):
        """
        Creates a new Job.

        Args:
        - job: Job creation parameters.
        """
        return self.http_client.post("/api/job/create", data=job)

    def get(self, job_id: Text):
        """
        Fetches a Job by its ID.

        Args:
        - job_id: Unique identifier of the Job.
        """
        return self.http_client.get(f"/api/job/detail/{job_id}")
