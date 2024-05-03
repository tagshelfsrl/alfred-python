# Native imports
from typing import Text, List
from abc import ABC, abstractmethod

# Project imports
from .typed import DataPointDict


class DataPointsBase(ABC):
    @abstractmethod
    def get_values(self, file_id: Text) -> List[DataPointDict]:
        """
        Fetch Data Point values for a specific File by its ID.

        Args:
        - file_id: Unique identifier of the File.
        """
