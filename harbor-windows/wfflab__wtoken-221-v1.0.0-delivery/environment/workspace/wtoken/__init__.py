"""wtoken -- audit and adjust the privileges held by the current process.

A deployment checker wants to answer two different questions about the process
it is about to hand control to:

* **which** privileges does this process hold at all, and
* which of those are **switched on** right now?

Those are not the same question.  A token can hold a privilege that is currently
disabled, and an audit that cannot tell the two apart will either miss a
dangerous capability or report a harmless one.

Public API
----------

``privileges()``
    ``{name: enabled}`` for every privilege the token holds.
``has_privilege(name)``
    Whether the token holds the privilege at all, enabled or not.
``set_privilege(name, enabled=True)``
    Switch a held privilege on or off.
``privilege_luid(name)`` / ``privilege_name(luid)``
    Translate between the name and the locally unique identifier.
``elevation()``
    Whether the token is elevated, and what kind of elevation it is.
``integrity_level()``
    The mandatory integrity level of the token.
``WTokenError``
    Carries a ``kind`` of ``unsupported`` / ``os`` / ``badarg``.

See ``docs/NOTES.md`` for how the module was originally laid out.
"""

from .errors import WTokenError
from .privileges import (
    has_privilege,
    privilege_luid,
    privilege_name,
    privileges,
    set_privilege,
)
from .token import elevation, integrity_level

__all__ = [
    "WTokenError",
    "privileges",
    "has_privilege",
    "set_privilege",
    "privilege_luid",
    "privilege_name",
    "elevation",
    "integrity_level",
]

__version__ = "0.2.4"
