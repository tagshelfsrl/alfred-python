# Native imports
import uuid
from abc import ABC, abstractmethod
from typing import Union

# Project imports
from .typed import (
    ClassificationResponse,
    CreateClassificationFilePayload,
    CreateClassificationPayload,
)


class ClassificationsBase(ABC):
    @abstractmethod
    def create(self, payload: CreateClassificationPayload) -> ClassificationResponse:
        """
        Start a standalone classification of a text against criteria sent in
        the request. Returns the 202 answer (status "queued").

        Each call creates, classifies and bills a new job. The API has no
        idempotency: do not retry this call blindly after a timeout; fetch the
        id you were given with `get` first, if you got one.

        Args:
        - payload: Criteria (`tags`), `text`, and optionally `file_name` and
          `correlation_id`.
        """

    @abstractmethod
    def create_from_file(
        self, payload: CreateClassificationFilePayload
    ) -> ClassificationResponse:
        """
        Start a standalone classification of one file against criteria sent in
        the request. Returns the 202 answer (status "queued").

        Each call creates, classifies and bills a new job. The API has no
        idempotency: do not retry this call blindly after a timeout.

        Args:
        - payload: The binary `file`, criteria (`tags`), and optionally
          `filename` and `correlation_id`.
        """

    @abstractmethod
    def get(self, classification_id: Union[str, uuid.UUID]) -> ClassificationResponse:
        """
        Fetch a standalone classification by id (the id of the job returned
        by `create` or `create_from_file`). Poll until `status` is
        "completed" or "failed".

        Args:
        - classification_id: Id of the classification job (str or UUID).
        """
