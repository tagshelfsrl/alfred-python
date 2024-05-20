class ConnectionError(Exception):
    """
    Raised when a connection error occurs.
    """
    def __init__(self, message="A connection error occurred"):
        self.message = message
        super().__init__(self.message)
