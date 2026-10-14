"""Hidden semantic suite for the wfflab__wspawn-218 Windows handle-handover contract.

This file is injected by the evaluation side and is never shipped in the task
package.  Every assertion that decides whether the candidate is right is backed
by a measurement the suite performs itself:

* it creates its own anonymous pipes with ``CreatePipe``,
* it flips the inherit bit with ``SetHandleInformation`` and reads it back with
  ``GetHandleInformation`` (never trusting the candidate's own report),
* it launches a child **through the candidate's** ``spawn`` and asks that child,
  in-band, which of the two pipes it could actually write to, and
* it reads the two pipes on its own read ends to confirm what really crossed.

The candidate never gets to describe its own result.
"""

import ctypes
import os
import subprocess
import sys
from ctypes import wintypes

import pytest

if os.name != "nt":
    pytest.skip(
        "the wspawn contract is a Windows handle-inheritance contract",
        allow_module_level=True,
    )

from wspawn import (  # noqa: E402  (import after the platform guard on purpose)
    WSpawnError,
    handle_kind,
    inheritable_handles,
    is_inheritable,
    set_inheritable,
    spawn,
)

# --------------------------------------------------------------- Win32 layer

GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
FILE_SHARE_ALL = 0x00000007
OPEN_EXISTING = 3
CREATE_ALWAYS = 2
FILE_ATTRIBUTE_NORMAL = 0x00000080
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

HANDLE_FLAG_INHERIT = 0x00000001
FILE_TYPE_DISK = 0x0001
FILE_TYPE_CHAR = 0x0002
FILE_TYPE_PIPE = 0x0003

_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_kernel32.CreatePipe.argtypes = [ctypes.POINTER(wintypes.HANDLE), ctypes.POINTER(wintypes.HANDLE),
                                 wintypes.LPVOID, wintypes.DWORD]
_kernel32.CreatePipe.restype = wintypes.BOOL
_kernel32.SetHandleInformation.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD]
_kernel32.SetHandleInformation.restype = wintypes.BOOL
_kernel32.GetHandleInformation.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
_kernel32.GetHandleInformation.restype = wintypes.BOOL
_kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
_kernel32.CloseHandle.restype = wintypes.BOOL
_kernel32.ReadFile.argtypes = [wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD,
                               ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID]
_kernel32.ReadFile.restype = wintypes.BOOL
_kernel32.WriteFile.argtypes = [wintypes.HANDLE, wintypes.LPCVOID, wintypes.DWORD,
                                ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID]
_kernel32.WriteFile.restype = wintypes.BOOL
_kernel32.GetFileType.argtypes = [wintypes.HANDLE]
_kernel32.GetFileType.restype = wintypes.DWORD
_kernel32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                  wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD,
                                  wintypes.HANDLE]
_kernel32.CreateFileW.restype = wintypes.HANDLE


def _last_error():
    return ctypes.get_last_error()


# ---------------------------------------------------- the child under test

CHILD_SOURCE = r'''
import ctypes
import sys
from ctypes import wintypes

k = ctypes.WinDLL("kernel32", use_last_error=True)
k.WriteFile.argtypes = [wintypes.HANDLE, wintypes.LPCVOID, wintypes.DWORD,
                        ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID]
k.WriteFile.restype = wintypes.BOOL
k.GetFileType.argtypes = [wintypes.HANDLE]
k.GetFileType.restype = wintypes.DWORD


def attempt(raw):
    h = wintypes.HANDLE(int(raw))
    kind = int(k.GetFileType(h))
    payload = b"PROBE-PAYLOAD"
    written = wintypes.DWORD(0)
    ok = bool(k.WriteFile(h, payload, len(payload), ctypes.byref(written), None))
    return "kind=%d ok=%d written=%d err=%d" % (kind, ok, written.value, ctypes.get_last_error())


def report(handle, text):
    h = wintypes.HANDLE(int(handle))
    data = (text + "\n").encode("ascii")
    written = wintypes.DWORD(0)
    return bool(k.WriteFile(h, data, len(data), ctypes.byref(written), None))


def main():
    report_handle = int(sys.argv[1])
    probe_handle = int(sys.argv[2])
    line = attempt(probe_handle)
    # try the candidate's own helpers too: a correct handover keeps the value
    if not report(report_handle, line):
        return 2
    return 0


sys.exit(main())
'''


@pytest.fixture()
def child_script(tmp_path):
    path = tmp_path / "handle_probe_child.py"
    path.write_text(CHILD_SOURCE, encoding="ascii")
    return str(path)


# ---------------------------------------------------------------- helpers

def _make_pipe():
    read_end = wintypes.HANDLE()
    write_end = wintypes.HANDLE()
    if not _kernel32.CreatePipe(ctypes.byref(read_end), ctypes.byref(write_end), None, 0):
        raise OSError(_last_error(), "CreatePipe failed")
    return read_end.value, write_end.value


def _close(handle):
    _kernel32.CloseHandle(wintypes.HANDLE(int(handle)))


def _observed_inherit(handle):
    """The inherit bit as the operating system reports it, read independently."""
    flags = wintypes.DWORD(0)
    if not _kernel32.GetHandleInformation(wintypes.HANDLE(int(handle)), ctypes.byref(flags)):
        raise OSError(_last_error(), "GetHandleInformation failed")
    return bool(flags.value & HANDLE_FLAG_INHERIT)


def _poke_inherit(handle, on=True):
    mask = HANDLE_FLAG_INHERIT
    flags = HANDLE_FLAG_INHERIT if on else 0
    if not _kernel32.SetHandleInformation(wintypes.HANDLE(int(handle)), mask, flags):
        raise OSError(_last_error(), "SetHandleInformation failed")


def _observed_kind(handle):
    return int(_kernel32.GetFileType(wintypes.HANDLE(int(handle))))


def _read_until_eof(handle):
    chunks = []
    buf = ctypes.create_string_buffer(4096)
    got = wintypes.DWORD(0)
    while _kernel32.ReadFile(wintypes.HANDLE(int(handle)), buf, 4096, ctypes.byref(got), None):
        if got.value == 0:
            break
        chunks.append(buf.raw[: got.value])
    return b"".join(chunks)


def _write(handle, blob):
    written = wintypes.DWORD(0)
    ok = _kernel32.WriteFile(wintypes.HANDLE(int(handle)), blob, len(blob),
                             ctypes.byref(written), None)
    return bool(ok), written.value


def open_scratch_file(path):
    handle = _kernel32.CreateFileW(str(path), GENERIC_READ | GENERIC_WRITE, FILE_SHARE_ALL,
                                   None, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, None)
    if handle == INVALID_HANDLE_VALUE:
        raise OSError(_last_error(), "CreateFileW failed", str(path))
    return handle


class HandoverRun(object):
    """One child launched through the candidate, with the parent's own verdict."""

    def __init__(self, status, child_report, probe_bytes, report_bytes):
        self.status = status
        self.child_report = child_report
        self.probe_bytes = probe_bytes
        self.report_bytes = report_bytes

    @property
    def child_says_probe_usable(self):
        return " ok=1 " in (" " + self.child_report + " ") or self.child_report.endswith("ok=1 written=12 err=0")

    @property
    def probe_reached_us(self):
        return b"PROBE-PAYLOAD" in self.probe_bytes


def run_handover(child_script, tmp_path, listed):
    """Launch the child with ``listed`` deciding whether probe_w is handed over.

    Returns a :class:`HandoverRun` whose fields come from the parent's own read
    ends plus the child's in-band report.
    """
    report_r, report_w = _make_pipe()
    probe_r, probe_w = _make_pipe()
    _poke_inherit(report_w, True)
    _poke_inherit(probe_w, True)

    inherit = [report_w] + ([probe_w] if listed else [])
    out_path = tmp_path / "child-stdout.txt"
    err_path = tmp_path / "child-stderr.txt"
    argv = [sys.executable, child_script, str(report_w), str(probe_w)]

    with open(out_path, "wb") as out, open(err_path, "wb") as err:
        helper = spawn(argv, inherit=inherit, stdin=subprocess.DEVNULL, stdout=out, stderr=err)
        status = helper.wait(timeout=120)

    # Drop our own copies of the write ends so the reads below can see EOF.
    _close(report_w)
    _close(probe_w)
    report_bytes = _read_until_eof(report_r)
    probe_bytes = _read_until_eof(probe_r)
    _close(report_r)
    _close(probe_r)

    return HandoverRun(status, report_bytes.decode("ascii", "replace").strip(),
                       probe_bytes, report_bytes)


# ------------------------------------------------- mechanism: exact handover

def test_listed_handle_crosses_the_boundary(child_script, tmp_path):
    run = run_handover(child_script, tmp_path, listed=True)
    assert run.status == 0, "the helper did not exit cleanly: %r" % (run.status,)
    assert run.child_report, "the helper could not report back at all"
    assert run.child_says_probe_usable, (
        "the helper could not use the handle it was promised: %s" % run.child_report)
    assert run.probe_reached_us, (
        "the promised pipe carried nothing back to the parent")


def test_unlisted_handle_does_not_cross_the_boundary(child_script, tmp_path):
    run = run_handover(child_script, tmp_path, listed=False)
    assert run.status == 0, "the helper did not exit cleanly: %r" % (run.status,)
    assert run.child_report, "the helper could not report back at all"
    assert not run.child_says_probe_usable, (
        "the helper could use a handle that was never handed over: %s" % run.child_report)
    assert not run.probe_reached_us, (
        "an object that was not handed over still carried data into the child")


def test_empty_inherit_leaks_nothing(child_script, tmp_path):
    report_r, report_w = _make_pipe()
    probe_r, probe_w = _make_pipe()
    _poke_inherit(report_w, True)
    _poke_inherit(probe_w, True)

    # Give the child a file to talk through instead, so it can still report.
    talk_path = tmp_path / "child-talk.txt"
    argv = [sys.executable, "-c",
            "import sys; open(sys.argv[1],'w').write('alive')", str(talk_path)]
    helper = spawn(argv, inherit=[], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    assert helper.wait(timeout=120) == 0
    assert talk_path.read_text(encoding="ascii") == "alive"

    # The pipe the parent still holds must not have been usable by the child,
    # which is to say nothing was written into it.
    _close(report_w)
    _close(probe_w)
    assert _read_until_eof(probe_r) == b"", "a handle crossed the boundary with an empty inherit list"
    _close(report_r)
    _close(probe_r)


def test_only_one_of_two_handed_over_pipes_crosses(child_script, tmp_path):
    """Two inheritable pipes exist; exactly one is named, so exactly one crosses."""
    report_r, report_w = _make_pipe()
    first_r, first_w = _make_pipe()
    second_r, second_w = _make_pipe()
    for handle in (report_w, first_w, second_w):
        _poke_inherit(handle, True)

    argv = [sys.executable, child_script, str(report_w), str(first_w)]
    out_path = tmp_path / "two-pipes-out.txt"
    with open(out_path, "wb") as out:
        helper = spawn(argv, inherit=[report_w, first_w], stdin=subprocess.DEVNULL,
                       stdout=out, stderr=subprocess.DEVNULL)
        assert helper.wait(timeout=120) == 0

    for handle in (report_w, first_w, second_w):
        _close(handle)
    report_bytes = _read_until_eof(report_r)
    first_bytes = _read_until_eof(first_r)
    second_bytes = _read_until_eof(second_r)
    for handle in (report_r, first_r, second_r):
        _close(handle)

    assert report_bytes, "the helper could not report back"
    assert b"PROBE-PAYLOAD" in first_bytes, "the named pipe did not cross the boundary"
    assert second_bytes == b"", (
        "a second inheritable pipe crossed the boundary although it was not named")


def test_cleared_inherit_flag_keeps_the_object_at_home(child_script, tmp_path):
    """Clearing the flag must keep the object out even when a list is not used."""
    report_r, report_w = _make_pipe()
    probe_r, probe_w = _make_pipe()
    _poke_inherit(report_w, True)
    # Start from inheritable, then ask the candidate to clear it.
    _poke_inherit(probe_w, True)
    set_inheritable(probe_w, False)
    assert _observed_inherit(probe_w) is False, (
        "the operating system still reports the object as inheritable")

    argv = [sys.executable, child_script, str(report_w), str(probe_w)]
    out_path = tmp_path / "cleared-out.txt"
    with open(out_path, "wb") as out:
        helper = spawn(argv, inherit=[report_w], stdin=subprocess.DEVNULL,
                       stdout=out, stderr=subprocess.DEVNULL)
        assert helper.wait(timeout=120) == 0

    _close(report_w)
    _close(probe_w)
    probe_bytes = _read_until_eof(probe_r)
    report_bytes = _read_until_eof(report_r)
    _close(report_r)
    _close(probe_r)

    assert report_bytes, "the helper could not report back"
    assert probe_bytes == b"", (
        "an object whose inherit flag was cleared still crossed the boundary")


# ------------------------------------------------ mechanism: inherit flag

def test_set_inheritable_changes_the_observed_flag(tmp_path):
    path = tmp_path / "flag-probe.bin"
    handle = open_scratch_file(path)
    try:
        _poke_inherit(handle, False)
        assert _observed_inherit(handle) is False
        set_inheritable(handle, True)
        assert _observed_inherit(handle) is True, (
            "the operating system still reports the object as non-inheritable")
        set_inheritable(handle, False)
        assert _observed_inherit(handle) is False, (
            "the operating system still reports the object as inheritable")
    finally:
        _close(handle)


def test_is_inheritable_matches_the_observed_flag(tmp_path):
    path = tmp_path / "flag-probe2.bin"
    handle = open_scratch_file(path)
    try:
        _poke_inherit(handle, False)
        assert is_inheritable(handle) is False
        _poke_inherit(handle, True)
        assert is_inheritable(handle) is True
        set_inheritable(handle, False)
        assert is_inheritable(handle) is False
        assert _observed_inherit(handle) is False
    finally:
        _close(handle)


# --------------------------------------------------- mechanism: kinds

def test_handle_kind_classifies_pipe_and_file(tmp_path):
    pipe_r, pipe_w = _make_pipe()
    path = tmp_path / "kind-probe.bin"
    file_handle = open_scratch_file(path)
    try:
        assert _observed_kind(pipe_r) == FILE_TYPE_PIPE, "fixture is not a pipe"
        assert _observed_kind(file_handle) == FILE_TYPE_DISK, "fixture is not a file"
        assert handle_kind(pipe_r) == "pipe", "a pipe was not reported as a pipe"
        assert handle_kind(file_handle) == "file", "a file was not reported as a file"
    finally:
        _close(pipe_r)
        _close(pipe_w)
        _close(file_handle)


def test_invalid_handle_is_rejected(tmp_path):
    path = tmp_path / "unused.bin"
    try:
        handle_kind(0)
    except WSpawnError as exc:
        assert exc.kind in ("os", "badarg", "unsupported"), "kind was %r" % (exc.kind,)
    else:
        raise AssertionError("handle_kind accepted a null handle")


# --------------------------------------------------------- regression surface

def test_spawn_reports_the_exit_code(child_script, tmp_path):
    helper = spawn([sys.executable, "-c", "raise SystemExit(7)"],
                   inherit=[], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    assert helper.wait(timeout=120) == 7


def test_spawn_captures_an_explicit_stdout(tmp_path):
    out_path = tmp_path / "captured.txt"
    with open(out_path, "wb") as out:
        helper = spawn([sys.executable, "-c", "print('captured-ok')"],
                       inherit=[], stdout=out, stderr=subprocess.DEVNULL)
        assert helper.wait(timeout=120) == 0
    assert b"captured-ok" in out_path.read_bytes()


def test_spawn_rejects_bad_arguments():
    with pytest.raises(WSpawnError) as bad_argv:
        spawn("python -c pass")
    assert bad_argv.value.kind == "badarg"
    with pytest.raises(WSpawnError) as empty_argv:
        spawn([])
    assert empty_argv.value.kind == "badarg"
    with pytest.raises(WSpawnError) as bad_inherit:
        spawn([sys.executable, "-c", "pass"], inherit=1234)
    assert bad_inherit.value.kind == "badarg"


def test_inheritable_handles_is_a_sequence():
    handles = inheritable_handles()
    assert isinstance(handles, (list, tuple))
    for item in handles:
        assert isinstance(item, int), "inheritable_handles returned a non-integer entry"


def test_visible_smoke_suite_still_passes():
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(here)
    smoke = os.path.join(here, "test_wspawn_basic.py")
    assert os.path.isfile(smoke), "the visible smoke suite was not staged next to this file"
    env = dict(os.environ)
    env["PYTHONPATH"] = root + os.pathsep + env.get("PYTHONPATH", "")
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", smoke],
        cwd=root, capture_output=True, text=True, env=env,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
