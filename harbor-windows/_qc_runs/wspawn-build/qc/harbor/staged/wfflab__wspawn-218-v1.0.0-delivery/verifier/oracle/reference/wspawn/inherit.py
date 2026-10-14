"""Inheritance flags for the objects the host hands to its helpers.

The flag lives on the *object handle*, not on a descriptor, so it is read and
written with the handle-level API. Clearing it is what keeps an object at home
even when a child is created with inheritance enabled.
"""

import os

from . import _winapi
from .errors import WSpawnError

#: The handles this process has been told to make inheritable. Windows offers no
#: cheap way to walk another party's object table, so the module records what it
#: was asked to do and reports that set.
_TRACKED = set()


def _as_handle(handle):
    if isinstance(handle, bool) or not isinstance(handle, int):
        try:
            handle = int(handle)
        except (TypeError, ValueError):
            raise WSpawnError("handle must be an integer, got %r" % (handle,), kind="badarg")
    return handle


def _reject_other_platform(handle):
    if not _winapi.is_windows():
        raise WSpawnError(
            "object handles exist only on Windows",
            kind="unsupported",
            handle=handle,
        )


def set_inheritable(handle, enabled=True):
    """Mark ``handle`` as transferable to child processes, or stop it being so."""
    number = _as_handle(handle)
    _reject_other_platform(number)
    if number <= 0:
        raise WSpawnError("not a usable object handle: %r" % (handle,), kind="badarg", handle=handle)

    ok, error = _winapi.set_inherit(number, bool(enabled))
    if not ok:
        raise WSpawnError(
            "the inherit flag could not be changed (Win32 error %d)" % error,
            kind=_winapi.kind_for_error(error),
            handle=number,
        )
    if enabled:
        _TRACKED.add(number)
    else:
        _TRACKED.discard(number)


def is_inheritable(handle):
    """Return ``True`` when ``handle`` is currently transferable."""
    number = _as_handle(handle)
    _reject_other_platform(number)
    if number <= 0:
        raise WSpawnError("not a usable object handle: %r" % (handle,), kind="badarg", handle=handle)

    inherit, ok, error = _winapi.get_inherit(number)
    if not ok:
        raise WSpawnError(
            "the inherit flag could not be read (Win32 error %d)" % error,
            kind=_winapi.kind_for_error(error),
            handle=number,
        )
    return inherit


def inheritable_handles():
    """Return the objects this process is known to have made transferable."""
    alive = []
    for number in sorted(_TRACKED):
        try:
            if is_inheritable(number):
                alive.append(number)
        except WSpawnError:
            continue
    return alive
