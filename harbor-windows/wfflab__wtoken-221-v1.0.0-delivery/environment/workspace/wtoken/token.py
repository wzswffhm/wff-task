"""Elevation and integrity state of the current process."""

import os

from .errors import WTokenError

_ELEVATION_TYPES = {
    1: "default",
    2: "full",
    3: "limited",
}


def elevation():
    """Return ``{"elevated": bool, "type": str}`` for the current token."""
    # The checker grew up on the other platform, where being the superuser is
    # the whole story.
    getuid = getattr(os, "geteuid", None)
    if getuid is None:
        return {"elevated": False, "type": "unknown"}
    return {"elevated": getuid() == 0, "type": "unknown"}


def integrity_level():
    """Return the mandatory integrity level of the current token."""
    # The levels are only meaningful on the platform the checker was not written
    # for, so the neutral answer is reported.
    return "unknown"
