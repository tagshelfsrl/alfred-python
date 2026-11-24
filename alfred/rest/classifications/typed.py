# Native imports
from enum import Enum
from io import BufferedReader, BytesIO
from typing import Dict, List, Optional, TypedDict, Union


class ClassificationStatus(str, Enum):
    """
    Status of a standalone classification request, as reported by the API.
    """

    QUEUED = "queued"
    COMPLETED = "completed"
    FAILED = "failed"


class _CriterionRequired(TypedDict):
    name: str
    description: str


class ClassificationCriterion(_CriterionRequired, total=False):
    """
    One document type the caller wants the document classified against.
    `name` and `description` are required; `threshold` is optional (a number
    from 0 to 1; 0, the default, always picks).
    """

    threshold: float


class _CreateClassificationRequired(TypedDict):
    tags: List[ClassificationCriterion]
    text: str


class CreateClassificationPayload(_CreateClassificationRequired, total=False):
    """
    Text input of `Classifications.create`. `tags` and `text` are required;
    `file_name` and `correlation_id` are optional.
    """

    file_name: str
    correlation_id: str


class _CreateClassificationFileRequired(TypedDict):
    file: Union[BufferedReader, BytesIO]
    tags: List[ClassificationCriterion]


class CreateClassificationFilePayload(_CreateClassificationFileRequired, total=False):
    """
    File input of `Classifications.create_from_file`. `file` and `tags` are
    required. `filename` is needed when the file object carries no name of
    its own. `correlation_id` is optional.
    """

    filename: str
    correlation_id: str


# `class` is a Python keyword, so the dictionaries that carry it use the
# functional syntax. Keys the API always sends are declared in a total
# dictionary; the ones it can leave out are added by a `total=False` subclass.
ClassificationPrediction = TypedDict(
    "ClassificationPrediction",
    {"class": str, "score": float},
)
ClassificationPrediction.__doc__ = "One criterion's score, as the classifier gave it."

_ClassificationResultRequired = TypedDict(
    "_ClassificationResultRequired",
    {
        "class": str,
        "score": float,
        "below_threshold": bool,
        "predictions": List[ClassificationPrediction],
        "model": str,
    },
)


class ClassificationResult(_ClassificationResultRequired, total=False):
    """
    Decision of a completed request. `class` is an empty string when no
    criterion matched; `reason` (no_match, no_text, no_candidates) and
    `answered` then say why. `reasoning`, `reason` and `answered` are left
    out when empty.
    """

    reasoning: str
    reason: str
    answered: str


class ClassificationFailure(TypedDict):
    """
    The `error` block of a failed request (a dictionary, not an exception):
    `code` is classification_failed, canceled or failed.
    """

    code: str
    message: str


class ClassificationInput(TypedDict, total=False):
    """
    Input block that file requests carry once the result audit is available.
    Which keys appear depends on the input and the worker build; a key can be
    absent.
    """

    pages: int
    classified_pages: int
    pages_truncated: bool
    text_truncated: bool
    bytes: int
    mode: str
    ocr_pages: int
    native_pages: int
    ocr_provider: str


class _ClassificationResponseRequired(TypedDict):
    id: str
    file_id: str
    status: str
    created_at: str
    correlation_id: str
    text_truncated: bool


class ClassificationResponse(_ClassificationResponseRequired, total=False):
    """
    Answer of `create`, `create_from_file` (202, status queued) and `get`.
    `id` is the id of the job the request created, and `correlation_id` is an
    empty string when none was sent. `completed_at`, `result`, `error` and
    `input` appear only when they have a value.
    """

    completed_at: str
    result: ClassificationResult
    error: ClassificationFailure
    input: ClassificationInput
