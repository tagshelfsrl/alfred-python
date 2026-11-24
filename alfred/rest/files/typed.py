# Native imports
from io import BufferedReader, BytesIO
from typing import Any, Dict, List, TypedDict, Optional, Union


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


class _FileDetailsRequired(TypedDict):
    id: str
    creation_date: str
    update_date: str
    file_name: str
    file_name_without_extension: str
    # Size in bytes. `file_size` holds the same number.
    size: int
    file_size: int
    blob_name: str
    blob_url: str
    user_name: str
    # Base64 of the binary MD5 of the content.
    md5_hash: str
    content_type: str
    channel: str
    description: str
    status: str
    # single_unit, primary (split into derived files), derived (a part of a
    # primary) or virtual (a document composed from several pages).
    input_type: str
    # none, text, multimodal or reused.
    extraction_type: str
    # Classification.
    should_be_classified: bool
    exclude_from_classification_data: bool
    classifier: str
    classification_score: float
    tag_name: str
    proposed_tag_variance: float
    classification_score_above_deviation: bool
    confirmed_by: str
    manual_classification: bool
    # Duplicates.
    is_duplicate: bool
    is_data_duplicate: bool
    is_duplicate_by_values: bool
    # Structure: split documents and grouped pages.
    is_parent: bool
    page_count: int
    page_number: int
    job_order_index: int
    company_id: str
    # The file's metadata merged with its job's, as JSON text.
    effective_metadata: str
    assigned_to: str


class FileDetailsResponse(_FileDetailsRequired, total=False):
    """
    Answer of `Files.get`: every field Alfred 1.130.0 sends for a file.

    The keys of `_FileDetailsRequired` are always present (text without a
    value is sent as an empty string). The keys below are optional: either
    Alfred leaves them out when they have no value, or they were added in
    Alfred 1.130.0 and an earlier version does not send them.
    """

    # Added in Alfred 1.130.0. Always present from that version on.
    # standalone, virtual or member.
    group_role: str
    # Whether the file is classified and extracted in its own right: not a
    # parent that was split, and not a member page of a group.
    is_processing_unit: bool
    # Whether an automated result exists for the file and can be read (a
    # review may still be pending).
    is_result_ready: bool

    # Added in Alfred 1.130.0, and left out when page grouping did not run.
    group_id: str

    # Left out when they have no value.
    tag_id: str
    proposed_tag_id: str
    confirmed_tag_id: str
    duplicate_origin_id: str
    parent_id: str
    deferred_session_id: str
    assignment_date: str
    validation_date: str
    # The metadata attached to the file: the parsed JSON, or the stored text
    # when it is not valid JSON.
    metadata: Optional[Any]
