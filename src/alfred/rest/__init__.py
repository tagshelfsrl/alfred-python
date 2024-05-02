# Native imports
from typing import Optional

# 3rd party imports
from src.alfred.base.config import ConfigurationDict
from src.alfred.http.http_client import HttpClient
from src.alfred.http.typed import AuthConfiguration, HttpConfiguration
from src.alfred.rest.data_points import DataPointsBase, DataPointsFactory


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
