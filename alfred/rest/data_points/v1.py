# Native imports
from typing import List, Optional, Text

# Project imports
from alfred.http.http_client import HttpClient
from alfred.rest.data_points.base import DataPointsBase
from alfred.rest.data_points.typed import DataPointValue


class DataPoints(DataPointsBase):
    def __init__(self, http_client: HttpClient):
        self.http_client = http_client

    def get_values(self, file_id: Text) -> Optional[List[DataPointValue]]:
        """
        Fetches Data Point values for a specific File by its ID.

        Each row carries the value, Alfred's confidence in it
        (`classification_score`) and, when there is something to report, the
        extractor's original output, the normalised value and the result of
        the data point's validators. See `DataPointValue`.

        Args:
        - file_id: Unique identifier of the File.

        Returns:
        - One `DataPointValue` per data point of the file's tag, exactly as
          the API sends them, or `None` when the API answers with no content.
        """
        parsed_resp, _ = self.http_client.get(f"/api/values/file/{file_id}")
        return parsed_resp
