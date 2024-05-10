from enum import Enum

from src.alfred.http.typed import ResponseType

# Response type/header mapping
RESPONSE_TYPE_HEADER_MAPPING = {
    ResponseType.JSON: "application/json",
    ResponseType.TEXT: "text/plain",
    ResponseType.XML: "application/xml",
}


class EventName(Enum):
    """
    Enumeration of event names.
    """
    JOB_EVENT = "job_event"
    FILE_EVENT = "file_event"
