# Native imports
import json
import socket
import logging
from typing import List, Union
from logging.handlers import SysLogHandler

# Project imports
from app.typings import LoggingOptions


def init_loggers(loggers: List[logging.Logger], options: LoggingOptions):
    """
    Setup a custom logger with JSON formatting and handler
    based on application environment.
    """
    env = options.get("env")
    name = options.get("name")
    pt_host = options.get("papertrail_host")
    pt_port = options.get("papertrail_port")

    class ContextFilter(logging.Filter):
        hostname = socket.gethostname()

        def filter(self, record):
            record.hostname = ContextFilter.hostname
            return True

    class PapertrailFormatter(logging.Formatter):
        def __init__(
            self,
            fmt: Union[str, None] = ...,
            datefmt: Union[str, None] = ...,
        ) -> None:
            super().__init__(datefmt=datefmt)

        def format(self, record):
            is_text = isinstance(record.msg, (str))
            record.message = record.getMessage() if is_text else record.msg
            record.asctime = self.formatTime(record, self.datefmt)
            record.stack_info = self.formatStack(record.stack_info)
            if record.exc_info:
                if not record.exc_text:
                    record.exc_text = self.formatException(record.exc_info)

            # Prepare json logging
            data = {"msg": record.message, "level": record.levelname}
            if record.exc_text:
                data["exception"] = record.exc_text

            return f"{record.asctime} {name} {name}-{env} {json.dumps(data)}"

    # Setup handler based on env
    if options.get("env") == "dev":
        handler = logging.StreamHandler()
    else:
        handler = SysLogHandler(address=(pt_host, pt_port))

    # Add filter to handler
    handler.addFilter(ContextFilter())

    # Setup handler formatter
    handler.setFormatter(PapertrailFormatter(datefmt="%b %d %H:%M:%S"))

    for logger in loggers:
        # Remove all logger existing handlers
        logger.handlers = []

        # Set logger level
        logger.setLevel(options["level"])

        # Set logger handler
        logger.addHandler(handler)
