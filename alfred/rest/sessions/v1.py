# Native imports
from typing import Text

# Project imports
from alfred.http.http_client import HttpClient
from alfred.rest.sessions.base import SessionsBase


class Sessions(SessionsBase):
    def __init__(self, http_client: HttpClient):
        self.http_client = http_client

    def create(self):
        """
        Creates a new Session.
        """
        parsed_resp, _ = self.http_client.post("/api/deferred/create")
        return parsed_resp

    def get(self, session_id: Text):
        """
        Fetches a Session by its ID.

        Args:
        - session_id: Unique identifier of the Session.
        """
        parsed_resp, _ = self.http_client.get(f"/api/deferred/detail/{session_id}")
        return parsed_resp
