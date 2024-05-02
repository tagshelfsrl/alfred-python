from .base import JobsBase
from .v1 import Jobs as V1


class JobsFactory:
    @staticmethod
    def create(version: int, http_client):
        """
        Create Jobs domain instance based on specified version.
        """
        if version == 1:
            return V1(http_client)
        else:
            raise ValueError(f"Unsupported version: {version}")
