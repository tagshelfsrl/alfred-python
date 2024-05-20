# Native imports
from typing import TypedDict, Union


# Typed dictionaries
class LoggingOptions(TypedDict):
    level: Union[str, int]
    name: str
    format: str
    papertrail_host: str
    papertrail_port: int
