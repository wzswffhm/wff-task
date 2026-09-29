#!/usr/bin/env python3
"""Behavior-driven verifier for block-storage-c-feature-20260812-1459
(nbd-server copy-on-write export semantics).

Scenarios run at import time; /var/tmp/programmatic_score.json is written for
test.sh. Each scenario drives a real nbd-server over a raw NBD protocol
client and inspects observable file-system state (backing file contents,
diff files appearing / disappearing).

Correct behavior contract (no symptom leaks here):
  * a copy-on-write export never writes through to the backing file;
    writes land in a per-session diff file,
  * a read on a COW export returns the diff's data (read-through),
  * the session diff file is removed when the client disconnects,
  * a plain (non-COW) export still writes straight to the backing file.
"""
import json
import os
import random
import signal
import subprocess
import tempfile
import time
from pathlib import Path

try:
    import pytest
except ImportError:  # pragma: no cover
    pytest = None

import nbd_proto

WS = Path(os.environ.get("WORKSPACE", "/workspace/nbd"))
SCRATCH = Path("/var/tmp")
SCRATCH.mkdir(exist_ok=True)
SERVER = WS / "nbd-server"

_PORT_BASE = 21000 + (os.getpid() % 500) * 10


def _port() -> int:
    return _PORT_BASE + random.randint(0, 9)


def _ensure_built():
    if not SERVER.is_file():
        subprocess.run(
            ["make", "-j", str(os.cpu_count() or 2), "nbd-server"],
            cwd=WS,
            check=True,
            capture_output=True,
        )
    assert SERVER.is_file() and os.access(SERVER, os.X_OK)


def _start_server(tmp: Path, conf: Path, port: int):
    import socket

    pidfile = tmp / "nbd.pid"
    srv = subprocess.Popen(
        [str(SERVER), "-C", str(conf), "-p", str(pidfile)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(200):
        if pidfile.is_file():
            break
        time.sleep(0.05)
    for _ in range(100):
        try:
            s = socket.create_connection(("127.0.0.1", port), timeout=0.3)
            s.close()
            return srv, pidfile
        except OSError:
            time.sleep(0.1)
    _stop_server(srv, pidfile)
    raise RuntimeError("server did not start")


def _stop_server(srv, pidfile):
    if pidfile is not None:
        try:
            os.kill(int(pidfile.read_text().strip()), signal.SIGTERM)
            time.sleep(0.3)
        except (OSError, ValueError):
            pass
    if srv is not None:
        try:
            srv.wait(timeout=3)
        except subprocess.TimeoutExpired:
            srv.kill()
            try:
                srv.wait(timeout=3)
            except subprocess.TimeoutExpired:
                pass


def _setup_cow_export(tmp: Path, port: int):
    export = tmp / "export.bin"
    export.write_bytes(b"\0" * (1024 * 1024))
    cowdir = tmp / "cowdir"
    cowdir.mkdir()
    conf = tmp / "nbd.conf"
    conf.write_text(
        f"[generic]\n\tport = {port}\n"
        f"[export]\n\texportname = {export}\n"
        f"\tcopyonwrite = true\n\tcowdir = {cowdir}\n",
        encoding="utf-8",
    )
    return export, cowdir, conf


def _any_diff_files(cowdir: Path) -> bool:
    return any(cowdir.iterdir())


def _scenario_write_does_not_touch_backing():
    """A WRITE on a COW export must not modify the backing file, and a diff
    file must exist while the session is live."""
    _ensure_built()
    port = _port()
    with tempfile.TemporaryDirectory(prefix="nbd-cow-") as td:
        tmp = Path(td)
        export, cowdir, conf = _setup_cow_export(tmp, port)
        srv, pidfile = _start_server(tmp, conf, port)
        c = nbd_proto.NbdClient("127.0.0.1", port)
        try:
            c.negotiate(b"export")
            c.write(0, bytes([0xAB]) * 4096)
            head = export.read_bytes()[:4096]
            assert head == b"\0" * 4096
            assert _any_diff_files(cowdir)
        finally:
            c.close()
            _stop_server(srv, pidfile)


def _scenario_read_returns_written():
    """A READ after a WRITE on a COW export returns new data while the
    backing file stays pristine (data must come from the diff)."""
    _ensure_built()
    port = _port()
    with tempfile.TemporaryDirectory(prefix="nbd-cow-") as td:
        tmp = Path(td)
        export, cowdir, conf = _setup_cow_export(tmp, port)
        srv, pidfile = _start_server(tmp, conf, port)
        c = nbd_proto.NbdClient("127.0.0.1", port)
        try:
            c.negotiate(b"export")
            payload = bytes([0xCD]) * 4096
            c.write(0, payload)
            got = c.read(0, 4096)
            assert got == payload
            assert _any_diff_files(cowdir)
        finally:
            c.close()
            _stop_server(srv, pidfile)


def _scenario_diff_cleaned_up():
    """A live COW session has a diff file; after disconnect it is removed."""
    _ensure_built()
    port = _port()
    with tempfile.TemporaryDirectory(prefix="nbd-cow-") as td:
        tmp = Path(td)
        export, cowdir, conf = _setup_cow_export(tmp, port)
        srv, pidfile = _start_server(tmp, conf, port)
        c = nbd_proto.NbdClient("127.0.0.1", port)
        try:
            c.negotiate(b"export")
            c.write(0, bytes([0x11]) * 4096)
            assert _any_diff_files(cowdir)
        finally:
            c.close()
        time.sleep(0.5)
        assert not _any_diff_files(cowdir)
        _stop_server(srv, pidfile)


def _scenario_plain_export_untouched():
    """Without the COW option, writes still go straight to the backing file."""
    _ensure_built()
    port = _port()
    with tempfile.TemporaryDirectory(prefix="nbd-plain-") as td:
        tmp = Path(td)
        export = tmp / "export.bin"
        export.write_bytes(b"\0" * (1024 * 1024))
        conf = tmp / "nbd.conf"
        conf.write_text(
            f"[generic]\n\tport = {port}\n"
            f"[export]\n\texportname = {export}\n",
            encoding="utf-8",
        )
        srv, pidfile = _start_server(tmp, conf, port)
        c = nbd_proto.NbdClient("127.0.0.1", port)
        try:
            c.negotiate(b"export")
            c.write(0, bytes([0xAB]) * 4096)
            head = export.read_bytes()[:4096]
            assert head == bytes([0xAB]) * 4096
        finally:
            c.close()
            _stop_server(srv, pidfile)


PAGE = 4096


def _scenario_partial_page_write_merges():
    """A partial-page WRITE (offset 100, len 500) must merge with the pristine
    backing page: read-back returns zeros | payload | zeros and the backing
    file stays untouched. Only a real copy-on-write merge can satisfy this."""
    _ensure_built()
    port = _port()
    with tempfile.TemporaryDirectory(prefix="nbd-cow-") as td:
        tmp = Path(td)
        export, cowdir, conf = _setup_cow_export(tmp, port)
        srv, pidfile = _start_server(tmp, conf, port)
        c = nbd_proto.NbdClient("127.0.0.1", port)
        try:
            c.negotiate(b"export")
            payload = bytes(range(256)) * 2  # 512 bytes, non-uniform
            c.write(100, payload)
            got = c.read(0, 700)
            expected = b"\0" * 100 + payload + b"\0" * (700 - 100 - len(payload))
            assert got == expected, "partial-page write did not merge with backing page"
            assert export.read_bytes()[:PAGE] == b"\0" * PAGE, "backing page modified"
        finally:
            c.close()
            _stop_server(srv, pidfile)


def _scenario_cross_page_write():
    """A WRITE spanning the 4KiB page boundary (offset 4096-100, len 500)
    must land in two diff pages and read back correctly."""
    _ensure_built()
    port = _port()
    with tempfile.TemporaryDirectory(prefix="nbd-cow-") as td:
        tmp = Path(td)
        export, cowdir, conf = _setup_cow_export(tmp, port)
        srv, pidfile = _start_server(tmp, conf, port)
        c = nbd_proto.NbdClient("127.0.0.1", port)
        try:
            c.negotiate(b"export")
            payload = bytes([0x5A]) * 500
            off = PAGE - 100  # 3996: 100 bytes in page 0, 400 in page 1
            c.write(off, payload)
            got = c.read(off, 500)
            assert got == payload, "cross-page write did not read back"
            # surrounding bytes must stay pristine
            before = c.read(off - 100, 100)
            after = c.read(off + 500, 100)
            assert before == b"\0" * 100 and after == b"\0" * 100
            assert export.read_bytes()[:PAGE * 2] == b"\0" * (PAGE * 2)
        finally:
            c.close()
            _stop_server(srv, pidfile)


def _scenario_session_isolation():
    """Diff files are per-session: after disconnect, a new connection reads
    the pristine backing data (previous session's writes are gone)."""
    _ensure_built()
    port = _port()
    with tempfile.TemporaryDirectory(prefix="nbd-cow-") as td:
        tmp = Path(td)
        export, cowdir, conf = _setup_cow_export(tmp, port)
        srv, pidfile = _start_server(tmp, conf, port)
        try:
            c1 = nbd_proto.NbdClient("127.0.0.1", port)
            c1.negotiate(b"export")
            c1.write(0, bytes([0x77]) * 4096)
            assert _any_diff_files(cowdir)
            c1.close()
            time.sleep(0.5)
            assert not _any_diff_files(cowdir), "diff not cleaned between sessions"
            c2 = nbd_proto.NbdClient("127.0.0.1", port)
            c2.negotiate(b"export")
            got = c2.read(0, 4096)
            assert got == b"\0" * 4096, "second session saw previous session's data"
            c2.close()
        finally:
            _stop_server(srv, pidfile)


def _scenario_multiple_offsets():
    """Writes at several offsets (0, mid, near-end) all track their diff pages
    independently; read-back at every offset returns the written pattern."""
    _ensure_built()
    port = _port()
    with tempfile.TemporaryDirectory(prefix="nbd-cow-") as td:
        tmp = Path(td)
        export, cowdir, conf = _setup_cow_export(tmp, port)
        srv, pidfile = _start_server(tmp, conf, port)
        c = nbd_proto.NbdClient("127.0.0.1", port)
        try:
            c.negotiate(b"export")
            size = 1024 * 1024
            spots = [(0, 0xA0), (size // 2, 0xB1), (size - PAGE, 0xC2)]
            for off, val in spots:
                c.write(off, bytes([val]) * PAGE)
            for off, val in spots:
                got = c.read(off, PAGE)
                assert got == bytes([val]) * PAGE, f"read-back failed at {off}"
            assert export.read_bytes()[:PAGE] == b"\0" * PAGE
        finally:
            c.close()
            _stop_server(srv, pidfile)


def _scenario_waitfile_commit():
    """waitfile mode: backing file does not exist at startup; writes buffer in
    a diff file and the backing file must NOT be created; while the client is
    still connected, SIGUSR1 commits the buffered writes to the backing file."""
    _ensure_built()
    port = _port()
    with tempfile.TemporaryDirectory(prefix="nbd-wait-") as td:
        tmp = Path(td)
        pending = tmp / "pending.bin"  # deliberately NOT created yet
        cowdir = tmp / "cowdir"
        cowdir.mkdir()
        conf = tmp / "nbd.conf"
        conf.write_text(
            f"[generic]\n\tport = {port}\n"
            f"[export]\n\texportname = {pending}\n"
            f"\tfilesize = 1048576\n"
            f"\twaitfile = true\n\tcowdir = {cowdir}\n",
            encoding="utf-8",
        )
        srv, pidfile = _start_server(tmp, conf, port)
        c = nbd_proto.NbdClient("127.0.0.1", port)
        try:
            c.negotiate(b"export")
            payload = bytes([0xE1]) * PAGE
            c.write(0, payload)
            # while waiting, the backing file must not exist; data lives in diff
            assert not pending.exists(), "backing file created during waitfile wait"
            assert _any_diff_files(cowdir), "no diff file in waitfile mode"
            # create the backing file and poke the whole server process group
            pending.write_bytes(b"\0" * (1024 * 1024))
            pid = int(pidfile.read_text().strip())
            try:
                os.killpg(os.getpgid(pid), signal.SIGUSR1)
            except (OSError, ProcessLookupError):
                os.kill(pid, signal.SIGUSR1)
            deadline = time.time() + 8
            committed = False
            while time.time() < deadline:
                if pending.read_bytes()[:PAGE] == payload:
                    committed = True
                    break
                time.sleep(0.3)
            assert committed, "waitfile commit did not write payload to backing file"
            # post-commit read-back comes from the committed backing file
            got = c.read(0, PAGE)
            assert got == payload, "read-back after commit mismatch"
        finally:
            c.close()
            _stop_server(srv, pidfile)


_SCENARIOS = [
    ("test_write_does_not_touch_backing_file", _scenario_write_does_not_touch_backing),
    ("test_read_returns_written_data", _scenario_read_returns_written),
    ("test_diff_cleaned_up_on_disconnect", _scenario_diff_cleaned_up),
    ("test_plain_export_untouched", _scenario_plain_export_untouched),
    ("test_partial_page_write_merges", _scenario_partial_page_write_merges),
    ("test_cross_page_write", _scenario_cross_page_write),
    ("test_session_isolation", _scenario_session_isolation),
    ("test_multiple_offsets", _scenario_multiple_offsets),
    ("test_waitfile_commit", _scenario_waitfile_commit),
]

_RESULTS = []
_SUITE_ERROR = None

try:
    for _name, _fn in _SCENARIOS:
        try:
            _fn()
            _RESULTS.append({"name": _name, "ok": True})
        except Exception as _exc:  # noqa: BLE001
            _RESULTS.append(
                {"name": _name, "ok": False, "message": str(_exc)[:800]}
            )
except Exception as _exc:  # noqa: BLE001
    _SUITE_ERROR = str(_exc)[:800]

# ---- expose as pytest tests -------------------------------------------
if pytest is not None:
    for _item in _RESULTS:
        def _make(_i):
            def _test():
                if not _i.get("ok"):
                    pytest.fail(_i.get("message", "assertion failed"))
            return _test

        globals()[_item["name"]] = _make(_item)

    if _SUITE_ERROR is not None:
        def _test_suite_harness_failed():
            pytest.fail(_SUITE_ERROR)

        globals()["test_suite_harness_failed"] = _test_suite_harness_failed

# ---- write programmatic score for test.sh ----------------------------
_passed = sum(1 for r in _RESULTS if r.get("ok"))
_total = len(_RESULTS)
_score = (_passed / _total) if _total else 0.0
(SCRATCH / "programmatic_score.json").write_text(json.dumps({
    "programmatic_score": _score,
    "test_pass_rate": _score,
    "tests_passed": _passed,
    "tests_total": _total,
    "passed_tests": [r.get("name") for r in _RESULTS if r.get("ok")],
    "failed_tests": [
        {"name": r.get("name"), "message": (r.get("message") or "")[:800]}
        for r in _RESULTS if not r.get("ok")
    ],
    "suite_error": _SUITE_ERROR,
}, indent=2), encoding="utf-8")
