from .base import SessionsBase
from .v1 import Sessions as V1


class SessionsFactory:
    @staticmethod
    def create(version: int, http_client):
        """
        Instance of Data Points class
        """
        if version == 1:
            return V1(http_client)

        raise Exception("Unsupported version for the specified domain.")
