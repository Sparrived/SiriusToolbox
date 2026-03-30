class SiriusToolboxError(Exception):
    """Base error for all application exceptions."""


class ValidationError(SiriusToolboxError):
    """Raised when a payload does not match expected shape."""


class CollectorError(SiriusToolboxError):
    """Raised when an external source collector fails."""


class StorageError(SiriusToolboxError):
    """Raised when persistence layer fails."""


class LoginRequiredError(SiriusToolboxError):
    """Raised when a source requires user login before collection can continue."""


class UserCancelledError(SiriusToolboxError):
    """Raised when user closes browser window and cancels an interactive task."""
