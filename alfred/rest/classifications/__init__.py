from .base import ClassificationsBase
from .typed import *
from .v1 import Classifications as V1


class ClassificationsFactory:
    @staticmethod
    def create(version: int, http_client):
        """
        Create Classifications domain instance based on specified version.
        """
        if version == 1:
            return V1(http_client)
        else:
            raise ValueError(f"Unsupported version: {version}")
