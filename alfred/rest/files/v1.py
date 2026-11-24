# Native imports
import os
import json
from email.message import Message
from email.utils import collapse_rfc2231_value
from typing import Text

# Project imports
from alfred.rest.files.typed import *  # pylint: disable=W0401, W0614
from alfred.http.http_client import HttpClient
from alfred.base.exceptions import AlfredMissingArgument
from .base import FilesBase
from .typed import FileDetailsResponse
import magic

class Files(FilesBase):
    def __init__(self, http_client: HttpClient):
        self.http_client = http_client

    def get(self, file_id: Text) -> FileDetailsResponse:
        parsed_resp, _ = self.http_client.get(f"/api/file/detail/{file_id}")
        return parsed_resp

    def download(self, file_id: Text) -> DownloadResponse:
        _, response = self.http_client.get(f"/api/file/download/{file_id}")
        file = BytesIO(response.content)
        mime_type = response.headers.get("Content-Type")
        original_name = self.__extract_filename(
            response.headers.get("Content-Disposition")
        )

        return {
            "file": file,
            "mime_type": mime_type,
            "original_name": original_name,
        }

    def upload(self, payload: UploadRemoteFilePayload) -> UploadRemoteFileResponse:
        parsed_resp, _ = self.http_client.post(
            "/api/file/upload", data=self.__with_api_names(payload)
        )
        return parsed_resp

    @staticmethod
    def __with_api_names(payload):
        """
        The API reads the names of remote files from `file_name` and
        `file_names`. Earlier versions of this SDK documented `filename` and
        `filenames`, which the API ignores: send those under the names it
        reads. A value given under the API's own name wins. The caller's
        payload is not modified.
        """
        if not isinstance(payload, dict):
            return payload

        body = dict(payload)
        for legacy_name, api_name in (("filename", "file_name"), ("filenames", "file_names")):
            if legacy_name in body:
                value = body.pop(legacy_name)
                body.setdefault(api_name, value)
        return body

    def upload_file(self, payload: UploadLocalFilePayload) -> UploadResponse:
        file = payload.get("file")
        filename = payload.get("filename")
        session_id = payload.get("session_id")
        # A missing or null metadata is sent as an empty object, not as "null".
        metadata = payload.get("metadata") or {}

        # Detect MIME type
        content_type = magic.from_buffer(file.read(1024), mime=True)
        file.seek(0)  # reset pointer

        if isinstance(file, BufferedReader):
            filename = os.path.basename(file.name)

        if not filename:
            raise AlfredMissingArgument("filename must be provided.")

        files = {
            "file": (filename, file, content_type)
        }

        data = {
            "session_id": session_id,
            "metadata": json.dumps(metadata)
        }

        parsed_response, _ = self.http_client.post(
            "/api/file/uploadfile",
            data=data,
            files=files
        )

        return parsed_response

    def __extract_filename(self, content_disposition: Text):
        """
        Extract the file name from the Content-Disposition header.
        If no file name present, None would be returned.

        Args:
        - content_disposition: Value of the Content-Disposition header.
        """
        if not content_disposition:
            return None

        message = Message()
        message["Content-Disposition"] = content_disposition

        plain_filename = None
        for name, value in message.get_params(header="content-disposition", failobj=[]):
            if name.lower() != "filename":
                continue
            if isinstance(value, tuple):
                # The encoded form (`filename*`, RFC 5987) wins over the plain
                # one when both are sent (RFC 6266, section 4.3).
                return collapse_rfc2231_value(value).strip() or None
            if plain_filename is None:
                plain_filename = value

        if not plain_filename:
            return None
        return plain_filename.strip() or None
