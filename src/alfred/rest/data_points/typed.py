# Native imports
from typing import TypedDict, Text


class DataPointDict(TypedDict):
    id: Text
    file_log_id: Text
    metadata_id: Text
    metadata_name: Text
    value: Text
    classification_score: float
