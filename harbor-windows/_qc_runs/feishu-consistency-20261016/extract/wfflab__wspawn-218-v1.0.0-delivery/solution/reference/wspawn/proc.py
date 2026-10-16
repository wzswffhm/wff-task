"""Starting helper processes with an explicit handover of the caller's objects.

The handover is expressed to the kernel, not to the standard library: the child
is created through ``CreateProcessW`` with an extended ``STARTUPINFO`` whose
attribute list names exactly the handles that may cross. Naming the list is what
makes the handover exclusive -- without it, inheritance-enabled creation hands
over every object in the parent that carries the inherit flag.
"""

import msvcrt
import os
import subprocess
import sys

from . import _winapi
from .errors import WSpawnError


class SpawnedProcess(object):
    """A helper process started by :func:`spawn`."""

    def __init__(self, process_handle, thread_handle, pid, inherit):
        self._handle = process_handle
        self._thread = thread_handle
        self.pid = pid
        self.inherit = tuple(inherit)
        self.returncode = None

    @property
    def handle(self):
        """The process object handle, for callers that need to wait on it."""
        return self._handle

    def poll(self):
        if self.returncode is not None:
            return self.returncode
        code = _winapi.exit_code(self._handle)
        if code != _winapi.STILL_ACTIVE:
            self.returncode = code
        return self.returncode

    def wait(self, timeout=None):
        if self.returncode is not None:
            return self.returncode
        timeout_ms = 0xFFFFFFFF if timeout is None else int(max(0.0, timeout) * 1000)
        status = _winapi.wait(self._handle, timeout_ms)
        if status == _winapi.WAIT_TIMEOUT:
            raise TimeoutError("the helper did not finish in time")
        code = _winapi.exit_code(self._handle)
        self.returncode = code
        _winapi.close(self._handle)
        _winapi.close(self._thread)
        self._handle = None
        self._thread = None
        return code

    def terminate(self):
        if self._handle is None:
            return
        ok, error = _winapi.terminate(self._handle)
        if not ok:
            raise WSpawnError("the helper could not be terminated (Win32 error %d)" % error,
                              kind=_winapi.kind_for_error(error))

    def __del__(self):
        try:
            _winapi.close(self._handle)
            _winapi.close(self._thread)
        except Exception:
            pass


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


def _resolve_stream(stream, keepalive, role):
    """The object handle behind a standard-stream argument, or ``None``.

    The standard library's stream sentinels are plain integers, so they have to
    be told apart from a real object handle before anything reaches the kernel.
    A sentinel meaning "the null device" is turned into an open device handle;
    that handle has to stay open until the child exists, so it is parked in
    ``keepalive`` for the duration of the call.
    """
    if stream is None:
        return None
    if stream == subprocess.DEVNULL:
        device = open(os.devnull, "r+b", buffering=0)
        keepalive.append(device)
        return msvcrt.get_osfhandle(device.fileno())
    if stream == subprocess.PIPE:
        raise WSpawnError(
            "%s=PIPE is not supported by this launcher: the caller must supply a "
            "real file object to hand over" % role,
            kind="unsupported",
        )
    if stream == subprocess.STDOUT:
        return _resolve_stream(sys.stdout, keepalive, "stdout")
    if isinstance(stream, int):
        if stream <= 0:
            raise WSpawnError("not a usable handle for %s: %r" % (role, stream), kind="badarg")
        return stream
    try:
        fileno = stream.fileno()
    except (AttributeError, OSError, ValueError) as exc:
        raise WSpawnError("the %s stream cannot be handed over: %s" % (role, exc),
                          kind="unsupported") from exc
    if fileno < 0:
        return None
    try:
        return msvcrt.get_osfhandle(fileno)
    except OSError as exc:
        raise WSpawnError("the %s stream cannot be handed over: %s" % (role, exc),
                          kind="os") from exc


def spawn(argv, inherit=(), stdin=None, stdout=None, stderr=None):
    """Start a helper process, handing it the objects named in ``inherit``.

    Only the named handles (plus any standard stream the caller supplies) cross
    the boundary; every other inheritable object in this process stays at home.
    Returns a :class:`SpawnedProcess`.
    """
    command = _normalise_argv(argv)
    handles = _normalise_handles(inherit)
    if not _winapi.is_windows():
        raise WSpawnError(
            "an exclusive handle handover requires the Win32 process-creation API, "
            "which exists only on Windows",
            kind="unsupported",
        )

    keepalive = []
    stdin_handle = _resolve_stream(stdin, keepalive, "stdin")
    stdout_handle = _resolve_stream(stdout, keepalive, "stdout")
    stderr_handle = _resolve_stream(stderr, keepalive, "stderr")

    # The standard handles only cross when they are named, so they join the list.
    to_hand_over = list(handles)
    for extra in (stdin_handle, stdout_handle, stderr_handle):
        if extra is not None and extra not in to_hand_over:
            to_hand_over.append(extra)

    # Each named object must carry the inherit flag, or the kernel will refuse it.
    for number in to_hand_over:
        ok, error = _winapi.set_inherit(number, True)
        if not ok:
            raise WSpawnError(
                "handle %d cannot be handed over (Win32 error %d)" % (number, error),
                kind=_winapi.kind_for_error(error),
                handle=number,
            )

    process, thread, pid, error = _winapi.create_process(
        command, to_hand_over,
        stdout_handle=stdout_handle, stderr_handle=stderr_handle, stdin_handle=stdin_handle)
    if process is None:
        raise WSpawnError(
            "the helper could not be created (Win32 error %d)" % error,
            kind=_winapi.kind_for_error(error),
        )
    _winapi.close_thread(thread)
    thread = None
    return SpawnedProcess(process, thread, pid, handles)
