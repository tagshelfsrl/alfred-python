# Native imports
from typing import TypedDict


# Typed dictionaries
class LoggingOptions(TypedDict):
    level: int
    name: str
    env: str
    papertrail_host: str
    papertrail_port: int
