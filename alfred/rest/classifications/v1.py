# Native imports
import json
import os
import uuid
from typing import Union
from urllib.parse import quote

# Project imports
from alfred.base.exceptions import AlfredMissingArgument
from alfred.http.http_client import HttpClient
from .base import ClassificationsBase
from .typed import (
    ClassificationResponse,
    CreateClassificationFilePayload,
    CreateClassificationPayload,
)
import magic


class Classifications(ClassificationsBase):
    def __init__(self, http_client: HttpClient):
        self.http_client = http_client

    def create(self, payload: CreateClassificationPayload) -> ClassificationResponse:
        parsed_resp, _ = self.http_client.post("/api/classify", data=payload)
        return parsed_resp

    def create_from_file(
        self, payload: CreateClassificationFilePayload
    ) -> ClassificationResponse:
        file = payload.get("file")
        if file is None:
            raise AlfredMissingArgument("file must be provided.")

        # An explicit filename wins over the opened file's own name: the API
        # decides the file type from the name's extension, and a caller who
        # passes a name is saying what to send.
        filename = payload.get("filename")
        if not filename:
            name = getattr(file, "name", None)
            if isinstance(name, str) and name:
                filename = os.path.basename(name)

        if not filename:
            raise AlfredMissingArgument("filename must be provided.")

        # Detect MIME type from the first bytes, then rewind.
        file.seek(0)
        content_type = magic.from_buffer(file.read(1024), mime=True)
        file.seek(0)

        data = {"tags": json.dumps(payload.get("tags"))}
        correlation_id = payload.get("correlation_id")
        if correlation_id:
            data["correlation_id"] = correlation_id

        files = {"file": (filename, file, content_type)}

        parsed_resp, _ = self.http_client.post(
            "/api/classify", data=data, files=files
        )
        return parsed_resp

    def get(self, classification_id: Union[str, uuid.UUID]) -> ClassificationResponse:
        if isinstance(classification_id, uuid.UUID):
            classification_id = str(classification_id)
        elif classification_id is None or (
            isinstance(classification_id, str) and not classification_id.strip()
        ):
            raise ValueError("classification_id must be provided.")
        elif not isinstance(classification_id, str):
            raise TypeError("classification_id must be a str or a uuid.UUID.")

        parsed_resp, _ = self.http_client.get(
            f"/api/classify/{quote(classification_id, safe='')}"
        )
        return parsed_resp
