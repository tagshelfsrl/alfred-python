class AlfredMissingAuthException(Exception):
    """
    Raised when proper authentication/authorization have not been provided.
    """


class AlfredMissingArgument(Exception):
    """
    Raised when a payload is missing a required argument based on the whole context
    of the operation.
    """
