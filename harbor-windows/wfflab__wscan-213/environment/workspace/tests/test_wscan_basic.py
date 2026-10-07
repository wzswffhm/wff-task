"""wscan 基础行为的可见测试（冒烟级）。"""

import os

from wscan import dedupe, scan_tree


def test_scan_simple_tree(tmp_path):
    root = str(tmp_path)
    with open(os.path.join(root, "a.txt"), "wb") as f:
        f.write(b"hello")
    os.makedirs(os.path.join(root, "sub"))
    with open(os.path.join(root, "sub", "b.txt"), "wb") as f:
        f.write(b"world!")
    result = scan_tree(root)
    assert result.files == ["a.txt", "sub\\b.txt"]
    assert result.total_bytes == 11


def test_dedupe_noop_for_unique_files(tmp_path):
    root = str(tmp_path)
    with open(os.path.join(root, "a.txt"), "wb") as f:
        f.write(b"one")
    with open(os.path.join(root, "b.txt"), "wb") as f:
        f.write(b"two")
    assert dedupe(root) == []
    with open(os.path.join(root, "a.txt"), "rb") as f:
        assert f.read() == b"one"
