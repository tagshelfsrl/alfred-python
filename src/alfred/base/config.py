# Native imports
from typing import TypedDict, Optional, Text


class ConfigurationDict(TypedDict):
    base_url: Text
    realtime_url: Text
    version: int


class OverridesDict(TypedDict):
    base_url: Optional[Text]


class Configuration:
    @staticmethod
    def default() -> ConfigurationDict:
        """
        Returns default client configuration. Currently, targets Alfred V1.
        """
        return Configuration.v1()

    @staticmethod
    def v1(overrides: Optional[OverridesDict] = None) -> ConfigurationDict:
        """
        Returns client configuration for Alfred V1.
        """
        overrides = overrides or {}
        return {
            "version": 1,
            "base_url": overrides.get("base_url", "https://app.tagshelf.com"),
            "realtime_url": overrides.get("realtime_url", "https://sockets.tagshelf.io"),
        }
