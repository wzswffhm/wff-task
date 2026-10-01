"""wdl 的基础行为测试（仓库自带，不得修改）。"""

import os

import pytest

from wdl import archive_tree, copy_file, read_stream, stream_exists, write_stream
from wdl.streams import ZONE_STREAM, stream_path


@pytest.fixture()
def sample(tmp_path):
    path = tmp_path / "report.pdf"
    path.write_bytes(b"PDF")
    return path


def test_stream_roundtrip(sample):
    write_stream(str(sample), ZONE_STREAM, b"[ZoneTransfer]\r\nZoneId=3\r\n")
    assert stream_exists(str(sample), ZONE_STREAM)
    assert b"ZoneId=3" in read_stream(str(sample), ZONE_STREAM)


def test_stream_path_uses_colon_syntax(sample):
    assert stream_path(str(sample), ZONE_STREAM).endswith("report.pdf:Zone.Identifier")


def test_copy_preserves_content(sample, tmp_path):
    dst = tmp_path / "copy.pdf"
    copy_file(str(sample), str(dst))
    assert dst.read_bytes() == b"PDF"


def test_archive_tree_returns_relative_paths(tmp_path):
    src = tmp_path / "src"
    (src / "sub").mkdir(parents=True)
    (src / "a.txt").write_bytes(b"a")
    (src / "sub" / "b.txt").write_bytes(b"b")

    done = archive_tree(str(src), str(tmp_path / "dst"))

    assert done == [os.path.join("sub", "b.txt"), "a.txt"] or done == ["a.txt", os.path.join("sub", "b.txt")]
    assert (tmp_path / "dst" / "sub" / "b.txt").read_bytes() == b"b"
