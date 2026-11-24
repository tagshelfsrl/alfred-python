# Native imports
from typing import Any, Dict, List, Optional, TypedDict, Union

__all__ = [
    "DataPointValidation",
    "DataPointValidationSummary",
    "DataPointValidatorOutcome",
    "DataPointValidatorResult",
    "DataPointValue",
]


class DataPointValidatorResult(TypedDict, total=False):
    """
    One validator's result inside the object form of a value's `validation`
    block (see `DataPointValidation`). Keys are PascalCase, as Alfred stores
    them, and a key without a value is left out.
    """

    ValidatorId: str
    Type: str
    Passed: bool
    Skipped: bool
    Severity: int
    BlocksCompletion: bool
    Message: str
    Metadata: Dict[str, Any]
    DurationMs: int
    ScriptName: str
    Runtime: str


class DataPointValidationSummary(TypedDict, total=False):
    """
    Counts of the validator results of one value.
    """

    Total: int
    Passed: int
    Failed: int
    Skipped: int
    HighestSeverityFailed: str
    HasBlockingFailures: bool


class DataPointValidation(TypedDict, total=False):
    """
    Object form of a value's `validation` block: the whole validation run.
    Keys are PascalCase, unlike the rest of the row, because Alfred returns
    the record as it was stored.
    """

    Status: str
    ExecutedAt: str
    DurationMs: int
    Results: List[DataPointValidatorResult]
    Summary: DataPointValidationSummary
    Reason: str
    MustPassValidation: bool


class DataPointValidatorOutcome(TypedDict, total=False):
    """
    One validator's result in the list form of a value's `validation` block,
    where the block is the list of results itself. Keys are snake_case.
    """

    validator_id: str
    type: str
    passed: bool
    skipped: bool
    severity: Union[int, str, None]
    blocks_completion: bool
    message: Optional[str]
    metadata: Optional[Dict[str, Any]]
    reason: str


class _DataPointValueRequired(TypedDict):
    id: str
    file_log_id: str
    metadata_id: str
    metadata_name: str
    field_key: str
    value: str
    classification_score: float


class DataPointValue(_DataPointValueRequired, total=False):
    """
    One row of `DataPoints.get_values`: the value Alfred extracted for one
    data point of a file.

    `classification_score` is Alfred's confidence in the value, from 0 to 1.
    The three optional keys are present only when there is something to
    report: `extracted_value` when formatting changed the extractor's
    output, `normalized_value` when a normalised form was computed, and
    `validation` when the data point's validators ran.

    `validation` is returned as Alfred stored it. It is a
    `DataPointValidation` object or a list of `DataPointValidatorOutcome`,
    depending on the pipeline that processed the file, and the stored text
    itself when it cannot be read as JSON.
    """

    extracted_value: str
    normalized_value: str
    validation: Union[DataPointValidation, List[DataPointValidatorOutcome], str]
