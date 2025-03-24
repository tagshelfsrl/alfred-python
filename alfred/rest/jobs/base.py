# Native imports
from typing import Text, Any
from alfred.rest.jobs.typed import CreateJobDict
from abc import ABC, abstractmethod


class JobsBase(ABC):
    @abstractmethod
    def create(self, job: CreateJobDict) -> Any:
        """
        Creates a new Job.

        Args:
        - job: Job creation parameters.
        """

    @abstractmethod
    def get(self, job_id: Text) -> Any:
        """
        Fetches a Job by its ID.

        Args:
        - job_id: Unique identifier of the Job.
        """

    @abstractmethod
    def get_all(self, page_size: int = None, current_page: int = None) -> Any:
        """
        Fetches all jobs for a company

        Args:
        - page_size: Number of jobs to fetch per page.
        - current_page: Page number to fetch.
        """
