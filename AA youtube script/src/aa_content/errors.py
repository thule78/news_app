class UserFacingError(Exception):
    """An actionable error safe to display without leaking input or secrets."""


class StageExecutionError(UserFacingError):
    """A persisted workflow failure that can be retried safely."""
