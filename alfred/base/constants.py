from enum import Enum

from alfred.base.typed import ResponseType

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
    """
    Values of the `event_name` field of the events that arrive on the file
    event stream (`file_event`).
    """
    # Defined by the platform; Alfred 1.130.0 does not send it.
    FILE_CREATE_EVENT = "alfred_event_file_create"

    # Triggered when a file is added to a job for processing.
    FILE_ADD_TO_JOB_EVENT = "alfred_event_file_added_to_job"

    # Occurs when a new category is created for a file.
    FILE_CATEGORY_CREATE_EVENT = "alfred_event_file_category_create"

    # Signals the deletion of a file's category.
    FILE_CATEGORY_DELETE_EVENT = "alfred_event_file_category_delete"

    # Indicates a change in the tag associated with a file.
    FILE_CHANGE_TAG_EVENT = "alfred_event_file_change_tag"

    # Signals that a file was decomposed into other files.
    FILE_DECOMPOSED_EVENT = "alfred_event_file_decomposed"

    # Marks the completion of file processing.
    FILE_DONE_EVENT = "alfred_event_file_done"

    # Triggered when new data is extracted from a file.
    FILE_EXTRACTED_DATA_CREATE_EVENT = "alfred_event_file_extracted_data_create"

    # Occurs when extracted data from a file is deleted.
    FILE_EXTRACTED_DATA_DELETE_EVENT = "alfred_event_file_extracted_data_delete"

    # Indicates a failure in file processing.
    FILE_FAILED_EVENT = "alfred_event_file_failed"

    # Signals the movement of a file within the system.
    FILE_MOVE_EVENT = "alfred_event_file_move"

    # Triggered when a file is moved to the decomposed state.
    FILE_MOVE_TO_DECOMPOSED_EVENT = "alfred_event_file_move_to_decomposed"

    # Triggered when a file is moved to a pending state.
    FILE_MOVE_TO_PENDING_EVENT = "alfred_event_file_move_to_pending"

    # Indicates movement of a file to the recycle bin.
    FILE_MOVE_TO_RECYCLE_BIN_EVENT = "alfred_event_file_move_to_recycle_bin"

    # Reflects the creation of a file property.
    FILE_PROPERTY_CREATE_EVENT = "alfred_event_file_property_create"

    # Signals the deletion of a file property.
    FILE_PROPERTY_DELETE_EVENT = "alfred_event_file_property_delete"

    # Alfred sends a tag removal under the change-tag name, so this is an alias
    # of FILE_CHANGE_TAG_EVENT. A removal carries `tag_being_removed_id`.
    FILE_REMOVE_TAG_EVENT = "alfred_event_file_change_tag"

    # Indicates an update in the file's status.
    FILE_STATUS_UPDATE_EVENT = "alfred_event_file_status_update"

    # Defined by the platform; Alfred 1.130.0 does not send it.
    FILE_UPDATE_EVENT = "alfred_event_file_update"


class JobEvent(Enum):
    """
    Values of the `event_name` field of the events that arrive on the job
    event stream (`job_event`).
    """
    # Triggered when a new job is instantiated for file operations.
    JOB_CREATE_EVENT = "alfred_event_job_create"

    # Triggered when job begins its workflow and state machine.
    JOB_START_EVENT = "alfred_event_job_start"

    # Occurs when job transitions from one workflow stage to another.
    JOB_STAGE_UPDATE_EVENT = "alfred_event_job_stage_update"

    # Sent after JOB_FAILED_EVENT when the job has used up its retries
    # (`exceeded_retries` is true). Despite the name, Alfred 1.130.0 does not
    # send it when a job is retried.
    JOB_RETRY_EVENT = "alfred_event_job_retry"

    # Alfred has no separate name for a job that has used up its retries: it is
    # sent under the retry name, so this is an alias of JOB_RETRY_EVENT.
    JOB_EXCEEDED_RETRIES_EVENT = "alfred_event_job_retry"

    # Fires when job fails initial validation of input files or parameters.
    JOB_INVALID_EVENT = "alfred_event_job_invalid"

    # Occurs when a job halts due to an unrecoverable error.
    JOB_FAILED_EVENT = "alfred_event_job_failed"

    # Triggered when a job is cancelled.
    JOB_CANCELLED_EVENT = "alfred_event_job_cancelled"

    # Triggered when a job expires.
    JOB_EXPIRED_EVENT = "alfred_event_job_expired"

    # Triggered when job successfully completes all workflow stages.
    JOB_FINISHED_EVENT = "alfred_event_job_finished"


# Event names used by earlier SDK versions, mapped to the name Alfred sends.
LEGACY_EVENT_NAMES = {
    "file_add_to_job_event": "alfred_event_file_added_to_job",
    "file_category_create_event": "alfred_event_file_category_create",
    "file_category_delete_event": "alfred_event_file_category_delete",
    "file_change_tag_event": "alfred_event_file_change_tag",
    "file_done_event": "alfred_event_file_done",
    "file_extracted_data_create_event": "alfred_event_file_extracted_data_create",
    "file_extracted_data_delete_event": "alfred_event_file_extracted_data_delete",
    "file_failed_event": "alfred_event_file_failed",
    "file_move_event": "alfred_event_file_move",
    "file_move_to_pending_event": "alfred_event_file_move_to_pending",
    "file_move_to_recycle_bin_event": "alfred_event_file_move_to_recycle_bin",
    "file_property_create_event": "alfred_event_file_property_create",
    "file_property_delete_event": "alfred_event_file_property_delete",
    "file_remove_tag_event": "alfred_event_file_change_tag",
    "file_status_update_event": "alfred_event_file_status_update",
    "file_update_event": "alfred_event_file_update",
    "job_create_event": "alfred_event_job_create",
    "job_exceeded_retries_event": "alfred_event_job_retry",
    "job_failed_event": "alfred_event_job_failed",
    "job_finished_event": "alfred_event_job_finished",
    "job_invalid_event": "alfred_event_job_invalid",
    "job_retry_event": "alfred_event_job_retry",
    "job_stage_update_event": "alfred_event_job_stage_update",
    "job_start_event": "alfred_event_job_start",
}
