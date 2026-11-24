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


class ClassificationCriterion(TypedDict, total=False):
    """
    One document type the caller wants the document classified against.
    `name` and `description` are required by the API; `threshold` is optional
    (a number from 0 to 1; 0, the default, always picks).
    """

    name: str
    description: str
    threshold: float


class CreateClassificationPayload(TypedDict, total=False):
    """
    Text input of `Classifications.create`. `tags` and `text` are required by
    the API; `file_name` and `correlation_id` are optional.
    """

    tags: List[ClassificationCriterion]
    text: str
    file_name: str
    correlation_id: str


class CreateClassificationFilePayload(TypedDict, total=False):
    """
    File input of `Classifications.create_from_file`. `file` and `tags` are
    required. `filename` is required when the file object carries no name of
    its own. `correlation_id` is optional.
    """

    file: Union[BufferedReader, BytesIO]
    tags: List[ClassificationCriterion]
    filename: str
    correlation_id: str


# `class` is a Python keyword, so these two use the functional syntax.
ClassificationPrediction = TypedDict(
    "ClassificationPrediction",
    {"class": str, "score": float},
    total=False,
)
ClassificationPrediction.__doc__ = "One criterion's score, as the classifier gave it."

ClassificationResult = TypedDict(
    "ClassificationResult",
    {
        "class": str,
        "score": float,
        "below_threshold": bool,
        "predictions": List[ClassificationPrediction],
        "model": str,
        "reasoning": str,
        "reason": str,
        "answered": str,
    },
    total=False,
)
ClassificationResult.__doc__ = (
    "Decision of a completed request. `class` is an empty string when no "
    "criterion matched; `reason` (no_match, no_text, no_candidates) and "
    "`answered` then say why. `reasoning`, `reason` and `answered` are left "
    "out when empty."
)


class ClassificationFailure(TypedDict, total=False):
    """
    The `error` block of a failed request (a dictionary, not an exception): `code` is classification_failed, canceled or failed.
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


class ClassificationResponse(TypedDict, total=False):
    """
    Answer of `create`, `create_from_file` (202, status queued) and `get`.
    `id` is the id of the job the request created. `completed_at`, `result`,
    `error` and `input` appear only when they have a value.
    """

    id: str
    file_id: str
    status: str
    created_at: str
    completed_at: str
    correlation_id: str
    text_truncated: bool
    result: ClassificationResult
    error: ClassificationFailure
    input: ClassificationInput
