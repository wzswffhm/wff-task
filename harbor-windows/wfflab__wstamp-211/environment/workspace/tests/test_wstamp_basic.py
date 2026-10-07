"""wstamp 基础行为的可见测试（冒烟级）。"""

import os

from wstamp import snapshot_times, sync_tree


def test_snapshot_times_reports_three_fields(tmp_path):
    path = tmp_path / "a.txt"
    path.write_bytes(b"hello")
    snap = snapshot_times(str(path))
    st = os.stat(str(path))
    assert snap["mtime_ns"] == st.st_mtime_ns
    assert snap["atime_ns"] == st.st_atime_ns
    assert snap["created"] == st.st_ctime


def test_sync_creates_missing_file(tmp_path):
    src = tmp_path / "source"
    dst = tmp_path / "target"
    src.mkdir()
    (src / "a.txt").write_bytes(b"data")
    report = sync_tree(str(src), str(dst))
    assert report.created == ["a.txt"]
    assert (dst / "a.txt").read_bytes() == b"data"


def test_sync_deletes_stale_file(tmp_path):
    src = tmp_path / "source"
    dst = tmp_path / "target"
    src.mkdir()
    dst.mkdir()
    (dst / "old.txt").write_bytes(b"old")
    report = sync_tree(str(src), str(dst))
    assert report.deleted == ["old.txt"]
    assert not (dst / "old.txt").exists()
