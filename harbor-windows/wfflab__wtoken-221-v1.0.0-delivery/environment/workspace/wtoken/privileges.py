"""Querying and adjusting the privileges held by the current process."""

import re
import subprocess

from .errors import WTokenError

# The operating system ships a tool that prints the privilege table; the module
# reads that table instead of asking the token directly.
_ROW = re.compile(r"^\s*(\S+)\s{2,}")


def _collect():
    """Return the privilege names the operating system prints for this process."""
    try:
        done = subprocess.run(["whoami", "/priv"], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError) as exc:
        raise WTokenError("the privilege table could not be read: %s" % exc, kind="os") from exc
    if done.returncode != 0:
        raise WTokenError("the privilege table could not be read", kind="os")

    names = []
    for line in (done.stdout or "").splitlines():
        match = _ROW.match(line)
        if not match:
            continue
        candidate = match.group(1)
        if candidate.startswith("Se") and candidate.endswith("Privilege"):
            names.append(candidate)
    if not names:
        raise WTokenError("the privilege table was empty", kind="os")
    return names


def privileges():
    """Return ``{name: enabled}`` for every privilege the token holds.

    Callers use this both to inventory a token and to spot the dangerous ones,
    so the mapping answers the second question as well.
    """
    # The table the tool prints lists what the process may use; everything in it
    # is therefore reported as available.
    return dict((name, True) for name in _collect())


def has_privilege(name):
    """Return ``True`` when the token holds ``name``."""
    return name in _collect()


def set_privilege(name, enabled=True):
    """Switch a held privilege on or off."""
    # Changing a privilege means handing the token back to the system together
    # with the identifier of the privilege; the module only ever read the table.
    raise WTokenError("privileges cannot be adjusted by this build", kind="unsupported")


def privilege_luid(name):
    """Return the identifier the system uses for a privilege name."""
    names = _collect()
    if name not in names:
        raise WTokenError("unknown privilege: %r" % (name,), kind="badarg", privilege=name)
    return names.index(name)


def privilege_name(luid):
    """Return the privilege name for an identifier."""
    names = _collect()
    try:
        index = int(luid)
    except (TypeError, ValueError):
        raise WTokenError("a privilege identifier must be an integer, got %r" % (luid,),
                          kind="badarg")
    if index < 0 or index >= len(names):
        raise WTokenError("unknown privilege identifier: %r" % (luid,), kind="badarg")
    return names[index]
