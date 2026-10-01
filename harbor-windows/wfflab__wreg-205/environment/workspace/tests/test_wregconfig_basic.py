"""wregconfig 的基础行为测试（仓库自带，不得修改）。"""

import uuid
import winreg

import pytest

from wregconfig import ConfigError, ConfigStore

BASE = r"SOFTWARE\WFFlabBench\wregconfig-basic"


@pytest.fixture()
def store():
    path = "%s\\%s" % (BASE, uuid.uuid4().hex)
    node = ConfigStore(winreg.HKEY_LOCAL_MACHINE, path)
    yield node
    try:
        node.delete_tree()
    except OSError:
        pass


def test_write_then_read(store):
    store.write("Mode", "fast")
    assert store.read("Mode") == "fast"


def test_read_missing_raises(store):
    with pytest.raises(ConfigError):
        store.read("Nope")


def test_read_missing_returns_default(store):
    assert store.read("Nope", default="fallback") == "fallback"


def test_exists_after_write(store):
    store.write("Mode", "fast")
    assert store.exists() is True


def test_delete_value(store):
    store.write("Mode", "fast")
    assert store.delete("Mode") is True
    assert store.delete("Mode") is False


def test_unknown_view_rejected():
    with pytest.raises(ValueError):
        ConfigStore(winreg.HKEY_LOCAL_MACHINE, BASE, view="128")
