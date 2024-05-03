from typing import Any, List, TypedDict, Optional


class CreateJobDict(TypedDict):
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
