import logging
import unittest
from unittest.mock import MagicMock, patch

import alfred.exceptions
from alfred.base.config import Configuration
from alfred.realtime import AlfredRealTimeClient

LOGGER_NAME = "alfred-python"
AUTH_CONFIG = {"api_key": "key-1"}


class _CapturingHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.messages = []

    def emit(self, record):
        self.messages.append(record.getMessage())


def _handlers_by_event(socket):
    """
    Map each event name passed to socket.on(...) to the callable registered for it.
    """
    return {c[0][0]: c[0][1] for c in socket.on.call_args_list}


class TestAlfredRealTimeClient(unittest.TestCase):
    def setUp(self):
        # Keep the shared logger out of the global state.
        logger = logging.getLogger(LOGGER_NAME)
        self._saved_handlers = list(logger.handlers)
        self._saved_level = logger.level
        self._saved_propagate = logger.propagate

        # Start at DEBUG so client construction does not reconfigure the logger
        # unless a test asks for that, and capture output instead of printing it.
        self.logs = _CapturingHandler()
        logger.handlers = [self.logs]
        logger.setLevel(logging.DEBUG)
        logger.propagate = False

        socket_patcher = patch("alfred.realtime.socketio.Client")
        self.socket_cls = socket_patcher.start()
        self.socket = self.socket_cls.return_value
        self._socket_patcher = socket_patcher

    def tearDown(self):
        self._socket_patcher.stop()
        logger = logging.getLogger(LOGGER_NAME)
        logger.handlers = self._saved_handlers
        logger.setLevel(self._saved_level)
        logger.propagate = self._saved_propagate

    def _client(self, **kwargs):
        return AlfredRealTimeClient(Configuration.v1(), AUTH_CONFIG, **kwargs)

    # Connection

    def test_connects_to_realtime_url_with_api_key_query_parameter(self):
        self._client()

        self.socket.connect.assert_called_once_with("https://sockets.tagshelf.io?apiKey=key-1")

    def test_connects_to_overridden_realtime_url(self):
        config = Configuration.v1({"realtime_url": "https://sockets.example.test"})

        AlfredRealTimeClient(config, AUTH_CONFIG)

        self.socket.connect.assert_called_once_with("https://sockets.example.test?apiKey=key-1")

    def test_exposes_socket_io_client_instance_as_socket(self):
        client = self._client()

        self.assertIs(client.socket, self.socket)

    def test_failing_connect_raises_connection_error_with_cause_in_message(self):
        self.socket.connect.side_effect = OSError("connection refused")

        with self.assertRaises(alfred.exceptions.ConnectionError) as ctx:
            self._client()

        self.assertIn("connection refused", str(ctx.exception))
        self.assertIn("Could not establish connection with server", str(ctx.exception))

    def test_registers_connect_disconnect_and_connect_error_lifecycle_handlers(self):
        self._client()

        self.assertEqual(
            set(_handlers_by_event(self.socket)),
            {"connect", "disconnect", "connect_error"},
        )

    def test_verbose_client_logs_attempt_before_connecting(self):
        self._client(verbose=True)

        self.assertIn("Attempting to establish a connection...", self.logs.messages)

    def test_non_verbose_client_logs_nothing_on_construction(self):
        self._client()

        self.assertEqual(self.logs.messages, [])

    # Lifecycle handlers

    def test_connect_handler_invokes_on_connect_callback(self):
        on_connect = MagicMock()
        self._client(on_connect=on_connect)

        _handlers_by_event(self.socket)["connect"]()

        on_connect.assert_called_once_with()

    def test_connect_handler_without_callback_does_not_raise(self):
        self._client()

        _handlers_by_event(self.socket)["connect"]()

    def test_connect_handler_logs_connected_url(self):
        self._client()

        _handlers_by_event(self.socket)["connect"]()

        self.assertIn(
            "Successfully connected to: https://sockets.tagshelf.io",
            self.logs.messages,
        )

    def test_disconnect_handler_logs_when_verbose(self):
        self._client(verbose=True)

        _handlers_by_event(self.socket)["disconnect"]()

        self.assertIn("Disconnected from the server.", self.logs.messages)

    def test_disconnect_handler_is_silent_when_not_verbose(self):
        self._client()

        _handlers_by_event(self.socket)["disconnect"]()

        self.assertEqual(self.logs.messages, [])

    def test_connect_error_handler_disconnects_socket(self):
        self._client()

        _handlers_by_event(self.socket)["connect_error"]("boom")

        self.socket.disconnect.assert_called_once_with()

    def test_connect_error_handler_passes_error_to_error_callback(self):
        error_callback = MagicMock()
        self._client(error_callback=error_callback)

        _handlers_by_event(self.socket)["connect_error"]("boom")

        error_callback.assert_called_once_with("boom")

    def test_connect_error_handler_without_error_callback_still_disconnects_without_raising(self):
        self._client()

        _handlers_by_event(self.socket)["connect_error"]("boom")

        self.socket.disconnect.assert_called_once_with()

    def test_connect_error_handler_logs_error_when_verbose(self):
        self._client(verbose=True)

        _handlers_by_event(self.socket)["connect_error"]("boom")

        self.assertIn("Connection error:  boom", self.logs.messages)

    def test_connect_error_handler_does_not_log_connection_error_when_not_verbose(self):
        self._client()

        _handlers_by_event(self.socket)["connect_error"]("boom")

        self.assertFalse(any("Connection error" in m for m in self.logs.messages))

    # Event subscriptions

    def test_on_job_event_registers_handler_under_job_event_name(self):
        client = self._client()

        client.on_job_event(MagicMock())

        self.assertIn("job_event", _handlers_by_event(self.socket))

    def test_on_file_event_registers_handler_under_file_event_name(self):
        client = self._client()

        client.on_file_event(MagicMock())

        self.assertIn("file_event", _handlers_by_event(self.socket))

    def test_on_registers_handler_under_given_event_name(self):
        client = self._client()

        client.on("job_start_event", MagicMock())

        self.assertIn("job_start_event", _handlers_by_event(self.socket))

    def test_job_event_handler_forwards_payload_to_callback_when_not_verbose(self):
        callback = MagicMock()
        client = self._client()
        client.on_job_event(callback)

        _handlers_by_event(self.socket)["job_event"]({"job_id": "j1"})

        callback.assert_called_once_with({"job_id": "j1"})
        self.assertEqual(self.logs.messages, [])

    def test_file_event_handler_forwards_payload_and_logs_it_when_verbose(self):
        callback = MagicMock()
        client = self._client(verbose=True)
        client.on_file_event(callback)

        _handlers_by_event(self.socket)["file_event"]({"file_id": "f1"})

        callback.assert_called_once_with({"file_id": "f1"})
        self.assertIn("Event file_event received: {'file_id': 'f1'}", self.logs.messages)

    def test_on_handler_forwards_payload_to_callback(self):
        callback = MagicMock()
        client = self._client()
        client.on("job_start_event", callback)

        _handlers_by_event(self.socket)["job_start_event"]({"job_id": "j2"})

        callback.assert_called_once_with({"job_id": "j2"})

    # Disconnect

    def test_disconnect_closes_socket_connection(self):
        client = self._client()

        client.disconnect()

        self.socket.disconnect.assert_called_once_with()

    # Logger configuration

    def test_configures_logger_at_info_when_verbose_is_false_and_level_unset(self):
        logging.getLogger(LOGGER_NAME).setLevel(logging.NOTSET)

        with patch("alfred.realtime.setup_logger") as setup_logger:
            self._client()

        setup_logger.assert_called_once_with({"level": "INFO", "name": "alfred-python"})

    def test_configures_logger_at_debug_when_verbose_and_level_unset(self):
        logging.getLogger(LOGGER_NAME).setLevel(logging.NOTSET)

        with patch("alfred.realtime.setup_logger") as setup_logger:
            self._client(verbose=True)

        setup_logger.assert_called_once_with({"level": "DEBUG", "name": "alfred-python"})

    def test_does_not_reconfigure_logger_when_level_already_set(self):
        logging.getLogger(LOGGER_NAME).setLevel(logging.WARNING)

        with patch("alfred.realtime.setup_logger") as setup_logger:
            self._client(verbose=True)

        setup_logger.assert_not_called()


if __name__ == "__main__":
    unittest.main()
