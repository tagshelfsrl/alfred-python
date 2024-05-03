# Native imports
from io import BufferedReader, BytesIO
from typing import Dict, List, TypedDict, Optional, Union


class UploadRemoteFilePayload(TypedDict):
    url: Optional[str]
    urls: Optional[List[str]]
    source: Optional[str]
    container: Optional[str]
    filename: Optional[str]
    filenames: Optional[List[str]]
    merge: Optional[bool]
    metadata: Optional[Dict]
    propagate_metadata: Optional[bool]
    parent_file_prefix: Optional[str]


class UploadLocalFilePayload(TypedDict):
    file: Union[BufferedReader, BytesIO]
    filename: Optional[str]
    session_id: str
    metadata: Optional[Dict]


class UploadResponse(TypedDict):
    file_id: str


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
