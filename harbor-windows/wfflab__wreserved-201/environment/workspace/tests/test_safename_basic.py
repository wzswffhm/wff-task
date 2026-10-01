"""wsafename 的基础行为测试（仓库自带，不得修改）。"""

import os

import pytest

from wsafename import FileStore, InvalidNameError, sanitize


@pytest.fixture()
def store(tmp_path):
    return FileStore(str(tmp_path / "uploads"))


def test_save_and_load_roundtrip(store):
    name = store.save("notes.txt", b"hello")
    assert name == "notes.txt"
    assert store.load("notes.txt") == b"hello"
    assert store.exists("notes.txt")


def test_target_path_stays_under_root(store):
    path = store.target_path("notes.txt")
    assert os.path.dirname(path) == store.root


def test_illegal_characters_are_replaced(store):
    assert sanitize("a:b*c?.txt") == "a_b_c_.txt"
    assert store.save("a:b*c?.txt", b"x") == "a_b_c_.txt"


def test_unicode_name_roundtrip(store):
    store.save("报表-2024.csv", "内容".encode("utf-8"))
    assert store.load("报表-2024.csv").decode("utf-8") == "内容"


def test_existing_entry_is_overwritten(store):
    store.save("a.txt", b"one")
    store.save("a.txt", b"two")
    assert store.load("a.txt") == b"two"
    assert store.list_names() == ["a.txt"]


def test_delete_removes_entry(store):
    store.save("a.txt", b"x")
    assert store.delete("a.txt") is True
    assert store.exists("a.txt") is False
    assert store.list_names() == []


def test_blank_name_is_rejected(store):
    with pytest.raises(InvalidNameError):
        store.save("   ", b"x")


def test_non_bytes_payload_is_rejected(store):
    with pytest.raises(TypeError):
        store.save("a.txt", "text")
