"""wjob 的基础行为测试（仓库自带，不得修改）。"""

import pytest

from wjob import find_powershell, run_script


def test_powershell_is_available():
    assert find_powershell()


def test_simple_output():
    result = run_script("Write-Output 'hello'")
    assert result.stdout.strip() == "hello"


def test_ok_property_is_true_on_success():
    assert run_script("Write-Output 1").ok is True


def test_result_repr_mentions_exit_code():
    result = run_script("Write-Output 1")
    assert "exit_code" in repr(result)


def test_environment_info_lists_powershell():
    from wjob import environment_info

    assert environment_info()["powershell"]
