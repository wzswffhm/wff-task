"""Deterministic behavioral checks for nbd-client netlink persist mode.

All tests validate observable process behavior (CLI output, process
residency, exit timing) — no source-code string matching.
"""

from __future__ import annotations

import os
import signal
import subprocess
import tempfile
import time
from pathlib import Path

NBD_DIR = Path("/app/nbd")
CLIENT = NBD_DIR / "nbd-client"
SERVER = NBD_DIR / "nbd-server"
MOCK_SRC = NBD_DIR / "tests/run/libnl_mock.c"


def _run(cmd, **kwargs):
    return subprocess.run(
        cmd,
        text=True,
        capture_output=True,
        **kwargs,
    )


def _ensure_built():
    assert NBD_DIR.is_dir(), f"missing tree: {NBD_DIR}"
    if not CLIENT.is_file() or not SERVER.is_file():
        if not (NBD_DIR / "Makefile").is_file():
            _run(["autoreconf", "-fi"], cwd=NBD_DIR, check=True)
            _run(["./configure", "--prefix=/usr"], cwd=NBD_DIR, check=True)
        r = _run(["make", "-j", str(os.cpu_count() or 2), "nbd-client", "nbd-server"], cwd=NBD_DIR)
        assert r.returncode == 0, f"build failed:\n{r.stdout}\n{r.stderr}"
    assert CLIENT.is_file() and os.access(CLIENT, os.X_OK)
    assert SERVER.is_file() and os.access(SERVER, os.X_OK)


def _usage_text() -> str:
    r = _run([str(CLIENT)], check=False)
    return (r.stdout or "") + (r.stderr or "")


def _wait_for_pidfile(pidfile: Path, attempts: int = 50, delay: float = 0.1):
    """Poll for server pidfile instead of a fixed sleep."""
    for _ in range(attempts):
        if pidfile.is_file():
            return
        time.sleep(delay)
    raise AssertionError(f"server pidfile not created: {pidfile}")


def _build_mock(tmp: Path) -> Path:
    so = tmp / "libnl_mock.so"
    assert MOCK_SRC.is_file(), f"missing mock source: {MOCK_SRC}"
    text = MOCK_SRC.read_text(encoding="utf-8", errors="replace")
    text = text.replace('#include "../../nbd-netlink.h"', '#include "nbd-netlink.h"')
    fixed = tmp / "libnl_mock.c"
    fixed.write_text(text, encoding="utf-8")
    cflags = _run(["pkg-config", "--cflags", "libnl-genl-3.0"], check=True).stdout.split()
    libs = _run(["pkg-config", "--libs", "libnl-genl-3.0"], check=True).stdout.split()
    cmd = [
        "cc",
        "-fPIC",
        "-shared",
        "-o",
        str(so),
        str(fixed),
        "-I",
        str(NBD_DIR),
        "-ldl",
        *cflags,
        *libs,
    ]
    r = _run(cmd)
    assert r.returncode == 0, f"mock build failed:\n{r.stdout}\n{r.stderr}"
    return so


def _start_server(tmp: Path):
    """Start nbd-server and wait until pidfile appears."""
    export_file = tmp / "export.bin"
    export_file.write_bytes(b"\0" * (1024 * 1024))
    conf = tmp / "nbd.conf"
    pidfile = tmp / "nbd.pid"
    conf.write_text(
        "[generic]\n[export]\n\texportname = %s\n" % export_file,
        encoding="utf-8",
    )
    srv = subprocess.Popen(
        [str(SERVER), "-C", str(conf), "-p", str(pidfile)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    _wait_for_pidfile(pidfile)
    return srv, pidfile


def _cleanup_server(srv, pidfile: Path):
    if srv.poll() is None:
        srv.send_signal(signal.SIGTERM)
        try:
            srv.wait(timeout=5)
        except subprocess.TimeoutExpired:
            srv.kill()
            srv.wait(timeout=5)
    if pidfile.is_file():
        try:
            os.kill(int(pidfile.read_text().strip()), signal.SIGTERM)
        except Exception:
            pass


def _cleanup_proc(proc):
    if proc.poll() is None:
        proc.kill()
        proc.wait(timeout=5)


def test_dead_timeout_cli_documented():
    """The -dead-timeout option must appear in CLI help/usage text."""
    _ensure_built()
    usage = _usage_text().lower()
    assert "dead-timeout" in usage or "dead timeout" in usage


def test_persist_mode_stays_resident_under_mock():
    """With -persist on netlink path, client must NOT exit after configure.

    This is a behavioral test: we start the client and verify it is still
    running after a grace period. If it exits immediately, persist mode is
    not working. The timeout is the observation window — not a fixed sleep.
    """
    _ensure_built()
    with tempfile.TemporaryDirectory(prefix="nbd-persist-") as td:
        tmp = Path(td)
        srv, pidfile = _start_server(tmp)
        try:
            mock = _build_mock(tmp)
            env = os.environ.copy()
            env["LD_PRELOAD"] = str(mock)
            proc = subprocess.Popen(
                [
                    str(CLIENT),
                    "-N",
                    "export",
                    "127.0.0.1",
                    "/dev/nbd0",
                    "-persist",
                    "-dead-timeout",
                    "30",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                env=env,
            )
            try:
                out, _ = proc.communicate(timeout=3.0)
                # If communicate returns, the process exited — persist not working.
                raise AssertionError(
                    f"persist client exited early code={proc.returncode} out:\n{out}"
                )
            except subprocess.TimeoutExpired:
                # Timed out waiting => process is still resident. Good.
                proc.send_signal(signal.SIGTERM)
                try:
                    proc.communicate(timeout=3.0)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.communicate(timeout=3.0)
            finally:
                _cleanup_proc(proc)
        finally:
            _cleanup_server(srv, pidfile)


def test_non_persist_mode_exits_quickly():
    """Without -persist, the client should exit (not hang) after configure.

    This is the behavioral contrast to the persist test: without -persist the
    client must not stay resident. We assert it exits within a few seconds.
    """
    _ensure_built()
    with tempfile.TemporaryDirectory(prefix="nbd-nopersist-") as td:
        tmp = Path(td)
        srv, pidfile = _start_server(tmp)
        try:
            mock = _build_mock(tmp)
            env = os.environ.copy()
            env["LD_PRELOAD"] = str(mock)
            proc = subprocess.Popen(
                [
                    str(CLIENT),
                    "-N",
                    "export",
                    "127.0.0.1",
                    "/dev/nbd0",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                env=env,
            )
            try:
                out, _ = proc.communicate(timeout=5.0)
                # Process must have exited — that's the expected non-persist behavior.
                assert proc.returncode is not None, "client did not exit in non-persist mode"
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.communicate(timeout=3.0)
                raise AssertionError("non-persist client stayed resident unexpectedly")
            finally:
                _cleanup_proc(proc)
        finally:
            _cleanup_server(srv, pidfile)


def test_dead_timeout_default_applied():
    """When -persist is given without -dead-timeout, the client must still
    stay resident — the default timeout should be applied automatically.

    This verifies the 'sensible default' behavior without checking source code.
    """
    _ensure_built()
    with tempfile.TemporaryDirectory(prefix="nbd-default-timeout-") as td:
        tmp = Path(td)
        srv, pidfile = _start_server(tmp)
        try:
            mock = _build_mock(tmp)
            env = os.environ.copy()
            env["LD_PRELOAD"] = str(mock)
            proc = subprocess.Popen(
                [
                    str(CLIENT),
                    "-N",
                    "export",
                    "127.0.0.1",
                    "/dev/nbd0",
                    "-persist",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                env=env,
            )
            try:
                out, _ = proc.communicate(timeout=3.0)
                raise AssertionError(
                    f"persist client (default timeout) exited early code={proc.returncode} out:\n{out}"
                )
            except subprocess.TimeoutExpired:
                # Still running — default timeout was applied. Good.
                proc.send_signal(signal.SIGTERM)
                try:
                    proc.communicate(timeout=3.0)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.communicate(timeout=3.0)
            finally:
                _cleanup_proc(proc)
        finally:
            _cleanup_server(srv, pidfile)
