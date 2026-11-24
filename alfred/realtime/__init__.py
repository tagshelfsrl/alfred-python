# Native Imports
from enum import Enum
from typing import Union
from urllib.parse import quote

# 3rd Party Imports
import socketio

# Project Imports
import alfred.exceptions
from alfred.base.config import ConfigurationDict
from alfred.base.constants import LEGACY_EVENT_NAMES, EventType, FileEvent, JobEvent
from alfred.http.typed import AuthConfiguration
from alfred.utils import logging, setup_logger

# Socket events ("streams") Alfred emits; the kind of each event is in the
# `event_name` field of its data.
EVENT_STREAMS = ("job_event", "file_event", "bulk_task_event")

# Event-name prefix -> the stream that carries those events.
EVENT_NAME_STREAMS = {
    "alfred_event_job_": "job_event",
    "alfred_event_file_": "file_event",
    "alfred_event_bulk_task_": "bulk_task_event",
}

# Events Alfred has no name of its own for: it announces each under the name
# of another event, and the data tells them apart.
#   subscription name -> (event_name Alfred sends, test on the event data)
REFINED_EVENTS = {
    FileEvent.FILE_REMOVE_TAG_EVENT.value: (
        FileEvent.FILE_CHANGE_TAG_EVENT.value,
        lambda data: data.get("tag_being_removed_id") is not None,
    ),
    JobEvent.JOB_EXCEEDED_RETRIES_EVENT.value: (
        JobEvent.JOB_RETRY_EVENT.value,
        lambda data: data.get("exceeded_retries") is True,
    ),
}


class AlfredRealTimeClient:
    def __init__(self, config: ConfigurationDict, auth_config: AuthConfiguration, verbose=False, error_callback=None, on_connect=None):
        """
        Initializes the AlfredRealTimeClient class.

        Args:
           config (ConfigurationDict): The configuration dictionary.
           auth_config (AuthConfiguration): The authentication configuration.
           verbose (bool, optional): Whether to print verbose output. Defaults to False.
        """
        self.socket = socketio.Client()
        self.verbose = verbose
        self.config = config
        self.auth_config = auth_config
        self.base_url = config.get("realtime_url")
        self.error_callback = error_callback
        self.on_connect = on_connect

        # Subscriptions: callbacks by stream and by event name, and the
        # streams the socket already listens on. Set before connecting.
        self.__stream_callbacks = {}
        self.__event_callbacks = {}
        self.__listening = set()

        # Initialize logger
        self.logger = logging.getLogger("alfred-python")
        if self.logger.level == logging.NOTSET:
            setup_logger({
                "level": "DEBUG" if verbose else "INFO",
                "name": "alfred-python"
            })

        # Subscribe to connection life-cycle events.
        self.socket.on('connect', self.__on_connect)
        self.socket.on('disconnect', self.__on_disconnect)
        self.socket.on('connect_error', self.__on_connect_error)

        # Establish connection with verbose output if enabled
        if self.verbose:
            self.logger.debug("Attempting to establish a connection...")
        try:
            self.socket.connect(f"{self.base_url}?apiKey={auth_config.get('api_key')}")
        except Exception as err:
            # The underlying error quotes the connection URL, API key included:
            # redact it, and do not chain the original exception, whose own
            # message would put the key back into tracebacks.
            raise alfred.exceptions.ConnectionError(
                f"Could not establish connection with server: {self.__redact(str(err))}"
            ) from None

    def __on_connect(self):
        """
        Handles the 'connect' event.
        """
        self.logger.info(f"Successfully connected to: {self.base_url}")
        if self.on_connect:
            self.on_connect()

    def __on_disconnect(self):
        """
        Handles the 'disconnect' event.
        """
        if self.verbose:
            self.logger.info("Disconnected from the server.")

    def __on_connect_error(self, err):
        """
        Handles the 'connect_error' event.

        Args:
          err (str): The error message.
        """
        err = self.__redact(err)
        if self.verbose:
            self.logger.error("Connection error:  %s", err)
        self.disconnect()
        # trigger error callback:
        if self.error_callback:
            self.error_callback(err)

    def __redact(self, value):
        """
        Removes the API key from text that quotes the connection URL, which
        carries the key as a query parameter. Anything that is not text is
        returned as it is.
        """
        api_key = self.auth_config.get("api_key")
        if not isinstance(api_key, str) or not api_key or not isinstance(value, str):
            return value
        for secret in (api_key, quote(api_key, safe="")):
            value = value.replace(secret, "[redacted]")
        return value

    def on_file_event(self, callback):
        """
        Listens to every event on the file stream (`file_event`).

        Args:
            callback (function): Called with the event data of each file event.
                Registering again replaces the earlier callback.
        """
        self.on(EventType.FILE_EVENT, callback)

    def on_job_event(self, callback):
        """
        Listens to every event on the job stream (`job_event`).

        Args:
            callback (function): Called with the event data of each job event.
                Registering again replaces the earlier callback.
        """
        self.on(EventType.JOB_EVENT, callback)

    def on(self, event: Union[FileEvent, JobEvent, EventType, str], callback):
        """
        Listens to one kind of event, or to a whole stream.

        Alfred sends events on a few streams (`job_event`, `file_event`); the
        kind of each event is in its `event_name` field. The SDK listens on
        the right stream and calls the callback only for matching events.

        Args:
            event (FileEvent | JobEvent | EventType | str): A member of the
                event enums, an event name such as "alfred_event_job_finished"
                (names used by earlier versions, such as "job_finished_event",
                still work), or a stream name such as "job_event" to receive
                every event on that stream.
            callback (function): Called with the event data. Registering again
                for the same event replaces the earlier callback.

        FileEvent.FILE_REMOVE_TAG_EVENT and JobEvent.JOB_EXCEEDED_RETRIES_EVENT
        have no event name of their own on the server: Alfred sends them as a
        change of tag and as a retry. The SDK recognises them from the event
        data, so each is a subscription of its own.
        """
        name = event.value if isinstance(event, Enum) else event
        if isinstance(name, str):
            name = LEGACY_EVENT_NAMES.get(name, name)

        if isinstance(name, str):
            for prefix, stream in EVENT_NAME_STREAMS.items():
                if name.startswith(prefix):
                    self.__event_callbacks[name] = callback
                    self.__listen(stream)
                    return

        if name not in EVENT_STREAMS:
            self.logger.warning(
                "%r is neither an event stream nor an event name the SDK knows; "
                "its callback will only fire if the server emits a socket event with that name.",
                name,
            )
        self.__stream_callbacks[name] = callback
        self.__listen(name)

    def __listen(self, stream):
        """
        Attaches the socket handler of a stream, once for the life of the client.
        """
        if stream in self.__listening:
            return
        self.__listening.add(stream)

        def handle_event(data=None):
            self.__dispatch(stream, data)

        self.socket.on(stream, handle_event)

    def __dispatch(self, stream, data):
        """
        Calls the callback of the stream, then the callbacks of the event the
        data describes. Every one of them runs, even when an earlier one raises;
        the first error is raised once all have run.
        """
        if self.verbose:
            self.logger.debug("Event %s received: %s", stream, data)

        callbacks = [self.__stream_callbacks.get(stream)]
        event_name = data.get("event_name") if isinstance(data, dict) else None
        if isinstance(event_name, str):
            callbacks.append(self.__event_callbacks.get(event_name))
            for name, (sent_as, matches) in REFINED_EVENTS.items():
                if event_name == sent_as and matches(data):
                    callbacks.append(self.__event_callbacks.get(name))

        error = None
        for callback in callbacks:
            if callback is None:
                continue
            try:
                callback(data)
            except Exception as err:
                if error is None:
                    error = err
        if error is not None:
            raise error

    def disconnect(self):
        """
        Disconnects client from the server.
        """
        self.logger.info("Closing connection...")
        self.socket.disconnect()

