"""Smoke tests for the wspawn public API.

These are the tests that run while the sandbox host is being developed. They
exercise the module's contract against the interpreter itself as the helper.
"""

import os
import subprocess
import sys

import pytest

from wspawn import (
    WSpawnError,
    handle_kind,
    inheritable_handles,
    is_inheritable,
    set_inheritable,
    spawn,
)

PY = sys.executable


def echo(code="print('helper-ok')"):
    return [PY, "-c", code]


def test_spawn_runs_a_helper_and_reports_the_exit_code():
    helper = spawn(echo(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    assert helper.pid > 0
    assert helper.wait(timeout=60) == 0


def test_spawn_reports_a_nonzero_exit_code():
    helper = spawn(echo("import sys; sys.exit(3)"),
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    assert helper.wait(timeout=60) == 3


def test_spawn_captures_an_explicit_stdout(tmp_path):
    out_file = tmp_path / "helper-out.txt"
    with open(out_file, "wb") as handle:
        helper = spawn(echo(), stdout=handle, stderr=subprocess.DEVNULL)
        assert helper.wait(timeout=60) == 0
    assert b"helper-ok" in out_file.read_bytes()


def test_spawn_rejects_a_bare_string_as_argv():
    with pytest.raises(WSpawnError) as caught:
        spawn("python -c pass")
    assert caught.value.kind == "badarg"


def test_spawn_rejects_an_empty_argv():
    with pytest.raises(WSpawnError) as caught:
        spawn([])
    assert caught.value.kind == "badarg"


def test_spawn_rejects_a_bare_integer_as_inherit():
    with pytest.raises(WSpawnError) as caught:
        spawn(echo(), inherit=1234)
    assert caught.value.kind == "badarg"


def test_spawn_rejects_a_non_integer_inherit_entry():
    with pytest.raises(WSpawnError) as caught:
        spawn(echo(), inherit=["not-a-handle"])
    assert caught.value.kind == "badarg"


def test_spawn_reports_a_missing_executable_as_an_os_error():
    with pytest.raises(WSpawnError) as caught:
        spawn([os.path.join(os.sep, "no", "such", "helper.exe")])
    assert caught.value.kind == "os"


def test_inheritable_handles_returns_a_sequence():
    handles = inheritable_handles()
    assert isinstance(handles, (list, tuple))


def test_is_inheritable_reports_a_boolean_or_a_typed_error():
    try:
        value = is_inheritable(0)
    except WSpawnError as exc:
        assert exc.kind in WSpawnError.KINDS
    else:
        assert isinstance(value, bool)


def test_set_inheritable_reports_a_typed_error_for_an_unusable_handle():
    with pytest.raises(WSpawnError) as caught:
        set_inheritable(999999999, True)
    assert caught.value.kind in WSpawnError.KINDS


def test_handle_kind_returns_a_string_for_a_plausible_handle():
    try:
        kind = handle_kind(1)
    except WSpawnError as exc:
        assert exc.kind in WSpawnError.KINDS
    else:
        assert kind in ("file", "pipe", "console", "unknown")


def test_handle_kind_rejects_a_non_integer():
    with pytest.raises(WSpawnError) as caught:
        handle_kind("nope")
    assert caught.value.kind == "badarg"
