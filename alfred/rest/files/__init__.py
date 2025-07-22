from .base import FilesBase
from .typed import *
from .v1 import Files as V1


class FilesFactory:
    @staticmethod
    def create(version: int, http_client):
        """
        Create Files domain instance based on specified version.
        """
        if version == 1:
            return V1(http_client)
        else:
            raise ValueError(f"Unsupported version: {version}")
