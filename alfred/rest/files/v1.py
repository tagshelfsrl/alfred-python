# Native imports
import os
import json
from typing import Text
from urllib.parse import unquote

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

    def upload(self, payload: UploadRemoteFilePayload) -> UploadResponse:
        parsed_resp, _ = self.http_client.post("/api/file/upload", data=payload)
        return parsed_resp

    def upload_file(self, payload: UploadLocalFilePayload) -> UploadResponse:
        file = payload.get("file")
        filename = payload.get("filename")
        session_id = payload.get("session_id")
        metadata = payload.get("metadata", {})

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
        filename = None
        if "filename*" in content_disposition:
            filename = content_disposition.split("filename*=UTF-8''")[-1]
            filename = unquote(filename)
        elif "filename=" in content_disposition:
            filename = content_disposition.split("filename=")[-1]
            filename = filename.strip("\"'")

        return filename
