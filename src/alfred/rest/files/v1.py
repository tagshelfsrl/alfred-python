# Native imports
from typing import Text
from io import BytesIO, FileIO
from urllib.parse import unquote

# Project imports
from alfred.rest.files.typed import *  # pylint: disable=W0401, W0614
from src.alfred.http.http_client import HttpClient
from src.alfred.base.exceptions import AlfredMissingArgument
from .base import FilesBase
from .typed import FileDetailsResponse


class Files(FilesBase):
    def __init__(self, http_client: HttpClient):
        self.http_client = http_client

    def get(self, file_id: Text) -> FileDetailsResponse:
        return self.http_client.get(f"/api/file/detail/{file_id}")

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
        return self.http_client.post("/api/file/upload", data=payload)

    def upload_file(self, payload: UploadLocalFilePayload) -> UploadResponse:
        file = payload.get("file")
        files = {}

        if isinstance(file, BytesIO):
            filename = payload.get("filename")
            if not filename:
                raise AlfredMissingArgument(
                    "filename is required when providing a BytesIO file."
                )

            files["file"] = (filename, file)
        elif isinstance(file, FileIO):
            files["file"] = file

        data = {key: value for key, value in payload.items() if key != "file"}

        return self.http_client.post("/api/file/uploadfile", data=data, files=files)

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
