from enum import Enum

from alfred.http.typed import ResponseType

# Response type/header mapping
RESPONSE_TYPE_HEADER_MAPPING = {
    ResponseType.JSON: "application/json",
    ResponseType.TEXT: "text/plain",
    ResponseType.XML: "application/xml",
}


class EventType(Enum):
    """
    Enumeration of event types.
    """
    JOB_EVENT = "job_event"
    FILE_EVENT = "file_event"


class FileEvent(Enum):
    # Triggered when a file is added to a job for processing.
    FILE_ADD_TO_JOB_EVENT = "file_add_to_job_event"

    # Occurs when a new category is created for a file.
    FILE_CATEGORY_CREATE_EVENT = "file_category_create_event"

    # Signals the deletion of a file's category.
    FILE_CATEGORY_DELETE_EVENT = "file_category_delete_event"

    # Indicates a change in the tag associated with a file.
    FILE_CHANGE_TAG_EVENT = "file_change_tag_event"

    # Marks the completion of file processing.
    FILE_DONE_EVENT = "file_done_event"

    # Triggered when new data is extracted from a file.
    FILE_EXTRACTED_DATA_CREATE_EVENT = "file_extracted_data_create_event"

    # Occurs when extracted data from a file is deleted.
    FILE_EXTRACTED_DATA_DELETE_EVENT = "file_extracted_data_delete_event"

    # Indicates a failure in file processing.
    FILE_FAILED_EVENT = "file_failed_event"

    # Signals the movement of a file within the system.
    FILE_MOVE_EVENT = "file_move_event"

    # Triggered when a file is moved to a pending state.
    FILE_MOVE_TO_PENDING_EVENT = "file_move_to_pending_event"

    # Indicates movement of a file to the recycle bin.
    FILE_MOVE_TO_RECYCLE_BIN_EVENT = "file_move_to_recycle_bin_event"

    # Reflects the creation of a file property.
    FILE_PROPERTY_CREATE_EVENT = "file_property_create_event"

    # Signals the deletion of a file property.
    FILE_PROPERTY_DELETE_EVENT = "file_property_delete_event"

    # Signals the removal of a tag from a file.
    FILE_REMOVE_TAG_EVENT = "file_remove_tag_event"

    # Indicates an update in the file's status.
    FILE_STATUS_UPDATE_EVENT = "file_status_update_event"

    # Triggered when a file is updated in any manner.
    FILE_UPDATE_EVENT = "file_update_event"


class JobEvent(Enum):
    # Triggered when a new job is instantiated for file operations.
    JOB_CREATE_EVENT = "job_create_event"

    # Fires when job exceeds maximum retry attempts for a stage.
    JOB_EXCEEDED_RETRIES_EVENT = "job_exceeded_retries_event"

    # Occurs when a job halts due to an unrecoverable error.
    JOB_FAILED_EVENT = "job_failed_event"

    # Triggered when job successfully completes all workflow stages.
    JOB_FINISHED_EVENT = "job_finished_event"

    # Fires when job fails initial validation of input files or parameters.
    JOB_INVALID_EVENT = "job_invalid_event"

    # Triggered when job retries a stage after a recoverable failure.
    JOB_RETRY_EVENT = "job_retry_event"

    # Occurs when job transitions from one workflow stage to another.
    JOB_STAGE_UPDATE_EVENT = "job_stage_update_event"

    # Triggered when job begins its workflow and state machine.
    JOB_START_EVENT = "job_start_event"
