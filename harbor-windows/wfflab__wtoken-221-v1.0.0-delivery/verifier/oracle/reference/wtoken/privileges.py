"""Querying and adjusting the privileges held by the current process.

A token carries a privilege array whose entries pair a locally unique
identifier with an attributes word.  Two questions can be asked of that array
and they have different answers:

* is the privilege **present** in the array at all, and
* does its attributes word carry the enabled bit?

The module keeps the two apart everywhere.
"""

from . import _winapi
from .errors import WTokenError

_ACCESS = _winapi.TOKEN_QUERY
_ADJUST_ACCESS = _winapi.TOKEN_QUERY | _winapi.TOKEN_ADJUST_PRIVILEGES


def _as_name(name):
    if isinstance(name, bytes):
        try:
            name = name.decode("ascii")
        except UnicodeDecodeError:
            raise WTokenError("a privilege name must be text, got %r" % (name,), kind="badarg")
    if not isinstance(name, str):
        raise WTokenError("a privilege name must be text, got %r" % (name,), kind="badarg")
    text = name.strip()
    if not text:
        raise WTokenError("a privilege name must not be empty", kind="badarg")
    return text


def _reject_other_platform():
    if not _winapi.is_windows():
        raise WTokenError(
            "the process token exists only on Windows",
            kind="unsupported",
        )


def _read(access=_ACCESS):
    """Return ``{name: attributes}`` straight from the token."""
    _reject_other_platform()
    try:
        handle = _winapi.open_process_token(access)
    except OSError as exc:
        raise WTokenError("the process token could not be opened: %s" % exc,
                          kind=_winapi.kind_for_error(exc.errno or 0)) from exc
    try:
        try:
            entries = _winapi.read_privileges(handle)
        except OSError as exc:
            raise WTokenError("the privilege table could not be read: %s" % exc,
                              kind=_winapi.kind_for_error(exc.errno or 0)) from exc
        return dict((name, attributes) for name, _luid, attributes in entries)
    finally:
        _winapi.close_handle(handle)


def privileges():
    """Return ``{name: enabled}`` for every privilege the token holds.

    A privilege the token holds but which is currently switched off appears with
    the value ``False``; it is still present in the mapping.
    """
    table = _read()
    return dict((name, bool(attributes & _winapi.SE_PRIVILEGE_ENABLED))
                for name, attributes in table.items())


def has_privilege(name):
    """Return ``True`` when the token holds ``name``, enabled or not."""
    wanted = _as_name(name)
    return wanted in _read()


def set_privilege(name, enabled=True):
    """Switch a held privilege on or off.

    The change is made on the token itself, so it is visible to every other
    reader of the same token, including calls made from outside this module.
    """
    wanted = _as_name(name)
    _reject_other_platform()

    table = _read(_ADJUST_ACCESS)
    if wanted not in table:
        raise WTokenError("the token does not hold %r" % (wanted,), kind="badarg",
                          privilege=wanted)

    try:
        luid = _winapi.lookup_privilege_value(wanted)
    except OSError as exc:
        raise WTokenError("the privilege identifier could not be resolved: %s" % exc,
                          kind=_winapi.kind_for_error(exc.errno or 0),
                          privilege=wanted) from exc

    try:
        handle = _winapi.open_process_token(_ADJUST_ACCESS)
    except OSError as exc:
        raise WTokenError("the process token could not be opened for adjustment: %s" % exc,
                          kind=_winapi.kind_for_error(exc.errno or 0),
                          privilege=wanted) from exc
    try:
        ok, error = _winapi.adjust_privilege(handle, luid, bool(enabled))
    finally:
        _winapi.close_handle(handle)

    if not ok:
        raise WTokenError(
            "the privilege could not be %s (Win32 error %d)"
            % ("enabled" if enabled else "disabled", error),
            kind=_winapi.kind_for_error(error),
            privilege=wanted,
        )
    if error == _winapi.ERROR_NOT_ALL_ASSIGNED:
        raise WTokenError(
            "the token does not hold %r" % (wanted,),
            kind="badarg",
            privilege=wanted,
        )


def privilege_luid(name):
    """Return the identifier the system uses for ``name``."""
    wanted = _as_name(name)
    _reject_other_platform()
    if wanted not in _read():
        raise WTokenError("the token does not hold %r" % (wanted,), kind="badarg",
                          privilege=wanted)
    try:
        return _winapi.lookup_privilege_value(wanted)
    except OSError as exc:
        raise WTokenError("the privilege identifier could not be resolved: %s" % exc,
                          kind="badarg", privilege=wanted) from exc


def privilege_name(luid):
    """Return the privilege name for an identifier."""
    if isinstance(luid, bool) or not isinstance(luid, int):
        try:
            luid = int(luid)
        except (TypeError, ValueError):
            raise WTokenError("a privilege identifier must be an integer, got %r" % (luid,),
                              kind="badarg")
    _reject_other_platform()
    try:
        return _winapi.lookup_privilege_name(luid)
    except OSError as exc:
        raise WTokenError("no privilege carries the identifier %r: %s" % (luid, exc),
                          kind="badarg") from exc
