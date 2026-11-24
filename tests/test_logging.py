import importlib
import json
import logging
import re
import socket
import sys
import unittest
from unittest.mock import patch

from alfred.utils.logging import setup_logger

LOGGER_NAME = "alfred-python"

# alfred/utils/__init__.py star-imports the logging module, which shadows the
# `alfred.utils.logging` attribute on the package. Resolve the real module
# through importlib so patch() targets the module that setup_logger uses.
LOGGING_MODULE = importlib.import_module("alfred.utils.logging")

# "Nov 24 01:35:00 alfred-python {...json...}"
LINE_PATTERN = re.compile(
    r"^[A-Z][a-z]{2} \d{2} \d{2}:\d{2}:\d{2} alfred-python (?P<json>\{.*\})$"
)


def _make_record(msg, args=None, exc_info=None):
    return logging.LogRecord(
        name=LOGGER_NAME,
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=msg,
        args=args,
        exc_info=exc_info,
    )


def _parse_line(line):
    match = LINE_PATTERN.match(line)
    if match is None:
        raise AssertionError(f"Log line does not match expected layout: {line!r}")
    return json.loads(match.group("json"))


class LoggerStateTestCase(unittest.TestCase):
    """
    The "alfred-python" logger is process-global, so each test starts from
    a known state and the original handlers, level and propagate flag are
    restored afterwards.
    """

    def setUp(self):
        logger = logging.getLogger(LOGGER_NAME)
        self._saved_handlers = list(logger.handlers)
        self._saved_level = logger.level
        self._saved_propagate = logger.propagate

    def tearDown(self):
        logger = logging.getLogger(LOGGER_NAME)
        logger.handlers = self._saved_handlers
        logger.setLevel(self._saved_level)
        logger.propagate = self._saved_propagate


class TestSetupLoggerConfiguration(LoggerStateTestCase):
    def test_returns_logger_named_alfred_python(self):
        logger = setup_logger({"level": "DEBUG", "name": "alfred-python"})

        self.assertIs(logger, logging.getLogger(LOGGER_NAME))
        self.assertEqual(logger.name, LOGGER_NAME)

    def test_sets_logger_level_from_option_name(self):
        logger = setup_logger({"level": "WARNING", "name": "alfred-python"})

        self.assertEqual(logger.level, logging.WARNING)

    def test_sets_logger_level_from_integer_option(self):
        logger = setup_logger({"level": logging.ERROR, "name": "alfred-python"})

        self.assertEqual(logger.level, logging.ERROR)

    def test_default_configuration_attaches_single_stream_handler(self):
        logger = setup_logger({"level": "INFO", "name": "alfred-python"})

        self.assertEqual([type(h) for h in logger.handlers], [logging.StreamHandler])

    def test_papertrail_host_and_port_attach_syslog_handler_after_stream_handler(self):
        with patch.object(LOGGING_MODULE, "SysLogHandler") as syslog_cls:
            logger = setup_logger({
                "level": "INFO",
                "name": "alfred-python",
                "papertrail_host": "logs.example.test",
                "papertrail_port": 1234,
            })

        syslog_cls.assert_called_once_with(address=("logs.example.test", 1234))
        self.assertEqual(len(logger.handlers), 2)
        self.assertIs(type(logger.handlers[0]), logging.StreamHandler)
        self.assertIs(logger.handlers[1], syslog_cls.return_value)

    def test_papertrail_host_without_port_does_not_attach_syslog_handler(self):
        with patch.object(LOGGING_MODULE, "SysLogHandler") as syslog_cls:
            logger = setup_logger({
                "level": "INFO",
                "name": "alfred-python",
                "papertrail_host": "logs.example.test",
            })

        syslog_cls.assert_not_called()
        self.assertEqual([type(h) for h in logger.handlers], [logging.StreamHandler])

    def test_calling_twice_replaces_handlers_instead_of_accumulating(self):
        first = setup_logger({"level": "INFO", "name": "alfred-python"})
        first_handler = first.handlers[0]

        second = setup_logger({"level": "INFO", "name": "alfred-python"})

        self.assertIs(first, second)
        self.assertEqual(len(second.handlers), 1)
        self.assertIsNot(second.handlers[0], first_handler)

    def test_handler_filter_sets_hostname_on_record(self):
        logger = setup_logger({"level": "INFO", "name": "alfred-python"})
        record = _make_record("hello")

        self.assertTrue(logger.handlers[0].filter(record))
        self.assertEqual(record.hostname, socket.gethostname())


class TestSetupLoggerFormatter(LoggerStateTestCase):
    def setUp(self):
        super().setUp()
        logger = setup_logger({"level": "DEBUG", "name": "alfred-python"})
        self.formatter = logger.handlers[0].formatter

    def test_text_message_is_formatted_as_timestamped_json_line(self):
        record = _make_record("hello %s", args=("world",))

        line = self.formatter.format(record)

        self.assertEqual(_parse_line(line), {"msg": "hello world", "level": "INFO"})

    def test_non_string_message_is_serialised_as_json_object(self):
        record = _make_record({"order": 7, "status": "ok"})

        line = self.formatter.format(record)

        self.assertEqual(
            _parse_line(line),
            {"msg": {"order": 7, "status": "ok"}, "level": "INFO"},
        )

    def test_record_without_exception_info_has_no_exception_key(self):
        record = _make_record("plain")

        data = _parse_line(self.formatter.format(record))

        self.assertNotIn("exception", data)

    def test_record_with_exception_info_adds_traceback_under_exception_key(self):
        try:
            raise ValueError("boom")
        except ValueError:
            exc_info = sys.exc_info()
        record = _make_record("failed", exc_info=exc_info)
        record.levelname = "ERROR"

        data = _parse_line(self.formatter.format(record))

        self.assertEqual(data["msg"], "failed")
        self.assertEqual(data["level"], "ERROR")
        self.assertIn("Traceback (most recent call last)", data["exception"])
        self.assertTrue(data["exception"].endswith("ValueError: boom"))

    def test_record_with_preformatted_exc_text_keeps_that_text(self):
        try:
            raise ValueError("boom")
        except ValueError:
            exc_info = sys.exc_info()
        record = _make_record("failed", exc_info=exc_info)
        record.exc_text = "cached traceback text"

        data = _parse_line(self.formatter.format(record))

        self.assertEqual(data["exception"], "cached traceback text")


if __name__ == "__main__":
    unittest.main()
