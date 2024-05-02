# Native imports
from typing import Text

# Project imports
from src.alfred.http.http_client import HttpClient
from src.alfred.rest.data_points.base import DataPointsBase


class DataPoints(DataPointsBase):
    def __init__(self, http_client: HttpClient):
        self.http_client = http_client

    def get_values(self, file_id: Text):
        """
        Fetches Data Point values for a specific File by its ID.

        Args:
        - file_id: Unique identifier of the File.
        """
        return self.http_client.get(f"/api/values/file/{file_id}")
