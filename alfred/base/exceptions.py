# The classes live in ``alfred.exceptions``; these names stay importable from
# here for existing code.
from alfred.exceptions import AlfredMissingArgument, AlfredMissingAuthException

__all__ = ["AlfredMissingAuthException", "AlfredMissingArgument"]
