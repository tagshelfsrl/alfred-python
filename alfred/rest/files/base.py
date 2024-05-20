# Native imports
from typing import Text
from abc import ABC, abstractmethod

# Project imports
from .typed import (
    UploadLocalFilePayload,
    UploadRemoteFilePayload,
    UploadResponse,
    DownloadResponse,
    FileDetailsResponse,
)


class FilesBase(ABC):
    @abstractmethod
    def get(self, file_id: Text) -> FileDetailsResponse:
        """
        Fetch file details by ID.

        Args:
        - file_id: Unique identifier of the File.
        """

    @abstractmethod
    def download(self, file_id: Text) -> DownloadResponse:
        """
        Download file by ID. Returns an object with a binary
        of the file, along with its name and mime type.

        Args:
        - file_id: Unique identifier of the Job.
        """

    @abstractmethod
    def upload(self, payload: UploadRemoteFilePayload) -> UploadResponse:
        """
        Upload a remote file (URL or blob).

        Args:
        - payload: Payload with remote file details and Alfred's properties.
        """

    @abstractmethod
    def upload_file(self, payload: UploadLocalFilePayload) -> UploadResponse:
        """
        Upload a local file.

        Args:
        - payload: Payload with the local file and Alfred's properties.
        """
