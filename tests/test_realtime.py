import logging
import unittest
from unittest.mock import MagicMock, patch

import alfred.exceptions
from alfred.base.config import Configuration
from alfred.base.constants import EventType, FileEvent, JobEvent
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

    def test_failing_connect_keeps_the_api_key_out_of_the_error(self):
        # The transport's error quotes the connection URL, key included.
        self.socket.connect.side_effect = OSError(
            "Max retries exceeded with url: /socket.io/?apiKey=key-1&transport=polling"
        )

        with self.assertRaises(alfred.exceptions.ConnectionError) as ctx:
            self._client()

        self.assertNotIn("key-1", str(ctx.exception))
        self.assertNotIn("key-1", ctx.exception.message)
        self.assertIn("/socket.io/?apiKey=[redacted]&transport=polling", str(ctx.exception))

    def test_failing_connect_does_not_chain_the_error_that_quotes_the_key(self):
        self.socket.connect.side_effect = OSError("url: /socket.io/?apiKey=key-1")

        with self.assertRaises(alfred.exceptions.ConnectionError) as ctx:
            self._client()

        self.assertIsNone(ctx.exception.__cause__)
        self.assertTrue(ctx.exception.__suppress_context__)

    def test_failing_connect_redacts_the_url_encoded_form_of_the_api_key(self):
        self.socket.connect.side_effect = OSError(
            "tried /socket.io/?apiKey=a%2Bb%2Fc%3D and /socket.io/?apiKey=a+b/c="
        )

        with self.assertRaises(alfred.exceptions.ConnectionError) as ctx:
            AlfredRealTimeClient(Configuration.v1(), {"api_key": "a+b/c="})

        self.assertNotIn("a%2Bb%2Fc%3D", str(ctx.exception))
        self.assertNotIn("a+b/c=", str(ctx.exception))
        self.assertEqual(str(ctx.exception).count("[redacted]"), 2)

    def test_failing_connect_without_an_api_key_keeps_the_error_text(self):
        self.socket.connect.side_effect = OSError("refused apiKey=None")

        with self.assertRaises(alfred.exceptions.ConnectionError) as ctx:
            AlfredRealTimeClient(Configuration.v1(), {})

        self.assertIn("refused apiKey=None", str(ctx.exception))

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

    def test_connect_error_handler_keeps_the_api_key_out_of_callback_and_log(self):
        error_callback = MagicMock()
        self._client(verbose=True, error_callback=error_callback)

        _handlers_by_event(self.socket)["connect_error"](
            "refused: /socket.io/?apiKey=key-1&EIO=4"
        )

        error_callback.assert_called_once_with("refused: /socket.io/?apiKey=[redacted]&EIO=4")
        self.assertFalse([m for m in self.logs.messages if "key-1" in m])
        self.assertIn(
            "Connection error:  refused: /socket.io/?apiKey=[redacted]&EIO=4",
            self.logs.messages,
        )

    def test_connect_error_handler_passes_an_error_that_is_not_text_unchanged(self):
        error_callback = MagicMock()
        error = {"message": "key-1 is not valid"}
        self._client(error_callback=error_callback)

        _handlers_by_event(self.socket)["connect_error"](error)

        error_callback.assert_called_once_with(error)
        self.assertIs(error_callback.call_args[0][0], error)

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

    def _deliver(self, stream, data):
        _handlers_by_event(self.socket)[stream](data)

    def test_on_job_event_attaches_one_handler_under_job_event(self):
        client = self._client()

        client.on_job_event(MagicMock())

        events = [c[0][0] for c in self.socket.on.call_args_list]
        self.assertEqual(events.count("job_event"), 1)

    def test_on_file_event_attaches_one_handler_under_file_event(self):
        client = self._client()

        client.on_file_event(MagicMock())

        events = [c[0][0] for c in self.socket.on.call_args_list]
        self.assertEqual(events.count("file_event"), 1)

    def test_on_job_event_forwards_data_unchanged(self):
        callback = MagicMock()
        client = self._client()
        client.on_job_event(callback)
        data = {"event_name": "alfred_event_job_start", "job_id": "j1"}

        self._deliver("job_event", data)

        callback.assert_called_once_with(data)
        self.assertIs(callback.call_args[0][0], data)
        self.assertEqual(self.logs.messages, [])

    def test_on_file_event_forwards_data_unchanged(self):
        callback = MagicMock()
        client = self._client()
        client.on_file_event(callback)
        data = {"event_name": "alfred_event_file_done", "file_id": "f1"}

        self._deliver("file_event", data)

        callback.assert_called_once_with(data)
        self.assertIs(callback.call_args[0][0], data)

    def test_on_with_job_event_type_behaves_like_on_job_event(self):
        callback = MagicMock()
        client = self._client()
        client.on(EventType.JOB_EVENT, callback)

        self._deliver("job_event", {"job_id": "j1"})

        callback.assert_called_once_with({"job_id": "j1"})

    def test_on_with_file_event_type_behaves_like_on_file_event(self):
        callback = MagicMock()
        client = self._client()
        client.on(EventType.FILE_EVENT, callback)

        self._deliver("file_event", {"file_id": "f1"})

        callback.assert_called_once_with({"file_id": "f1"})

    def test_on_with_stream_name_behaves_like_on_job_event(self):
        callback = MagicMock()
        client = self._client()
        client.on("job_event", callback)

        self._deliver("job_event", {"job_id": "j1"})

        callback.assert_called_once_with({"job_id": "j1"})
        self.assertEqual(self.logs.messages, [])

    def test_on_with_enum_member_fires_for_matching_event_name(self):
        callback = MagicMock()
        client = self._client()
        client.on(JobEvent.JOB_FINISHED_EVENT, callback)
        data = {"event_name": "alfred_event_job_finished", "job_id": "j1"}

        self._deliver("job_event", data)

        callback.assert_called_once_with(data)

    def test_on_with_event_name_string_fires_for_matching_event_name(self):
        callback = MagicMock()
        client = self._client()
        client.on("alfred_event_job_finished", callback)
        data = {"event_name": "alfred_event_job_finished"}

        self._deliver("job_event", data)

        callback.assert_called_once_with(data)
        self.assertEqual(self.logs.messages, [])

    def test_on_with_legacy_event_name_fires_for_the_name_alfred_sends(self):
        callback = MagicMock()
        client = self._client()
        client.on("job_finished_event", callback)
        data = {"event_name": "alfred_event_job_finished"}

        self._deliver("job_event", data)

        callback.assert_called_once_with(data)
        self.assertNotIn("job_finished_event", _handlers_by_event(self.socket))
        self.assertEqual(self.logs.messages, [])

    def test_on_with_legacy_file_event_name_fires_for_the_name_alfred_sends(self):
        callback = MagicMock()
        client = self._client()
        client.on("file_add_to_job_event", callback)
        data = {"event_name": "alfred_event_file_added_to_job"}

        self._deliver("file_event", data)

        callback.assert_called_once_with(data)

    def test_on_with_enum_member_does_not_fire_for_another_event_name(self):
        callback = MagicMock()
        client = self._client()
        client.on(JobEvent.JOB_FINISHED_EVENT, callback)

        self._deliver("job_event", {"event_name": "alfred_event_job_start"})

        callback.assert_not_called()

    def test_on_with_event_name_string_does_not_fire_for_another_event_name(self):
        callback = MagicMock()
        client = self._client()
        client.on("alfred_event_job_finished", callback)

        self._deliver("job_event", {"event_name": "alfred_event_job_failed"})

        callback.assert_not_called()

    def test_on_with_legacy_event_name_does_not_fire_for_another_event_name(self):
        callback = MagicMock()
        client = self._client()
        client.on("job_finished_event", callback)

        self._deliver("job_event", {"event_name": "alfred_event_job_start"})

        callback.assert_not_called()

    def test_file_event_name_listens_on_file_event_stream(self):
        client = self._client()

        client.on(FileEvent.FILE_DONE_EVENT, MagicMock())

        self.assertIn("file_event", _handlers_by_event(self.socket))
        self.assertNotIn("job_event", _handlers_by_event(self.socket))

    def test_job_event_name_listens_on_job_event_stream(self):
        client = self._client()

        client.on(JobEvent.JOB_START_EVENT, MagicMock())

        self.assertIn("job_event", _handlers_by_event(self.socket))
        self.assertNotIn("file_event", _handlers_by_event(self.socket))

    def test_bulk_task_event_name_listens_on_bulk_task_event_stream(self):
        callback = MagicMock()
        client = self._client()
        client.on("alfred_event_bulk_task_closed", callback)
        data = {"event_name": "alfred_event_bulk_task_closed"}

        self._deliver("bulk_task_event", data)

        callback.assert_called_once_with(data)
        self.assertNotIn("job_event", _handlers_by_event(self.socket))
        self.assertNotIn("file_event", _handlers_by_event(self.socket))
        self.assertEqual(self.logs.messages, [])

    def test_bulk_task_stream_name_listens_without_warning(self):
        callback = MagicMock()
        client = self._client()
        client.on("bulk_task_event", callback)

        self._deliver("bulk_task_event", {"x": 1})

        callback.assert_called_once_with({"x": 1})
        self.assertEqual(self.logs.messages, [])

    def test_stream_callback_and_event_callback_both_fire_stream_first(self):
        calls = []
        client = self._client()
        client.on_job_event(lambda data: calls.append(("stream", data)))
        client.on(JobEvent.JOB_FINISHED_EVENT, lambda data: calls.append(("event", data)))
        data = {"event_name": "alfred_event_job_finished"}

        self._deliver("job_event", data)

        self.assertEqual(calls, [("stream", data), ("event", data)])

    def test_event_callback_still_runs_and_error_propagates_when_stream_callback_raises(self):
        event_callback = MagicMock()
        client = self._client()
        client.on_job_event(MagicMock(side_effect=RuntimeError("boom")))
        client.on(JobEvent.JOB_FINISHED_EVENT, event_callback)
        data = {"event_name": "alfred_event_job_finished"}

        with self.assertRaises(RuntimeError):
            self._deliver("job_event", data)

        event_callback.assert_called_once_with(data)

    def test_registering_a_stream_twice_replaces_the_first_callback(self):
        first, second = MagicMock(), MagicMock()
        client = self._client()
        client.on_job_event(first)
        client.on_job_event(second)

        self._deliver("job_event", {"job_id": "j1"})

        first.assert_not_called()
        second.assert_called_once_with({"job_id": "j1"})

    def test_registering_an_event_twice_replaces_the_first_callback(self):
        first, second = MagicMock(), MagicMock()
        client = self._client()
        client.on(JobEvent.JOB_FINISHED_EVENT, first)
        client.on("job_finished_event", second)

        self._deliver("job_event", {"event_name": "alfred_event_job_finished"})

        first.assert_not_called()
        second.assert_called_once_with({"event_name": "alfred_event_job_finished"})

    def test_two_event_names_on_the_same_stream_both_work(self):
        started, finished = MagicMock(), MagicMock()
        client = self._client()
        client.on(JobEvent.JOB_START_EVENT, started)
        client.on(JobEvent.JOB_FINISHED_EVENT, finished)

        self._deliver("job_event", {"event_name": "alfred_event_job_start"})
        self._deliver("job_event", {"event_name": "alfred_event_job_finished"})

        started.assert_called_once_with({"event_name": "alfred_event_job_start"})
        finished.assert_called_once_with({"event_name": "alfred_event_job_finished"})

    def test_socket_handler_of_a_stream_is_attached_only_once(self):
        client = self._client()

        client.on_job_event(MagicMock())
        client.on(JobEvent.JOB_START_EVENT, MagicMock())
        client.on("alfred_event_job_failed", MagicMock())
        client.on("job_finished_event", MagicMock())
        client.on("job_event", MagicMock())

        events = [c[0][0] for c in self.socket.on.call_args_list]
        self.assertEqual(events.count("job_event"), 1)

    # Events Alfred sends under the name of another event

    def test_remove_tag_subscription_fires_for_a_change_tag_event_that_removes_a_tag(self):
        callback = MagicMock()
        client = self._client()
        client.on(FileEvent.FILE_REMOVE_TAG_EVENT, callback)
        data = {"event_name": "alfred_event_file_change_tag", "tag_being_removed_id": "t1"}

        self._deliver("file_event", data)

        callback.assert_called_once_with(data)

    def test_remove_tag_subscription_does_not_fire_for_a_change_of_tag(self):
        callback = MagicMock()
        client = self._client()
        client.on(FileEvent.FILE_REMOVE_TAG_EVENT, callback)

        self._deliver("file_event", {"event_name": "alfred_event_file_change_tag", "new_tag_id": "t2"})
        self._deliver(
            "file_event",
            {"event_name": "alfred_event_file_change_tag", "tag_being_removed_id": None},
        )

        callback.assert_not_called()

    def test_change_tag_subscription_fires_for_changes_and_for_removals(self):
        callback = MagicMock()
        client = self._client()
        client.on(FileEvent.FILE_CHANGE_TAG_EVENT, callback)
        change = {"event_name": "alfred_event_file_change_tag", "new_tag_id": "t2"}
        removal = {"event_name": "alfred_event_file_change_tag", "tag_being_removed_id": "t1"}

        self._deliver("file_event", change)
        self._deliver("file_event", removal)

        self.assertEqual([c[0][0] for c in callback.call_args_list], [change, removal])

    def test_change_tag_and_remove_tag_subscriptions_do_not_replace_each_other(self):
        calls = []
        client = self._client()
        client.on(FileEvent.FILE_CHANGE_TAG_EVENT, lambda data: calls.append("change"))
        client.on(FileEvent.FILE_REMOVE_TAG_EVENT, lambda data: calls.append("remove"))

        self._deliver(
            "file_event",
            {"event_name": "alfred_event_file_change_tag", "tag_being_removed_id": "t1"},
        )
        self._deliver("file_event", {"event_name": "alfred_event_file_change_tag", "new_tag_id": "t2"})

        self.assertEqual(calls, ["change", "remove", "change"])

    def test_legacy_remove_tag_name_fires_for_removals_only(self):
        callback = MagicMock()
        client = self._client()
        client.on("file_remove_tag_event", callback)
        removal = {"event_name": "alfred_event_file_change_tag", "tag_being_removed_id": "t1"}

        self._deliver("file_event", {"event_name": "alfred_event_file_change_tag", "new_tag_id": "t2"})
        self._deliver("file_event", removal)

        callback.assert_called_once_with(removal)

    def test_remove_tag_subscription_fires_if_alfred_sends_it_under_its_own_name(self):
        callback = MagicMock()
        client = self._client()
        client.on(FileEvent.FILE_REMOVE_TAG_EVENT, callback)
        data = {"event_name": "alfred_event_file_remove_tag"}

        self._deliver("file_event", data)

        callback.assert_called_once_with(data)

    def test_exceeded_retries_subscription_fires_for_a_retry_event_that_says_so(self):
        callback = MagicMock()
        client = self._client()
        client.on(JobEvent.JOB_EXCEEDED_RETRIES_EVENT, callback)
        data = {"event_name": "alfred_event_job_retry", "exceeded_retries": True}

        self._deliver("job_event", data)

        callback.assert_called_once_with(data)

    def test_exceeded_retries_subscription_does_not_fire_for_other_retry_events(self):
        callback = MagicMock()
        client = self._client()
        client.on(JobEvent.JOB_EXCEEDED_RETRIES_EVENT, callback)

        for value in (False, None, "true", 1):
            self._deliver("job_event", {"event_name": "alfred_event_job_retry", "exceeded_retries": value})
        self._deliver("job_event", {"event_name": "alfred_event_job_retry"})

        callback.assert_not_called()

    def test_retry_subscription_fires_for_every_retry_event(self):
        callback = MagicMock()
        client = self._client()
        client.on(JobEvent.JOB_RETRY_EVENT, callback)

        self._deliver("job_event", {"event_name": "alfred_event_job_retry", "exceeded_retries": True})
        self._deliver("job_event", {"event_name": "alfred_event_job_retry", "exceeded_retries": False})

        self.assertEqual(callback.call_count, 2)

    def test_retry_and_exceeded_retries_subscriptions_do_not_replace_each_other(self):
        calls = []
        client = self._client()
        client.on(JobEvent.JOB_EXCEEDED_RETRIES_EVENT, lambda data: calls.append("exceeded"))
        client.on(JobEvent.JOB_RETRY_EVENT, lambda data: calls.append("retry"))

        self._deliver("job_event", {"event_name": "alfred_event_job_retry", "exceeded_retries": True})

        self.assertEqual(calls, ["retry", "exceeded"])

    def test_legacy_exceeded_retries_name_fires_for_exhausted_retries_only(self):
        callback = MagicMock()
        client = self._client()
        client.on("job_exceeded_retries_event", callback)
        exhausted = {"event_name": "alfred_event_job_retry", "exceeded_retries": True}

        self._deliver("job_event", {"event_name": "alfred_event_job_retry", "exceeded_retries": False})
        self._deliver("job_event", exhausted)

        callback.assert_called_once_with(exhausted)

    def test_exceeded_retries_subscription_fires_if_alfred_sends_it_under_its_own_name(self):
        callback = MagicMock()
        client = self._client()
        client.on(JobEvent.JOB_EXCEEDED_RETRIES_EVENT, callback)
        data = {"event_name": "alfred_event_job_exceeded_retries"}

        self._deliver("job_event", data)

        callback.assert_called_once_with(data)

    # Errors raised by callbacks

    def test_every_callback_runs_and_the_first_error_is_raised_when_several_raise(self):
        removal_callback = MagicMock()
        client = self._client()
        client.on_file_event(MagicMock(side_effect=RuntimeError("stream")))
        client.on(FileEvent.FILE_CHANGE_TAG_EVENT, MagicMock(side_effect=ValueError("change")))
        client.on(FileEvent.FILE_REMOVE_TAG_EVENT, removal_callback)
        data = {"event_name": "alfred_event_file_change_tag", "tag_being_removed_id": "t1"}

        with self.assertRaises(RuntimeError) as raised:
            self._deliver("file_event", data)

        self.assertEqual(str(raised.exception), "stream")
        removal_callback.assert_called_once_with(data)

    def test_error_of_an_event_callback_is_raised_when_the_stream_callback_succeeds(self):
        stream_callback = MagicMock()
        client = self._client()
        client.on_job_event(stream_callback)
        client.on(JobEvent.JOB_FINISHED_EVENT, MagicMock(side_effect=ValueError("event")))
        data = {"event_name": "alfred_event_job_finished"}

        with self.assertRaises(ValueError):
            self._deliver("job_event", data)

        stream_callback.assert_called_once_with(data)

    def test_data_that_is_not_a_dict_reaches_only_the_stream_callback(self):
        stream_callback, event_callback = MagicMock(), MagicMock()
        client = self._client()
        client.on_job_event(stream_callback)
        client.on(JobEvent.JOB_FINISHED_EVENT, event_callback)

        for data in ("text", ["alfred_event_job_finished"], None):
            self._deliver("job_event", data)

        self.assertEqual(
            [c[0][0] for c in stream_callback.call_args_list],
            ["text", ["alfred_event_job_finished"], None],
        )
        event_callback.assert_not_called()

    def test_handler_called_without_data_passes_none_to_the_callback(self):
        callback = MagicMock()
        client = self._client()
        client.on_job_event(callback)

        _handlers_by_event(self.socket)["job_event"]()

        callback.assert_called_once_with(None)

    def test_dict_without_event_name_triggers_no_event_callback(self):
        stream_callback, event_callback = MagicMock(), MagicMock()
        client = self._client()
        client.on_job_event(stream_callback)
        client.on(JobEvent.JOB_FINISHED_EVENT, event_callback)

        self._deliver("job_event", {"job_id": "j1"})

        stream_callback.assert_called_once_with({"job_id": "j1"})
        event_callback.assert_not_called()

    def test_dict_with_non_string_event_name_triggers_no_event_callback(self):
        stream_callback, event_callback = MagicMock(), MagicMock()
        client = self._client()
        client.on_job_event(stream_callback)
        client.on(JobEvent.JOB_FINISHED_EVENT, event_callback)

        for name in (None, 5, ["alfred_event_job_finished"]):
            self._deliver("job_event", {"event_name": name})

        self.assertEqual(stream_callback.call_count, 3)
        event_callback.assert_not_called()

    def test_event_with_nothing_registered_for_it_does_nothing(self):
        client = self._client()
        client.on(JobEvent.JOB_FINISHED_EVENT, MagicMock())

        self._deliver("job_event", {"event_name": "alfred_event_job_start"})
        self._deliver("job_event", "text")

        self.assertEqual(self.logs.messages, [])

    def test_event_for_a_stream_with_only_stream_callback_ignores_event_name(self):
        callback = MagicMock()
        client = self._client()
        client.on_job_event(callback)

        self._deliver("job_event", {"event_name": "alfred_event_job_start"})

        callback.assert_called_once_with({"event_name": "alfred_event_job_start"})

    def test_unknown_socket_event_name_is_attached_as_a_raw_socket_event(self):
        callback = MagicMock()
        client = self._client()

        client.on("something_else", callback)
        self._deliver("something_else", {"a": 1})

        callback.assert_called_once_with({"a": 1})

    def test_unknown_socket_event_name_logs_exactly_one_warning(self):
        records = []
        handler = logging.Handler()
        handler.emit = records.append
        logging.getLogger(LOGGER_NAME).addHandler(handler)
        client = self._client()

        client.on("something_else", MagicMock())
        self._deliver("something_else", {"a": 1})

        warnings = [r for r in records if r.levelno == logging.WARNING]
        self.assertEqual(len(warnings), 1)
        message = warnings[0].getMessage()
        self.assertIn("something_else", message)
        self.assertIn("neither an event stream nor an event name", message)

    def test_event_that_is_not_text_is_attached_as_a_raw_socket_event_with_a_warning(self):
        callback = MagicMock()
        client = self._client()

        client.on(42, callback)
        self._deliver(42, "data")

        callback.assert_called_once_with("data")
        self.assertEqual(len(self.logs.messages), 1)

    def test_known_streams_and_event_names_log_no_warning(self):
        client = self._client()

        client.on("job_event", MagicMock())
        client.on("file_event", MagicMock())
        client.on("bulk_task_event", MagicMock())
        client.on("alfred_event_job_start", MagicMock())
        client.on(FileEvent.FILE_DONE_EVENT, MagicMock())

        self.assertEqual(self.logs.messages, [])

    def test_verbose_client_logs_each_received_event_once_with_the_stream_name(self):
        client = self._client(verbose=True)
        client.on_job_event(MagicMock())
        client.on(JobEvent.JOB_FINISHED_EVENT, MagicMock())
        self.logs.messages.clear()

        self._deliver("job_event", {"event_name": "alfred_event_job_finished"})

        self.assertEqual(
            self.logs.messages,
            ["Event job_event received: {'event_name': 'alfred_event_job_finished'}"],
        )

    def test_verbose_client_logs_an_event_with_nothing_registered_for_it(self):
        client = self._client(verbose=True)
        client.on(JobEvent.JOB_FINISHED_EVENT, MagicMock())
        self.logs.messages.clear()

        self._deliver("job_event", {"job_id": "j1"})

        self.assertEqual(self.logs.messages, ["Event job_event received: {'job_id': 'j1'}"])

    def test_non_verbose_client_logs_nothing_for_events(self):
        client = self._client()
        client.on_job_event(MagicMock())
        client.on(JobEvent.JOB_FINISHED_EVENT, MagicMock())

        self._deliver("job_event", {"event_name": "alfred_event_job_finished"})

        self.assertEqual(self.logs.messages, [])

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



class TestAlfredRealTimeClientWithRealSocketIO(unittest.TestCase):
    """
    Uses the real socketio.Client, with only its connection patched out, and
    delivers events through the handler registry the library keeps.
    """

    def setUp(self):
        logger = logging.getLogger(LOGGER_NAME)
        self._saved_handlers = list(logger.handlers)
        self._saved_level = logger.level
        self._saved_propagate = logger.propagate
        logger.handlers = [_CapturingHandler()]
        logger.setLevel(logging.DEBUG)
        logger.propagate = False

        connect_patcher = patch("socketio.Client.connect")
        connect_patcher.start()
        self._connect_patcher = connect_patcher

    def tearDown(self):
        self._connect_patcher.stop()
        logger = logging.getLogger(LOGGER_NAME)
        logger.handlers = self._saved_handlers
        logger.setLevel(self._saved_level)
        logger.propagate = self._saved_propagate

    def test_enum_subscription_fires_for_the_matching_event_name_only(self):
        callback = MagicMock()
        client = AlfredRealTimeClient(Configuration.v1(), AUTH_CONFIG)
        client.on(JobEvent.JOB_FINISHED_EVENT, callback)
        handler = client.socket.handlers["/"]["job_event"]

        handler({"event_name": "alfred_event_job_start"})
        callback.assert_not_called()

        handler({"event_name": "alfred_event_job_finished"})
        callback.assert_called_once_with({"event_name": "alfred_event_job_finished"})


if __name__ == "__main__":
    unittest.main()
