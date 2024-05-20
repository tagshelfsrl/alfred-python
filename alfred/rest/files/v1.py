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

        if isinstance(file, BufferedReader):
            filename = os.path.basename(file.name)

        if not filename:
            raise AlfredMissingArgument("filename must be provided.")

        files = [
            ("file", (filename, file, "application/octet-stream")),
            ("session_id", (None, payload["session_id"], "text/plain")),
            (
                "metadata",
                (None, json.dumps(payload.get("metadata")), "application/json"),
            ),
        ]

        parsed_resp, _ = self.http_client.post(
            "/api/file/uploadfile",
            files=files,
            headers={"content-type": None},
        )
        return parsed_resp

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
