# Native imports
from typing import List, Text

# Project imports
from src.alfred.http.http_client import HttpClient
from src.alfred.rest.data_points.base import DataPointsBase
from src.alfred.rest.data_points.typed import DataPointDict


class DataPoints(DataPointsBase):
    def __init__(self, http_client: HttpClient):
        self.http_client = http_client

    def get_values(self, file_id: Text) -> List[DataPointDict]:
        parsed_resp, _ = self.http_client.get(f"/api/values/file/{file_id}")
        return parsed_resp
