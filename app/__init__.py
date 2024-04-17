# Native imports
import logging

# Project imports
from app.config import settings
from app.utils import init_loggers
from app.typings import LoggingOptions

# Initialize loggers
loggers = [logging.getLogger(__name__)]
logging_options: LoggingOptions = {
    "env": settings.env,
    "level": logging.INFO,
    "name": settings.name,
    "papertrail_host": settings.pt_host,
    "papertrail_port": settings.pt_port,
}
init_loggers(loggers, logging_options)


def run():
    """
    Run main application
    """
