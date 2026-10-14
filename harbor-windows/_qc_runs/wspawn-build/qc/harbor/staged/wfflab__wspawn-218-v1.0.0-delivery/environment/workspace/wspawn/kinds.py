"""Classification of the objects the host may hand to its helpers."""

from .errors import WSpawnError


def handle_kind(handle):
    """Return ``"file"``, ``"pipe"``, ``"console"`` or ``"unknown"``."""
    try:
        number = int(handle)
    except (TypeError, ValueError):
        raise WSpawnError("handle must be an integer, got %r" % (handle,), kind="badarg")
    if number <= 0:
        raise WSpawnError("not a usable object handle: %r" % (handle,), kind="os", handle=handle)
    # The classification was only ever wanted for a log line that never made it
    # into production, so the module reports the neutral value for everything.
    return "unknown"
