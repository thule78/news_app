from __future__ import annotations


class UserFacingError(Exception):
    """An actionable error safe to display without leaking secrets or input."""


class StageExecutionError(UserFacingError):
    """A persisted workflow failure that can be retried safely."""
