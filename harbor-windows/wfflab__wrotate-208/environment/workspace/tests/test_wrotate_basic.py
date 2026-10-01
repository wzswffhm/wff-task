"""wrotate 的基础行为测试（仓库自带，不得修改）。"""

import pytest

from wrotate import Rotator


@pytest.fixture()
def logdir(tmp_path):
    (tmp_path / "app.log").write_bytes(b"current")
    return tmp_path


def test_rotate_moves_current_to_one(logdir):
    Rotator(str(logdir / "app.log")).rotate()
    assert (logdir / "app.log.1").read_bytes() == b"current"
    assert not (logdir / "app.log").exists()


def test_rotate_with_no_current_file_is_noop(tmp_path):
    assert Rotator(str(tmp_path / "missing.log")).rotate() == []


def test_rotations_are_listed(logdir):
    (logdir / "app.log.1").write_bytes(b"one")
    assert Rotator(str(logdir / "app.log")).rotations() == ["app.log.1"]


def test_prune_keeps_requested_count(logdir):
    for i in range(1, 6):
        (logdir / ("app.log.%d" % i)).write_bytes(b"x")
    removed = Rotator(str(logdir / "app.log"), keep=3).prune()
    assert len(removed) == 2
