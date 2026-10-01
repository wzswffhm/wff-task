"""wtextio 的基础行为测试（仓库自带，不得修改）。"""

import pytest

from wtextio import append_text, detect_bom, read_lines, read_text, write_text


def test_ascii_roundtrip(tmp_path):
    path = tmp_path / "a.txt"
    write_text(str(path), "hello world")
    assert read_text(str(path)) == "hello world"


def test_returns_written_length(tmp_path):
    path = tmp_path / "b.txt"
    assert write_text(str(path), "abcde") == 5


def test_append(tmp_path):
    path = tmp_path / "c.txt"
    write_text(str(path), "one\r\n")
    append_text(str(path), "two\r\n")
    assert read_lines(str(path)) == ["one", "two"]


def test_crlf_newlines(tmp_path):
    path = tmp_path / "d.txt"
    write_text(str(path), "line1\nline2")
    assert path.read_bytes() == b"line1\r\nline2"


def test_detect_bom_absent(tmp_path):
    path = tmp_path / "e.txt"
    write_text(str(path), "plain")
    assert detect_bom(str(path)) is None
