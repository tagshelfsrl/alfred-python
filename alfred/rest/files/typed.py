# Native imports
from io import BufferedReader, BytesIO
from typing import Dict, List, TypedDict, Optional, Union


class UploadRemoteFilePayload(TypedDict, total=False):
    url: Optional[str]
    urls: Optional[List[str]]
    source: Optional[str]
    container: Optional[str]
    # Name of the remote file (with `url` or `source`) or names (with `urls`).
    file_name: Optional[str]
    file_names: Optional[List[str]]
    # Deprecated spellings of file_name and file_names. The API does not read
    # them; the SDK sends them under the names above.
    filename: Optional[str]
    filenames: Optional[List[str]]
    merge: Optional[bool]
    metadata: Optional[Dict]
    propagate_metadata: Optional[bool]
    parent_file_prefix: Optional[str]
    channel: Optional[str]
    # Opaque, case-sensitive caller identifier, at most 512 characters.
    correlation_id: Optional[str]
    # Password of the protected files of this request (PDF, zip, Office). At
    # most 256 bytes in UTF-8, used exactly as sent. Alfred answers 400 where
    # password-protected uploads are not enabled.
    password: Optional[str]


class UploadLocalFilePayload(TypedDict):
    file: Union[BufferedReader, BytesIO]
    filename: Optional[str]
    session_id: str
    metadata: Optional[Dict]


class UploadResponse(TypedDict):
    """Answer of `upload_file`: the file added to the deferred session."""

    file_id: str


class UploadRemoteFileResponse(TypedDict, total=False):
    """Answer of `upload`: the job created from the remote files."""

    job_id: str
    correlation_id: str
    # Advisories about the submission; only present when there are any.
    warnings: List[str]


class DownloadResponse(TypedDict):
    file: BytesIO
    original_name: str
    mime_type: str


class FileDetailsResponse(TypedDict):
    id: str
    creation_date: str
    update_date: str
    file_name: str
    file_name_without_extension: str
    blob_name: str
    blob_url: str
    user_name: Optional[str]
    md5_hash: str
    content_type: str
    channel: str
    should_be_classified: bool
    classifier: str
    classification_score: float
    status: str
    input_type: str
    is_duplicate: bool
    is_duplicate_by_values: bool
    duplicate_origin_id: Optional[str]
    tag_id: str
    is_parent: bool
    parent_id: Optional[str]
    deferred_session_id: Optional[str]
    tag_name: str
    company_id: str
    file_size: int
    proposed_tag_id: str
    proposed_tag_variance: float
    classification_score_above_deviation: bool
    confirmed_tag_id: str
    confirmed_by: str
    manual_classification: bool
    metadata: Dict
    page_count: int
    page_number: int
