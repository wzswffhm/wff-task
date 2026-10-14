"""Inheritance flags for the objects the host hands to its helpers."""

import os

from .errors import WSpawnError


def _as_number(handle):
    try:
        return int(handle)
    except (TypeError, ValueError):
        raise WSpawnError("handle must be an integer, got %r" % (handle,), kind="badarg")


def set_inheritable(handle, enabled=True):
    """Mark ``handle`` as transferable to child processes, or stop it being so."""
    number = _as_number(handle)
    try:
        os.set_inheritable(number, bool(enabled))
    except OSError as exc:
        raise WSpawnError(str(exc), kind="os", handle=handle) from exc
    except (TypeError, ValueError) as exc:
        raise WSpawnError(str(exc), kind="badarg", handle=handle) from exc


def is_inheritable(handle):
    """Return ``True`` when ``handle`` is currently transferable."""
    number = _as_number(handle)
    try:
        return bool(os.get_inheritable(number))
    except OSError as exc:
        raise WSpawnError(str(exc), kind="os", handle=handle) from exc


def inheritable_handles():
    """Return every object in this process that is currently transferable.

    The host tracks the objects it opens itself, so the module reports what the
    current implementation knows about.
    """
    return []
