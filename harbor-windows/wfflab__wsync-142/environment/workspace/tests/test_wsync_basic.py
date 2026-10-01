"""wsync 自带的基础行为测试。"""

from __future__ import annotations

import os
from pathlib import Path

from wsync import build_plan, sync_tree


def write(path, text, mtime=None):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    if mtime is not None:
        os.utime(path, (mtime, mtime))
    return path


def test_creates_missing_file(tmp_path):
    source = tmp_path / "source"
    target = tmp_path / "target"
    write(source / "hello.txt", "hello")

    result = sync_tree(str(source), str(target))

    assert (target / "hello.txt").read_text(encoding="utf-8") == "hello"
    assert result.created == ["hello.txt"]
    assert result.ok


def test_updates_changed_file(tmp_path):
    source = tmp_path / "source"
    target = tmp_path / "target"
    write(target / "notes.txt", "old", mtime=1_600_000_000)
    write(source / "notes.txt", "new", mtime=1_700_000_000)

    result = sync_tree(str(source), str(target))

    assert (target / "notes.txt").read_text(encoding="utf-8") == "new"
    assert result.updated == ["notes.txt"]


def test_deletes_stale_file(tmp_path):
    source = tmp_path / "source"
    target = tmp_path / "target"
    write(source / "keep.txt", "keep")
    write(target / "stale.tmp", "stale")

    result = sync_tree(str(source), str(target))

    assert not (target / "stale.tmp").exists()
    assert result.deleted == ["stale.tmp"]


def test_keeps_identical_file(tmp_path):
    source = tmp_path / "source"
    target = tmp_path / "target"
    write(target / "same.txt", "same", mtime=1_600_000_000)
    write(source / "same.txt", "same", mtime=1_600_000_000)

    result = sync_tree(str(source), str(target))

    assert result.updated == []
    assert result.kept == ["same.txt"]


def test_nested_tree_is_mirrored(tmp_path):
    source = tmp_path / "source"
    target = tmp_path / "target"
    write(source / "a" / "b" / "deep.txt", "deep")

    sync_tree(str(source), str(target))

    assert (target / "a" / "b" / "deep.txt").read_text(encoding="utf-8") == "deep"


def test_dry_run_does_not_touch_target(tmp_path):
    source = tmp_path / "source"
    target = tmp_path / "target"
    write(source / "new.txt", "new")
    write(target / "stale.txt", "stale")

    result = sync_tree(str(source), str(target), dry_run=True)

    assert (target / "stale.txt").exists()
    assert not (target / "new.txt").exists()
    assert sorted(result.created + result.deleted) == ["new.txt", "stale.txt"]


def test_plan_actions(tmp_path):
    source = tmp_path / "source"
    target = tmp_path / "target"
    write(source / "added.txt", "a")
    write(source / "changed.txt", "v2", mtime=1_700_000_000)
    write(target / "changed.txt", "v1", mtime=1_600_000_000)
    write(target / "removed.txt", "r")

    plan = build_plan(str(source), str(target))
    by_action = {action: sorted(e.relpath for e in plan.by_action(action))
                 for action in ("create", "update", "delete")}

    assert by_action["create"] == ["added.txt"]
    assert by_action["update"] == ["changed.txt"]
    assert by_action["delete"] == ["removed.txt"]
