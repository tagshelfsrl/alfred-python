# Native imports
from typing import List, Optional, Text
from abc import ABC, abstractmethod

# Project imports
from alfred.rest.data_points.typed import DataPointValue


class DataPointsBase(ABC):
    @abstractmethod
    def get_values(self, file_id: Text) -> Optional[List[DataPointValue]]:
        """
        Fetch Data Point values for a specific File by its ID.

        Args:
        - file_id: Unique identifier of the File.

        Returns:
        - One `DataPointValue` per data point of the file's tag, exactly as
          the API sends them, or `None` when the API answers with no content.
        """
