"""winstall 的可见回归测试（仓库自带，不得改动）。

只覆盖最基本的公开契约：版本比较、干净安装、升级覆盖、卸载、作用域隔离、
字节保真与参数校验。更细的 Windows 安装事务语义由隐藏测试覆盖。
"""

from __future__ import annotations

import json
import os

import pytest

from winstall import (
    ApplyFailed,
    PlanRejected,
    apply_transaction,
    compare_versions,
    install_root,
    payload_dir,
    plan_transaction,
    read_manifest,
)


def _payload(tmp_path, name, marker):
    """在临时目录里造一个载荷源文件，返回 ``{相对路径: 源文件}``。"""
    src = tmp_path / ("src-" + name.replace("/", "_"))
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_bytes(marker)
    return src


def test_compare_versions_is_symmetric_on_equal_versions():
    assert compare_versions("1.2.3", "1.2.3") == 0
    assert compare_versions("v1.2.3", "1.2.3") == 0


def test_compare_versions_orders_plain_versions():
    assert compare_versions("1.2.4", "1.2.3") == 1
    assert compare_versions("1.2.3", "1.2.4") == -1
    assert compare_versions("2.0.0", "1.9.9") == 1


def test_compare_versions_prefers_release_over_prerelease():
    assert compare_versions("1.0.0", "1.0.0-beta") == 1
    assert compare_versions("1.0.0-beta", "1.0.0") == -1


def test_clean_install_writes_payload_and_manifest(tmp_path):
    root = str(tmp_path / "root")
    files = {"bin/app.exe": _payload(tmp_path, "bin/app.exe", b"app-1.0.0")}
    plan = plan_transaction("install", "demo", "1.0.0", files, root=root)
    result = apply_transaction(plan)

    assert result.deferred == ()
    assert os.path.isfile(os.path.join(payload_dir(root, "demo"), "bin", "app.exe"))
    data = read_manifest(root)
    assert data["products"]["demo"]["version"] == "1.0.0"


def test_upgrade_overwrites_payload_in_place(tmp_path):
    root = str(tmp_path / "root")
    first = {"bin/app.exe": _payload(tmp_path, "a1", b"app-1.0.0")}
    apply_transaction(plan_transaction("install", "demo", "1.0.0", first, root=root))

    second = {"bin/app.exe": _payload(tmp_path, "a2", b"app-1.1.0")}
    apply_transaction(plan_transaction("install", "demo", "1.1.0", second, root=root))

    with open(os.path.join(payload_dir(root, "demo"), "bin", "app.exe"), "rb") as fh:
        assert fh.read() == b"app-1.1.0"
    assert read_manifest(root)["products"]["demo"]["version"] == "1.1.0"


def test_uninstall_drops_the_product_entry(tmp_path):
    root = str(tmp_path / "root")
    files = {"app.ini": _payload(tmp_path, "ini", b"[demo]\n")}
    apply_transaction(plan_transaction("install", "demo", "1.0.0", files, root=root))
    apply_transaction(plan_transaction("uninstall", "demo", root=root))

    assert "demo" not in read_manifest(root)["products"]
    assert not os.path.isfile(os.path.join(payload_dir(root, "demo"), "app.ini"))


def test_reinstalling_the_same_version_is_rejected(tmp_path):
    root = str(tmp_path / "root")
    files = {"app.ini": _payload(tmp_path, "ini", b"[demo]\n")}
    apply_transaction(plan_transaction("install", "demo", "1.0.0", files, root=root))
    with pytest.raises(PlanRejected):
        plan_transaction("install", "demo", "1.0.0", files, root=root)


def test_uninstall_of_an_unknown_product_is_rejected(tmp_path):
    with pytest.raises(PlanRejected):
        plan_transaction("uninstall", "ghost", root=str(tmp_path / "root"))


def test_payload_bytes_are_written_verbatim(tmp_path):
    root = str(tmp_path / "root")
    blob = bytes(range(256)) * 8
    files = {"data/blob.bin": _payload(tmp_path, "blob", blob)}
    apply_transaction(plan_transaction("install", "demo", "1.0.0", files, root=root))

    with open(os.path.join(payload_dir(root, "demo"), "data", "blob.bin"), "rb") as fh:
        assert fh.read() == blob


def test_scopes_have_distinct_roots():
    assert install_root("machine") != install_root("user")
    with pytest.raises(ValueError):
        install_root("galaxy")


def test_unknown_operation_is_rejected(tmp_path):
    with pytest.raises(ValueError):
        plan_transaction("reinstall", "demo", "1.0.0", {}, root=str(tmp_path / "root"))
