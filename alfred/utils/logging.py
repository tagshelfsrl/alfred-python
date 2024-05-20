# Native imports
import json
import logging
import socket
from logging.handlers import SysLogHandler
from typing import Union

# Project imports
from alfred.typings import LoggingOptions


def setup_logger(options: LoggingOptions):
    """
    Set up a custom logger with JSON formatting and handler
    based on application environment.
    """
    logger = logging.getLogger("alfred-python")
    name = options.get("name")
    pt_host = options.get("papertrail_host")
    pt_port = options.get("papertrail_port")
    _format = options.get("format")

    class ContextFilter(logging.Filter):
        hostname = socket.gethostname()

        def filter(self, record):
            record.hostname = ContextFilter.hostname
            return True

    class PapertrailFormatter(logging.Formatter):
        def __init__(
                self,
                fmt: Union[str, None] = _format,
                datefmt: Union[str, None] = ...,
        ) -> None:
            super().__init__(datefmt=datefmt, fmt=fmt)

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

            return f"{record.asctime} {name} {json.dumps(data)}"

    # Setup handlers based on env
    handlers = [logging.StreamHandler()]
    if pt_host and pt_port:
        handlers.append(SysLogHandler(address=(pt_host, pt_port)))

    # Remove all logger existing handlers
    logger.handlers = []

    # Set logger level
    logger.setLevel(options["level"])

    # Set logger handler
    for handler in handlers:
        # Add filter to handler
        handler.addFilter(ContextFilter())

        # Setup handler formatter
        handler.setFormatter(PapertrailFormatter(datefmt="%b %d %H:%M:%S"))

        # Add handler
        logger.addHandler(handler)

    return logger
