# Native imports
import datetime
import uuid
from abc import ABC, abstractmethod
from typing import Iterable, Optional, Text, Union

# Project imports
from alfred.rest.jobs.typed import (
    CancelJobResponseDict,
    CheckSourcesResponseDict,
    CreateJobDict,
    CreateJobResponseDict,
    JobFullDict,
    JobPageDict,
    JobSummaryDict,
    JobView,
    RestartJobResponseDict,
)

JobId = Union[Text, uuid.UUID]
DateLike = Union[datetime.date, datetime.datetime, Text]


class JobsBase(ABC):
    @abstractmethod
    def create(self, job: CreateJobDict) -> CreateJobResponseDict:
        """
        Creates a new Job.

        Args:
        - job: Job creation parameters. `correlation_id` is optional.

        Returns the 202 response: `job_id` and, when one was sent,
        `correlation_id`.
        """

    @abstractmethod
    def get(
        self,
        job_id: JobId,
        view: Optional[Union[JobView, Text]] = None,
        exclude: Optional[Union[Text, Iterable[Text]]] = None,
    ) -> Union[JobSummaryDict, JobFullDict]:
        """
        Fetches a Job by its ID.

        Args:
        - job_id: Unique identifier of the Job (str or uuid.UUID).
        - view: "summary" or "full" (or a JobView). None sends nothing, so the
          API default applies: a summary on Alfred 1.130.0 and later. The full
          view needs an API key, an Account Admin or a platform Admin.
        - exclude: Comma-separated string or iterable of names to leave out of
          the full view: files, metadata, fileUrls, errorMessages.

        Raises ValueError when job_id is missing or blank, and TypeError when it
        is not a str or uuid.UUID.
        """

    @abstractmethod
    def get_all(
        self,
        page_size: Optional[int] = None,
        current_page: Optional[int] = None,
        *,
        page: Optional[int] = None,
        sort_direction: Optional[Text] = None,
        start_date: Optional[DateLike] = None,
        end_date: Optional[DateLike] = None,
        correlation_id: Optional[Text] = None,
        channel: Optional[Text] = None,
        view: Optional[Union[JobView, Text]] = None,
    ) -> JobPageDict:
        """
        Fetches one page of the company's jobs, newest-updated first by default.

        Always returns the page envelope `items`, `page`, `page_size`, `total`,
        `has_more`, even when Alfred is older than 1.130.0 and answers with
        `result`, `total`, `is_empty`.

        Args:
        - page_size: Items per page (the API accepts 10 to 100).
        - current_page: Page number, from 1.
        - page: Same as current_page. Giving both with different values raises
          ValueError.
        - sort_direction: "ASC" or "DESC".
        - start_date, end_date: datetime.date, datetime.datetime (its calendar
          date is used) or a string; sent as YYYY-MM-DD. The API rejects an
          end date without a start date, and future dates.
        - correlation_id: Exact, case-sensitive match.
        - channel: Only jobs of this channel.
        - view: "summary" or "full" (or a JobView); see `get`.
        """

    @abstractmethod
    def cancel(self, job_id: JobId) -> CancelJobResponseDict:
        """
        Cancels a Job. Returns `{"canceled": bool}`.

        Raises ValueError when job_id is missing or blank, and TypeError when it
        is not a str or uuid.UUID.
        """

    @abstractmethod
    def restart(
        self, job_id: JobId, redownload_remote_files: bool = False
    ) -> RestartJobResponseDict:
        """
        Restarts a Job. Returns `{"restarted": bool}`.

        Args:
        - job_id: Unique identifier of the Job.
        - redownload_remote_files: Download remote sources again.

        Raises ValueError when job_id is missing or blank, and TypeError when it
        is not a str or uuid.UUID.
        """

    @abstractmethod
    def check_sources(self, job_id: JobId) -> CheckSourcesResponseDict:
        """
        Checks whether a Job's remote sources are still reachable. Returns
        `available` and `unavailable_urls`.

        Raises ValueError when job_id is missing or blank, and TypeError when it
        is not a str or uuid.UUID.
        """
