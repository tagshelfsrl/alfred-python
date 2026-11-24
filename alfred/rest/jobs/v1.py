# Native imports
import datetime
import json
import uuid
from typing import Any, Dict, Iterable, Optional, Text, Union
from urllib.parse import quote

# Project imports
from alfred.http.http_client import HttpClient
from alfred.rest.jobs.base import DateLike, JobId, JobsBase
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

DEFAULT_PAGE = 1
DEFAULT_PAGE_SIZE = 10


class Jobs(JobsBase):
    def __init__(self, http_client: HttpClient):
        self.http_client = http_client

    def create(self, job: CreateJobDict) -> CreateJobResponseDict:
        """
        Creates a new Job.

        Args:
        - job: Job creation parameters. `correlation_id` is optional.

        Returns the 202 response: `job_id` and, when one was sent,
        `correlation_id`.
        """
        parsed_resp, _ = self.http_client.post("/api/job/create", data=job)
        return parsed_resp

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
          view needs an API key, an Account Admin or a platform Admin. The
          value is not validated here; the API answers 400 for a bad one.
        - exclude: Comma-separated string or iterable of names to leave out of
          the full view: files, metadata, fileUrls, errorMessages.

        Raises ValueError when job_id is missing or blank, and TypeError when it
        is not a str or uuid.UUID.
        """
        path_id = quote(self.__job_id(job_id), safe="")
        params: Dict[str, Any] = {}
        view_value = self.__view_value(view)
        if view_value is not None:
            params["view"] = view_value
        exclude_value = self.__exclude_value(exclude)
        if exclude_value:
            params["exclude"] = exclude_value

        parsed_resp, _ = self.http_client.get(
            f"/api/job/detail/{path_id}", params=params
        )

        wants_metadata = self.__is_full(view_value) and not self.__excludes_metadata(
            exclude_value
        )
        return self.__normalize_detail(parsed_resp, wants_metadata)

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
        if page is not None and current_page is not None and page != current_page:
            raise ValueError(
                f"page ({page!r}) and current_page ({current_page!r}) "
                "name the same thing and differ; give only one."
            )
        requested_page = page if page is not None else current_page

        params: Dict[str, Any] = {}
        # Both names are sent so the call works on Alfred 1.130.0+ (page,
        # page_size) and on older versions (currentPage, pageSize).
        if requested_page is not None:
            params["page"] = requested_page
            params["currentPage"] = requested_page
        if page_size is not None:
            params["page_size"] = page_size
            params["pageSize"] = page_size
        if sort_direction is not None:
            params["sortDirection"] = sort_direction
        if start_date is not None:
            params["startDate"] = self.__date_value(start_date, "start_date")
        if end_date is not None:
            params["endDate"] = self.__date_value(end_date, "end_date")
        if correlation_id is not None:
            params["correlation_id"] = correlation_id
        if channel is not None:
            params["channel"] = channel
        view_value = self.__view_value(view)
        if view_value is not None:
            params["view"] = view_value

        parsed_resp, _ = self.http_client.get("/api/job/all", params=params)
        return self.__normalize_page(
            parsed_resp,
            requested_page,
            page_size,
            self.__is_full(view_value),
        )

    def cancel(self, job_id: JobId) -> CancelJobResponseDict:
        """
        Cancels a Job. Returns `{"canceled": bool}`.

        Raises ValueError when job_id is missing or blank, and TypeError when it
        is not a str or uuid.UUID.
        """
        parsed_resp, _ = self.http_client.post(
            "/api/job/cancel", params={"jobId": self.__job_id(job_id)}
        )
        return parsed_resp

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
        parsed_resp, _ = self.http_client.post(
            "/api/job/restart",
            params={
                "jobId": self.__job_id(job_id),
                "redownloadRemoteFiles": "true" if redownload_remote_files else "false",
            },
        )
        return parsed_resp

    def check_sources(self, job_id: JobId) -> CheckSourcesResponseDict:
        """
        Checks whether a Job's remote sources are still reachable. Returns
        `available` and `unavailable_urls`.

        Raises ValueError when job_id is missing or blank, and TypeError when it
        is not a str or uuid.UUID.
        """
        parsed_resp, _ = self.http_client.post(
            "/api/job/check-sources", params={"jobId": self.__job_id(job_id)}
        )
        return parsed_resp

    # ------------------------------------------------------------------
    # Parameter helpers
    # ------------------------------------------------------------------

    @staticmethod
    def __job_id(job_id: Any) -> str:
        """Return the job id as stripped text; ValueError when missing or blank."""
        if isinstance(job_id, uuid.UUID):
            return str(job_id)
        if job_id is None:
            raise ValueError("job_id is required.")
        if not isinstance(job_id, str):
            raise TypeError(
                f"job_id must be a str or uuid.UUID, got {type(job_id).__name__}."
            )
        job_id = job_id.strip()
        if not job_id:
            raise ValueError("job_id is required.")
        return job_id

    @staticmethod
    def __view_value(view: Any) -> Optional[str]:
        if view is None:
            return None
        if isinstance(view, JobView):
            return view.value
        return str(view)

    @staticmethod
    def __exclude_value(exclude: Any) -> str:
        if exclude is None:
            return ""
        if isinstance(exclude, str):
            parts = exclude.split(",")
        else:
            parts = [str(part) for part in exclude]
        return ",".join(part.strip() for part in parts if part and part.strip())

    @staticmethod
    def __excludes_metadata(exclude_value: str) -> bool:
        return "metadata" in [p.lower() for p in exclude_value.split(",")]

    @staticmethod
    def __is_full(view_value: Optional[str]) -> bool:
        return view_value is not None and view_value.strip().lower() == "full"

    @staticmethod
    def __date_value(value: Any, name: str) -> str:
        # datetime is a subclass of date: test it first.
        if isinstance(value, datetime.datetime):
            return value.date().isoformat()
        if isinstance(value, datetime.date):
            return value.isoformat()
        if isinstance(value, str):
            return value
        raise TypeError(
            f"{name} must be a datetime.date, datetime.datetime or str, "
            f"got {type(value).__name__}."
        )

    # ------------------------------------------------------------------
    # Response normalization
    # ------------------------------------------------------------------

    def __normalize_detail(self, payload: Any, wants_metadata: bool) -> Any:
        """
        Normalize the response of the detail endpoint.

        A wrapped response (a job under a `result` key) is still understood.
        Anything that is not a dict is returned untouched.
        """
        if not isinstance(payload, dict):
            return payload

        result = payload.get("result")
        if isinstance(result, dict):
            response = dict(payload)
            response["result"] = self.__normalize_job(result, wants_metadata)
            return response

        return self.__normalize_job(payload, wants_metadata)

    def __normalize_page(
        self,
        payload: Any,
        requested_page: Optional[int],
        requested_page_size: Optional[int],
        wants_metadata: bool,
    ) -> Any:
        """
        Return the page envelope whatever shape the server answered with.

        New servers answer `items`/`page`/`page_size`/`total`/`has_more`; older
        ones `result`/`total`/`is_empty`, which is converted. Anything that is
        not a dict is returned untouched.
        """
        if not isinstance(payload, dict):
            return payload

        response = dict(payload)

        if "items" in response or "result" not in response:
            raw_items = response.get("items")
            legacy = False
        else:
            raw_items = response.pop("result")
            response.pop("is_empty", None)
            legacy = True

        if not isinstance(raw_items, list):
            raw_items = []
        response["items"] = [
            self.__normalize_job(item, wants_metadata) for item in raw_items
        ]

        if legacy:
            page = requested_page if requested_page is not None else DEFAULT_PAGE
            page_size = (
                requested_page_size
                if requested_page_size is not None
                else DEFAULT_PAGE_SIZE
            )
            total = response.get("total")
            total = total if isinstance(total, int) else 0
            response["page"] = page
            response["page_size"] = page_size
            response["total"] = total
            response["has_more"] = page * page_size < total

        return response

    def __normalize_job(self, job: Any, wants_metadata: bool) -> Any:
        """
        Coerce a job's metadata to a dictionary.

        A `metadata` key is never invented, except when the caller asked for
        the full view without excluding metadata (`wants_metadata`).
        """
        if not isinstance(job, dict):
            return job

        if "metadata" not in job and not wants_metadata:
            return job

        normalized_job = dict(job)
        normalized_job["metadata"] = self.__normalize_metadata(job.get("metadata"))
        return normalized_job

    @staticmethod
    def __normalize_metadata(metadata: Any) -> Dict[str, Any]:
        """
        Convert upstream job metadata into a dictionary when possible.

        Metadata arrives as a JSON-encoded string, an already parsed
        dictionary, or an empty/invalid value. Values inside the object may be
        strings, lists, records or objects and are kept as they are. A payload
        that is not a JSON object becomes an empty dictionary.
        """
        if isinstance(metadata, dict):
            return metadata

        if not metadata or not isinstance(metadata, str):
            return {}

        try:
            parsed_metadata = json.loads(metadata)
        except (TypeError, ValueError):
            return {}

        if isinstance(parsed_metadata, dict):
            return parsed_metadata

        return {}
