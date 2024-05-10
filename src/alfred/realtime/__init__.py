# 3rd Party Imports
import socketio

import src.alfred.exceptions
from src.alfred.base.config import ConfigurationDict
from src.alfred.base.constants import EventName
from src.alfred.http.typed import AuthConfiguration
from src.alfred.utils import logging


class AlfredRealtimeClient:
    def __init__(self, config: ConfigurationDict, auth_config: AuthConfiguration, verbose=False):
        """
        Initializes the AlfredRealtimeClient class.

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

        # Initialize logger
        self.logger = logging.getLogger("alfred-python")

        # Subscribe to connection life-cycle events.
        self.socket.on('connect', self.on_connect)
        self.socket.on('disconnect', self.on_disconnect)
        self.socket.on('connect_error', self.on_connect_error)

        # Establish connection with verbose output if enabled
        if self.verbose:
            self.logger.debug("Attempting to establish a connection...")
        try:
            self.socket.connect(f"{self.base_url}?apiKey={auth_config.get('api_key')}")
        except Exception as err:
            raise src.alfred.exceptions.ConnectionError(f"Could not establish connection with server: {err}")


    def on_connect(self):
        """
        Handles the 'connect' event.
        """
        if self.verbose:
            self.logger.debug(f"Successfully connected to: {self.base_url}")

    def on_disconnect(self):
        """
        Handles the 'disconnect' event.
        """
        if self.verbose:
            self.logger.debug("Disconnected from the server.")

    def on_connect_error(self, err):
        """
        Handles the 'connect_error' event.

        Args:
          err (str): The error message.
        """
        if self.verbose:
            self.logger.debug("Connection error:  %s", err)
        self.disconnect()
        raise Exception(f"Failed to connect to {self.base_url}: {err}")

    def _callback(self, event: str, callback):
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
        Handles the 'file_event' event.

        Args:
            callback (function): The callback function to handle the event.
        """
        self._callback(EventName.FILE_EVENT.value, callback)

    def on_job_event(self, callback):
        """
         Handles the 'job_event' event.

         Args:
             callback (function): The callback function to handle the event.
         """
        self._callback(EventName.JOB_EVENT.value, callback)

    def on(self, event: str, callback):
        """
        Handles a specific event.

        Args:
            event (str): The event name.
            callback (function): The callback function to handle the event.
        """
        self._callback(event, callback)

    def disconnect(self):
        """
        Disconnects client from the server.
        """
        if self.verbose:
            self.logger.debug("Closing connection...")
        self.socket.disconnect()
