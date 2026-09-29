#!/usr/bin/env python3
"""Behavior-driven verifier for block-storage-c-feature-20260813-1515
(nbd-server treefiles export semantics).

Scenarios run at import time; /var/tmp/programmatic_score.json is written for
test.sh. Each scenario drives a real nbd-server over a raw NBD protocol client
and inspects observable file-system state (tree block files appearing under
the export base directory).

Correct behavior contract:
  * a treefiles export stores each 4KiB block in a file under the export
    base directory (FILExxxx), routed by offset,
  * reads return the block data / zeros for never-written blocks,
  * a plain (non-treefiles) export still reads/writes a single file.
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
PAGE = 4096
# construct_path(): < FILE%04X with pos/TREEPAGESIZE % TREEDIRSIZE
def _block_file(base: Path, off: int) -> Path:
    return base / ("FILE%04X" % (off // PAGE))


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


def _setup_tree_export(tmp: Path, port: int):
    base = tmp / "treeexp"
    conf = tmp / "nbd.conf"
    conf.write_text(
        f"[generic]\n\tport = {port}\n"
        f"[export]\n\texportname = {base}\n"
        f"\tfilesize = 1048576\n"
        f"\ttreefiles = true\n",
        encoding="utf-8",
    )
    return base, conf


def _scenario_treefiles_write_read():
    """Writes at several offsets land in separate block files under the export
    base; read-back returns the written patterns."""
    _ensure_built()
    port = _port()
    with tempfile.TemporaryDirectory(prefix="nbd-tree-") as td:
        tmp = Path(td)
        base, conf = _setup_tree_export(tmp, port)
        srv, pidfile = _start_server(tmp, conf, port)
        c = nbd_proto.NbdClient("127.0.0.1", port)
        try:
            c.negotiate(b"export")
            spots = [(0, 0xA1), (PAGE, 0xB2), (512 * 1024, 0xC3)]
            for off, val in spots:
                c.write(off, bytes([val]) * PAGE)
            for off, val in spots:
                got = c.read(off, PAGE)
                assert got == bytes([val]) * PAGE, f"read-back failed at {off}"
            for off, val in spots:
                bf = _block_file(base, off)
                assert bf.is_file(), f"block file missing: {bf}"
                assert bf.read_bytes() == bytes([val]) * PAGE, f"block content wrong: {bf}"
        finally:
            c.close()
            _stop_server(srv, pidfile)


def _scenario_treefiles_unwritten_read():
    """Reading a never-written block returns zeros; no block file for it."""
    _ensure_built()
    port = _port()
    with tempfile.TemporaryDirectory(prefix="nbd-tree-") as td:
        tmp = Path(td)
        base, conf = _setup_tree_export(tmp, port)
        srv, pidfile = _start_server(tmp, conf, port)
        c = nbd_proto.NbdClient("127.0.0.1", port)
        try:
            c.negotiate(b"export")
            got = c.read(2 * PAGE, PAGE)
            assert got == b"\0" * PAGE, "unwritten block did not read as zeros"
        finally:
            c.close()
            _stop_server(srv, pidfile)


def _scenario_plain_export_untouched():
    """Without the treefiles option, writes still go straight to one file."""
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
            payload = bytes([0xAB]) * PAGE
            c.write(0, payload)
            got = c.read(0, PAGE)
            assert got == payload
            head = export.read_bytes()[:PAGE]
            assert head == payload
        finally:
            c.close()
            _stop_server(srv, pidfile)


_SCENARIOS = [
    ("test_treefiles_write_read", _scenario_treefiles_write_read),
    ("test_treefiles_unwritten_read", _scenario_treefiles_unwritten_read),
    ("test_plain_export_untouched", _scenario_plain_export_untouched),
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
