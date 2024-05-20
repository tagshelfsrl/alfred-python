from .base import DataPointsBase
from .v1 import DataPoints as V1


class DataPointsFactory:
    @staticmethod
    def create(version: int, http_client):
        """
        Instance of Data Points class
        """
        if version == 1:
            return V1(http_client)

        raise Exception("Unsupported version for the specified domain.")
