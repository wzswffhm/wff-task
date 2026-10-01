"""wexec 的基础行为测试（仓库自带，不得修改）。"""

import os

import pytest

from wexec import CommandNotFound, resolve, run, search_dirs


def test_search_dirs_follows_path(monkeypatch, tmp_path):
    monkeypatch.setenv("PATH", str(tmp_path))
    assert search_dirs() == [str(tmp_path)]


def test_resolve_finds_system_executable():
    assert os.path.isfile(resolve("cmd"))


def test_resolve_returns_absolute_path():
    assert os.path.isabs(resolve("cmd"))


def test_resolve_missing_command_raises():
    with pytest.raises(CommandNotFound):
        resolve("definitely-not-a-real-command-xyz")


def test_run_returns_completed_process():
    proc = run(["cmd", "/c", "exit 0"])
    assert proc.returncode == 0
