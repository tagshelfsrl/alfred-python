# Native imports
from typing import Optional

# Project imports
from alfred.base.config import ConfigurationDict
from alfred.http.http_client import HttpClient
from alfred.http.typed import AuthConfiguration, HttpConfiguration
from alfred.rest.data_points import DataPointsBase, DataPointsFactory
from alfred.rest.sessions import SessionsBase, SessionsFactory
from alfred.rest.jobs import JobsBase, JobsFactory
from alfred.rest.files import FilesBase, FilesFactory


class AlfredClient:
    __DEFAULT_HTTP_CONFIG: HttpConfiguration = {
        "max_retries": 3,
        "pool_connections": True,
        "timeout": 5,
    }

    def __init__(
        self,
        config: ConfigurationDict,
        auth_config: AuthConfiguration,
        http_config: HttpConfiguration = None,
        http_client: HttpClient = None,
    ) -> None:
        # Initialize HTTP client
        self.config = config
        http_config = http_config or self.__DEFAULT_HTTP_CONFIG
        self.http_client = http_client or HttpClient(
            config.get("base_url"), auth_config, http_config
        )

        # Domain properties
        self._data_points: Optional[DataPointsBase] = None
        self._sessions: Optional[SessionsBase] = None
        self._jobs: Optional[JobsBase] = None
        self._files: Optional[FilesBase] = None

    def __get_domain_by_version(self, factory):
        """
        Get domain instance based on specified version.
        """
        version = self.config.get("version")
        return factory.create(version, self.http_client)

    @property
    def data_points(self) -> "DataPointsBase":
        """
        Access the Data Points domain.
        """
        if self._data_points is None:
            self._data_points = self.__get_domain_by_version(DataPointsFactory)

        return self._data_points

    @property
    def sessions(self) -> "SessionsBase":
        """
        Access the Sessions domain.
        """
        if self._sessions is None:
            self._sessions = self.__get_domain_by_version(SessionsFactory)

        return self._sessions

    @property
    def jobs(self) -> "JobsBase":
        """
        Access the Jobs domain.
        """
        if self._jobs is None:
            self._jobs = self.__get_domain_by_version(JobsFactory)

        return self._jobs

    @property
    def files(self) -> "FilesBase":
        """
        Access the Files domain.
        """
        if self._files is None:
            self._files = self.__get_domain_by_version(FilesFactory)

        return self._files
