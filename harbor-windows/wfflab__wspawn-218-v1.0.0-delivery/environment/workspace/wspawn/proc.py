"""Starting helper processes with a handover of the caller's objects."""

import os
import subprocess

from .errors import WSpawnError


class SpawnedProcess(object):
    """A helper process started by :func:`spawn`."""

    def __init__(self, popen, inherit):
        self._popen = popen
        self.inherit = tuple(inherit)
        self.pid = popen.pid
        self.returncode = None

    def wait(self, timeout=None):
        self.returncode = self._popen.wait(timeout=timeout)
        return self.returncode

    def poll(self):
        self.returncode = self._popen.poll()
        return self.returncode

    def terminate(self):
        self._popen.terminate()


def _normalise_argv(argv):
    if isinstance(argv, (str, bytes)):
        raise WSpawnError("argv must be a sequence of arguments, not a single string", kind="badarg")
    try:
        items = [os.fspath(item) for item in argv]
    except TypeError as exc:
        raise WSpawnError("argv must be an iterable of paths: %s" % exc, kind="badarg") from exc
    if not items:
        raise WSpawnError("argv must not be empty", kind="badarg")
    return items


def _normalise_handles(inherit):
    if inherit is None:
        return ()
    if isinstance(inherit, int):
        raise WSpawnError("inherit must be a sequence of handles, not a single handle", kind="badarg")
    try:
        return tuple(int(item) for item in inherit)
    except (TypeError, ValueError) as exc:
        raise WSpawnError("inherit must contain integer handles: %s" % exc, kind="badarg") from exc


def spawn(argv, inherit=(), stdin=None, stdout=None, stderr=None):
    """Start a helper process, handing it the objects named in ``inherit``.

    Returns a :class:`SpawnedProcess`.
    """
    command = _normalise_argv(argv)
    handles = _normalise_handles(inherit)

    kwargs = {
        # The helper is expected to need the objects it is handed, so close_fds
        # stays off; otherwise the log pipe is gone before the helper starts.
        "close_fds": False,
        "stdin": stdin,
        "stdout": stdout,
        "stderr": stderr,
    }
    try:
        popen = subprocess.Popen(command, **kwargs)
    except OSError as exc:
        raise WSpawnError(str(exc), kind="os") from exc
    return SpawnedProcess(popen, handles)
