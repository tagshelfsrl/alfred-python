# 3rd Party Imports
import socketio

from src.alfred.base.config import ConfigurationDict
from src.alfred.base.constants import EventName
from src.alfred.http.typed import AuthConfiguration
from src.alfred.utils import logging


class AlfredChannel:
    def __init__(self, config: ConfigurationDict, auth_config: AuthConfiguration, verbose=False):
        self.socket = socketio.Client()
        self.verbose = verbose
        self.config = config
        self.auth_config = auth_config

        # Initialize logger
        self.logger = logging.getLogger("alfred-python")

        # Establish connection with verbose output if enabled
        if self.verbose:
            self.logger.debug("Attempting to establish a connection...")
        self.socket.connect(f"{config.get('base_url')}?apiKey={auth_config.get('api_key')}")

        self.socket.on('connect', self.on_connect)
        self.socket.on('disconnect', self.on_disconnect)
        self.socket.on('connect_error', self.on_connect_error)

    def on_connect(self):
        if self.verbose:
            self.logger.debug("Connected successfully to:", self.config.get("base_url"))

    def on_disconnect(self):
        if self.verbose:
            self.logger.debug("Disconnected from the server.")

    def on_connect_error(self, err):
        if self.verbose:
            self.logger.debug("Connection error:", err)
        self.disconnect()
        raise Exception(f"Failed to connect to {self.config.get('base_url')}: {err}")

    def _callback(self, event: str, callback):
        def handle_event(data):
            if self.verbose:
                self.logger.debug(f"Event {event} received:", data)
            callback(data)

        self.socket.on(event, handle_event)

    def on_file_event(self, callback):
        self._callback(EventName.FILE_EVENT.value, callback)

    def on_job_event(self, callback):
        self._callback(EventName.JOB_EVENT.value, callback)

    def on(self, event: str, callback):
        self._callback(event, callback)

    def disconnect(self):
        if self.verbose:
            self.logger.debug("Closing connection...")
        self.socket.disconnect()
