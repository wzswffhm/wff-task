"""wproc 的可见回归测试（仓库自带，不得改动）。

只覆盖最基本的公开契约：成功、退出码、输出合并、工作目录、环境替换、
输出量、超时标志与参数校验。更细的 Windows 进程树语义由隐藏测试覆盖。
"""

from __future__ import annotations

import os
import sys

import pytest

from wproc import CommandFailed, run

PY = sys.executable


def _py(code: str) -> list:
    return [PY, "-c", code]


def test_success_captures_output():
    result = run(_py("print('hello-wproc')"), timeout=60)
    assert result.returncode == 0
    assert result.ok
    assert "hello-wproc" in result.text()


def test_nonzero_exit_code_is_preserved():
    result = run(_py("import sys; sys.exit(3)"), timeout=60)
    assert result.returncode == 3
    assert not result.ok
    assert result.timed_out is False


def test_stderr_is_merged_into_output():
    result = run(
        _py("import sys; sys.stderr.write('to-stderr\\n'); print('to-stdout')"),
        timeout=60,
    )
    text = result.text()
    assert "to-stderr" in text
    assert "to-stdout" in text


def test_cwd_is_honoured(tmp_path):
    workdir = tmp_path / "workdir"
    workdir.mkdir()
    result = run(_py("import os; print(os.getcwd())"), cwd=str(workdir), timeout=60)
    assert str(workdir) in result.text()


def test_env_replaces_the_parent_environment(monkeypatch):
    monkeypatch.setenv("WPROC_PARENT_ONLY", "1")
    env = {
        "SystemRoot": os.environ.get("SystemRoot", r"C:\Windows"),
        "WPROC_MARK": "yes",
    }
    result = run(
        _py(
            "import os;"
            "print('mark=' + os.environ.get('WPROC_MARK', '<missing>'));"
            "print('parent=' + ('present' if 'WPROC_PARENT_ONLY' in os.environ else 'absent'))"
        ),
        env=env,
        timeout=60,
    )
    text = result.text()
    assert "mark=yes" in text
    assert "parent=absent" in text


def test_large_output_of_a_finished_child_is_collected():
    code = (
        "import sys;"
        "chunk='x'*4096;"
        "sys.stdout.write('BEGIN');"
        "sys.stdout.write(chunk*128);"
        "sys.stdout.write('END')"
    )
    result = run(_py(code), timeout=120)
    assert result.returncode == 0
    assert result.output.count(b"x") == 4096 * 128
    assert b"BEGIN" in result.output and b"END" in result.output


def test_check_raises_command_failed_with_result():
    with pytest.raises(CommandFailed) as excinfo:
        run(_py("import sys; print('boom'); sys.exit(4)"), timeout=60, check=True)
    assert excinfo.value.result.returncode == 4
    assert "boom" in excinfo.value.result.text()


def test_timeout_sets_the_timed_out_flag():
    result = run(_py("import time; time.sleep(300)"), timeout=2)
    assert result.timed_out is True


def test_string_command_is_rejected():
    with pytest.raises(TypeError):
        run("python -c print(1)", timeout=10)


def test_empty_command_is_rejected():
    with pytest.raises(ValueError):
        run([], timeout=10)
