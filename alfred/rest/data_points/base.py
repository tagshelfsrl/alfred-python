# Native imports
from typing import Text, Any
from abc import ABC, abstractmethod


class DataPointsBase(ABC):
    @abstractmethod
    def get_values(self, file_id: Text) -> Any:
        """
        Fetch Data Point values for a specific File by its ID.

        Args:
        - file_id: Unique identifier of the File.
        """
