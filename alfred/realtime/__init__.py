# Native Imports
from typing import Union

# 3rd Party Imports
import socketio

# Project Imports
import alfred.exceptions
from alfred.base.config import ConfigurationDict
from alfred.base.constants import EventType, FileEvent, JobEvent
from alfred.http.typed import AuthConfiguration
from alfred.utils import logging, setup_logger


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
            raise alfred.exceptions.ConnectionError(f"Could not establish connection with server: {err}")

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
        if self.verbose:
            self.logger.error("Connection error:  %s", err)
        self.disconnect()
        # trigger error callback:
        if self.error_callback:
            self.error_callback(err)

    def __callback(self, event: Union[FileEvent, JobEvent, EventType], callback):
        """
        Wrapper function to subscribe a specific event.

        Args:
            event (str): The event name.
            callback (function): The callback function to handle the event.
        """
        def handle_event(data):
            if self.verbose:
                self.logger.debug(f"Event {event} received: %s", data)
            callback(data)

        self.socket.on(event, handle_event)

    def on_file_event(self, callback):
        """
        Listens to all file-related events.

        Args:
            callback (function): The callback function to handle the event.
        """
        self.__callback(EventType.FILE_EVENT.value, callback)

    def on_job_event(self, callback):
        """
         Listens to all job-related events.

         Args:
             callback (function): The callback function to handle the event.
         """
        self.__callback(EventType.JOB_EVENT.value, callback)

    def on(self, event: Union[FileEvent, JobEvent], callback):
        """
        Listens to a specific event.

        Args:
            event (str): The event name.
            callback (function): The callback function to handle the event.
        """
        self.__callback(event, callback)

    def disconnect(self):
        """
        Disconnects client from the server.
        """
        self.logger.info("Closing connection...")
        self.socket.disconnect()

