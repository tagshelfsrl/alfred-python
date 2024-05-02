# Native imports
from typing import Text, Any
from abc import ABC, abstractmethod


class SessionsBase(ABC):
    @abstractmethod
    def create(self) -> Any:
        """
        Creates a new Session.
        """

    @abstractmethod
    def get(self, session_id: Text) -> Any:
        """
        Fetches a Session by its ID.

        Args:
        - session_id: Unique identifier of the Session.
        """
