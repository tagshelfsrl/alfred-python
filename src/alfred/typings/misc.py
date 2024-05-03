# Native imports
from typing import TypedDict


# Typed dictionaries
class LoggingOptions(TypedDict):
    level: int
    name: str
    format: str
    papertrail_host: str
    papertrail_port: int
