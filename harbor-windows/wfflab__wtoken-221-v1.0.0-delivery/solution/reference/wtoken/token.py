"""Elevation and integrity state of the current process.

Elevation is not the same question as "is this the superuser": a token records
whether it is elevated and which flavour of elevation it is, and separately
carries a mandatory integrity label that the system enforces on writes.
"""

from . import _winapi
from .errors import WTokenError

_ELEVATION_TYPES = _winapi.ELEVATION_TYPE_NAMES
_INTEGRITY_NAMES = _winapi.INTEGRITY_NAMES


def _reject_other_platform():
    if not _winapi.is_windows():
        raise WTokenError(
            "the process token exists only on Windows",
            kind="unsupported",
        )


def elevation():
    """Return ``{"elevated": bool, "type": str}`` for the current token."""
    _reject_other_platform()
    try:
        handle = _winapi.open_process_token(_winapi.TOKEN_QUERY)
    except OSError as exc:
        raise WTokenError("the process token could not be opened: %s" % exc,
                          kind=_winapi.kind_for_error(exc.errno or 0)) from exc
    try:
        try:
            elevated = bool(_winapi.get_token_dword(handle, _winapi.TokenElevation))
            kind = int(_winapi.get_token_dword(handle, _winapi.TokenElevationType))
        except OSError as exc:
            raise WTokenError("the elevation state could not be read: %s" % exc,
                              kind=_winapi.kind_for_error(exc.errno or 0)) from exc
    finally:
        _winapi.close_handle(handle)
    return {"elevated": elevated, "type": _ELEVATION_TYPES.get(kind, "unknown")}


def integrity_level():
    """Return the mandatory integrity level of the current token."""
    _reject_other_platform()
    try:
        handle = _winapi.open_process_token(_winapi.TOKEN_QUERY)
    except OSError as exc:
        raise WTokenError("the process token could not be opened: %s" % exc,
                          kind=_winapi.kind_for_error(exc.errno or 0)) from exc
    try:
        try:
            rid = _winapi.integrity_rid(handle)
        except OSError as exc:
            raise WTokenError("the integrity level could not be read: %s" % exc,
                              kind=_winapi.kind_for_error(exc.errno or 0)) from exc
    finally:
        _winapi.close_handle(handle)

    name = _INTEGRITY_NAMES.get(rid)
    if name is None:
        raise WTokenError("unknown integrity level 0x%x" % rid, kind="unsupported")
    return name
