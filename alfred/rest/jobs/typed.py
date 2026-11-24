from enum import Enum
from typing import Any, Dict, List, Optional, TypedDict


class JobView(str, Enum):
    """
    How much of a job the API returns (Alfred 1.130.0 and later).

    - SUMMARY: a short, fixed set of fields. This is the API default.
    - FULL: the job's complete record. Needs an API key, an Account Admin or a
      platform Admin.
    """

    SUMMARY = "summary"
    FULL = "full"


class CreateJobDict(TypedDict, total=False):
    session_id: Optional[str]
    propagate_metadata: Optional[bool]
    merge: Optional[bool]
    decompose: Optional[bool]
    metadata: Optional[Any]
    channel: Optional[str]
    parent_file_prefix: Optional[str]
    page_rotation: Optional[int]
    container: Optional[str]
    file_name: Optional[str]
    file_names: Optional[List[str]]
    # Opaque, case-sensitive caller identifier, at most 512 characters after
    # trimming. Alfred does not deduplicate jobs on it.
    correlation_id: Optional[str]
    # Password of the job's protected files (PDF, zip, Office). At most 256
    # bytes in UTF-8, used exactly as sent. Alfred answers 400 where
    # password-protected uploads are not enabled.
    password: Optional[str]


class CreateJobResponseDict(TypedDict, total=False):
    job_id: str
    # Omitted by the API when the job was created without a correlation id.
    correlation_id: Optional[str]


class JobSummaryDict(TypedDict, total=False):
    """A job's summary: the default view, also each item of a default page."""

    id: str
    correlation_id: str
    stage: str
    channel: str
    priority: str
    user_name: str
    file_sources_count: int
    file_count: int
    finished_files: int
    has_failed_files: bool
    failed_files_count: int
    has_confirmation_required_files: bool
    confirmation_required_files_count: int
    retries: int
    exceeded_retries: bool
    merge: bool
    decompose: bool
    propagate_metadata: bool
    creation_date: str
    update_date: str
    start_date: str


class JobFileDict(TypedDict, total=False):
    """One entry of a full view's `files`."""

    id: str
    creation_date: str
    update_date: str
    file_name: str
    content_type: str
    tag_name: str
    is_parent: bool
    group_role: str
    group_id: str
    is_processing_unit: bool
    is_result_ready: bool
    parent_id: str
    is_children: bool
    status: str
    is_reextracting: bool


class JobFullDict(TypedDict, total=False):
    """
    A job's full view (`view="full"`).

    `metadata` is a JSON text string on the wire; this SDK parses it into a
    dict. `priority` is the .NET name (for example "High"), unlike the
    summary's snake_case value. The full view has no `failed_files_count`,
    `has_confirmation_required_files` or `confirmation_required_files_count`.
    In a page, `files`, `file_urls`, `error_messages`,
    `last_cancellation_date`, `remote_sources_available` and
    `unavailable_source_urls` are not sent.
    """

    id: str
    cancellation_reason: str
    last_canceled_by: str
    last_cancellation_date: str
    company_id: str
    bulk_id: str
    deferred_session_id: str
    user_name: str
    channel: str
    correlation_id: str
    source: str
    container: str
    remote_file_name: str
    merge: bool
    decompose: bool
    propagate_metadata: bool
    parent_file_prefix: str
    metadata: Dict[str, Any]
    file_count: int
    total_file_count: int
    file_sources_count: int
    metadata_objects_count: int
    finished_files: int
    files: List[JobFileDict]
    retries: int
    cancel_count: int
    restart_count: int
    cached_restart_count: int
    redownload_restart_count: int
    restarted_by: str
    restarted_at: str
    exceeded_retries: bool
    file_urls: List[str]
    error_messages: List[str]
    stage: str
    remote_sources_available: bool
    unavailable_source_urls: List[str]
    priority: str
    start_date: str
    has_failed_files: bool
    has_broken_input_sources: bool
    creation_date: str
    update_date: str


class JobPageDict(TypedDict, total=False):
    """
    The page envelope returned by `Jobs.get_all`. `items` holds
    `JobSummaryDict` entries, or `JobFullDict` entries when `view="full"`.
    """

    items: List[Dict[str, Any]]
    page: int
    page_size: int
    total: int
    has_more: bool


class CancelJobResponseDict(TypedDict):
    canceled: bool


class RestartJobResponseDict(TypedDict, total=False):
    restarted: bool


class CheckSourcesResponseDict(TypedDict, total=False):
    available: bool
    # Serialized as `unavailable_urls` (snake_case); omitted when empty/null.
    unavailable_urls: List[str]
