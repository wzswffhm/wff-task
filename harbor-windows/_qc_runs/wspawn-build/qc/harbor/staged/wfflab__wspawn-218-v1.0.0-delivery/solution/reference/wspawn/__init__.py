"""wspawn -- start sandboxed helper processes with an explicit handle handover.

The sandbox host keeps a handful of objects open (a log pipe, an input pipe, a
scratch file) and must hand a *subset* of them to the helper it launches.  The
helper is untrusted: anything it can reach is something it can read, write or
keep alive.

Public API
----------

``spawn(argv, inherit=(), stdin=None, stdout=None, stderr=None)``
    Start a helper process, handing it the objects named in ``inherit``.
``set_inheritable(handle, enabled=True)``
    Mark an object as transferable to child processes, or stop it being so.
``is_inheritable(handle)``
    Report whether an object is currently transferable.
``inheritable_handles()``
    Every object in this process that is currently transferable.
``handle_kind(handle)``
    ``"file"`` / ``"pipe"`` / ``"console"`` / ``"unknown"``.
``WSpawnError``
    Carries a ``kind`` of ``unsupported`` / ``os`` / ``badarg``.

See ``docs/NOTES.md`` for how the module was originally laid out.
"""

from .errors import WSpawnError
from .inherit import inheritable_handles, is_inheritable, set_inheritable
from .kinds import handle_kind
from .proc import SpawnedProcess, spawn

__all__ = [
    "WSpawnError",
    "SpawnedProcess",
    "spawn",
    "set_inheritable",
    "is_inheritable",
    "inheritable_handles",
    "handle_kind",
]

__version__ = "0.3.1"
