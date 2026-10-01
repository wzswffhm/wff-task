"""winstall 的 Windows 安装事务回归测试（隐藏）。

required 集合：
  F2P —— base 上失败、参考解上必须通过
  P2P —— base 与参考解上都必须通过

本模块依赖 Windows 的文件占用语义（另一句柄打开目标文件时原子替换失败），
非 Windows 平台整体跳过。
"""

from __future__ import annotations

import os

import pytest

from winstall import (
    ApplyFailed,
    PlanRejected,
    apply_transaction,
    compare_versions,
    payload_dir,
    plan_transaction,
    read_manifest,
)

pytestmark = pytest.mark.skipif(
    os.name != "nt", reason="requires Windows file-sharing semantics")


# --------------------------------------------------------------------------
# 辅助
# --------------------------------------------------------------------------

def _stage(tmp_path, name, data):
    """造一个载荷源文件，返回其路径。"""
    src = tmp_path / "src" / name
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_bytes(data)
    return str(src)


def _read(path):
    with open(path, "rb") as fh:
        return fh.read()


def _snapshot(root):
    """把一棵目录树拍成 {相对路径: 内容}。"""
    out = {}
    for base, _dirs, names in os.walk(root):
        for name in names:
            full = os.path.join(base, name)
            out[os.path.relpath(full, root).replace("\\", "/")] = _read(full)
    return out


def _install(root, version, files):
    return apply_transaction(plan_transaction("install", "demo", version, files, root=root))


def _payload(root):
    return payload_dir(root, "demo")


# --------------------------------------------------------------------------
# F2P：base 失败的缺口
# --------------------------------------------------------------------------

def test_version_segments_compare_numerically_not_lexically():
    """四段版本必须按十进制数值比较，而不是按字符串。"""
    assert compare_versions("1.10.0", "1.9.0") == 1
    assert compare_versions("1.9.0", "1.10.0") == -1
    assert compare_versions("2.0.0", "10.0.0") == -1
    assert compare_versions("1.0.10.1", "1.0.9.99") == 1
    assert compare_versions("1.2", "1.2.0") == 0


def test_downgrade_is_rejected_and_current_install_is_intact(tmp_path):
    """1.9.0 低于已装的 1.10.0，必须拒绝，且磁盘与清单保持原样。"""
    root = str(tmp_path / "root")
    _install(root, "1.10.0", {"bin/app.exe": _stage(tmp_path, "app110", b"app-1.10.0")})
    before = _snapshot(_payload(root))

    older = {"bin/app.exe": _stage(tmp_path, "app190", b"app-1.9.0")}
    with pytest.raises(PlanRejected):
        plan_transaction("install", "demo", "1.9.0", older, root=root)

    assert _snapshot(_payload(root)) == before
    assert read_manifest(root)["products"]["demo"]["version"] == "1.10.0"


def test_locked_payload_file_is_deferred_instead_of_aborting(tmp_path):
    """目标文件被别的进程打开时，只推迟这一个文件，其它文件照常更新。"""
    root = str(tmp_path / "root")
    _install(root, "1.0.0", {
        "bin/app.exe": _stage(tmp_path, "app1", b"app-1.0.0"),
        "etc/app.ini": _stage(tmp_path, "ini1", b"[demo]\nversion=1.0.0\n"),
    })
    payload = _payload(root)
    locked = os.path.join(payload, "bin", "app.exe")

    plan = plan_transaction("install", "demo", "1.1.0", {
        "bin/app.exe": _stage(tmp_path, "app2", b"app-1.1.0"),
        "etc/app.ini": _stage(tmp_path, "ini2", b"[demo]\nversion=1.1.0\n"),
    }, root=root)

    with open(locked, "rb"):
        result = apply_transaction(plan)

    assert list(result.deferred) == ["bin/app.exe"]
    assert "etc/app.ini" in result.applied
    assert _read(os.path.join(payload, "etc", "app.ini")) == b"[demo]\nversion=1.1.0\n"
    assert _read(locked) == b"app-1.0.0"

    entry = read_manifest(root)["products"]["demo"]
    assert entry["version"] == "1.1.0"
    assert entry["pending_replace"] == ["bin/app.exe"]


def test_deferred_file_is_completed_by_the_next_apply(tmp_path):
    """占用解除后，对同一计划再次执行必须完成替换并清空待替换记录。"""
    root = str(tmp_path / "root")
    _install(root, "1.0.0", {
        "bin/app.exe": _stage(tmp_path, "app1", b"app-1.0.0"),
        "etc/app.ini": _stage(tmp_path, "ini1", b"[demo]\nversion=1.0.0\n"),
    })
    payload = _payload(root)
    locked = os.path.join(payload, "bin", "app.exe")

    plan = plan_transaction("install", "demo", "1.1.0", {
        "bin/app.exe": _stage(tmp_path, "app2", b"app-1.1.0"),
        "etc/app.ini": _stage(tmp_path, "ini2", b"[demo]\nversion=1.1.0\n"),
    }, root=root)

    holder = open(locked, "rb")
    try:
        first = apply_transaction(plan)
    finally:
        holder.close()
    assert list(first.deferred) == ["bin/app.exe"]

    second = apply_transaction(plan)
    assert list(second.deferred) == []
    assert _read(locked) == b"app-1.1.0"
    assert read_manifest(root)["products"]["demo"]["pending_replace"] == []


def _failing_upgrade(tmp_path):
    """构造一次必定在最后一步硬失败、且前面已有覆盖与新建的升级。"""
    root = str(tmp_path / "root")
    _install(root, "1.0.0", {"bin/app.exe": _stage(tmp_path, "app1", b"app-1.0.0")})
    payload = _payload(root)
    os.makedirs(os.path.join(payload, "zzz", "blocked.dat"))

    plan = plan_transaction("install", "demo", "1.1.0", {
        "aa_new/compat.dll": _stage(tmp_path, "dll2", b"compat-1.1.0"),
        "bin/app.exe": _stage(tmp_path, "app2", b"app-1.1.0"),
        "zzz/blocked.dat": _stage(tmp_path, "blk2", b"blocked-1.1.0"),
    }, root=root)
    with pytest.raises(ApplyFailed):
        apply_transaction(plan)
    return root, payload


def test_failed_upgrade_restores_overwritten_file_bytes(tmp_path):
    """不可延迟的失败之后，被覆盖的文件必须逐字节回到旧内容。"""
    root, payload = _failing_upgrade(tmp_path)

    assert _read(os.path.join(payload, "bin", "app.exe")) == b"app-1.0.0"
    assert read_manifest(root)["products"]["demo"]["version"] == "1.0.0"


def test_failed_upgrade_removes_newly_created_files(tmp_path):
    """回滚必须把这次事务新建的文件删掉。"""
    _root, payload = _failing_upgrade(tmp_path)

    assert not os.path.exists(os.path.join(payload, "aa_new", "compat.dll"))


def test_failed_upgrade_leaves_no_temporary_files(tmp_path):
    """回滚之后不得在载荷目录里留下任何临时文件。"""
    _root, payload = _failing_upgrade(tmp_path)

    leftovers = []
    for base, _dirs, names in os.walk(payload):
        for name in names:
            if name.endswith(".winstall-part"):
                leftovers.append(os.path.relpath(os.path.join(base, name), payload))
    assert leftovers == []


# --------------------------------------------------------------------------
# P2P：base 与参考解都必须通过的回归保护
# --------------------------------------------------------------------------

def test_clean_install_writes_payload_and_records_version(tmp_path):
    root = str(tmp_path / "root")
    files = {
        "bin/app.exe": _stage(tmp_path, "app", b"app-1.0.0"),
        "etc/app.ini": _stage(tmp_path, "ini", b"[demo]\nversion=1.0.0\n"),
    }
    result = _install(root, "1.0.0", files)

    assert result.deferred == ()
    assert sorted(result.applied) == ["bin/app.exe", "etc/app.ini"]
    assert _read(os.path.join(_payload(root), "bin", "app.exe")) == b"app-1.0.0"
    entry = read_manifest(root)["products"]["demo"]
    assert entry["version"] == "1.0.0"
    assert sorted(entry["files"]) == ["bin/app.exe", "etc/app.ini"]


def test_upgrade_overwrites_payload_and_records_new_version(tmp_path):
    root = str(tmp_path / "root")
    _install(root, "1.0.0", {"bin/app.exe": _stage(tmp_path, "app1", b"app-1.0.0")})
    _install(root, "1.1.0", {"bin/app.exe": _stage(tmp_path, "app2", b"app-1.1.0")})

    assert _read(os.path.join(_payload(root), "bin", "app.exe")) == b"app-1.1.0"
    assert read_manifest(root)["products"]["demo"]["version"] == "1.1.0"


def test_upgrade_drops_files_absent_from_the_new_version(tmp_path):
    root = str(tmp_path / "root")
    _install(root, "1.0.0", {
        "bin/app.exe": _stage(tmp_path, "app1", b"app-1.0.0"),
        "bin/legacy.dll": _stage(tmp_path, "legacy", b"legacy"),
    })
    _install(root, "1.1.0", {"bin/app.exe": _stage(tmp_path, "app2", b"app-1.1.0")})

    assert not os.path.exists(os.path.join(_payload(root), "bin", "legacy.dll"))
    assert read_manifest(root)["products"]["demo"]["files"] == ["bin/app.exe"]


def test_uninstall_removes_payload_and_manifest_entry(tmp_path):
    root = str(tmp_path / "root")
    _install(root, "1.0.0", {"etc/app.ini": _stage(tmp_path, "ini", b"[demo]\n")})
    apply_transaction(plan_transaction("uninstall", "demo", root=root))

    assert "demo" not in read_manifest(root)["products"]
    assert not os.path.exists(os.path.join(_payload(root), "etc", "app.ini"))


def test_machine_and_user_scopes_do_not_interfere(tmp_path):
    machine_root = str(tmp_path / "machine")
    user_root = str(tmp_path / "user")
    apply_transaction(plan_transaction(
        "install", "demo", "1.0.0",
        {"app.ini": _stage(tmp_path, "m", b"machine")}, scope="machine", root=machine_root))
    apply_transaction(plan_transaction(
        "install", "demo", "1.0.0",
        {"app.ini": _stage(tmp_path, "u", b"user")}, scope="user", root=user_root))

    assert _read(os.path.join(payload_dir(machine_root, "demo"), "app.ini")) == b"machine"
    assert _read(os.path.join(payload_dir(user_root, "demo"), "app.ini")) == b"user"


def test_planning_does_not_touch_the_filesystem(tmp_path):
    root = str(tmp_path / "root")
    plan_transaction("install", "demo", "1.0.0",
                     {"app.ini": _stage(tmp_path, "ini", b"[demo]\n")}, root=root)

    assert not os.path.exists(root)


def test_unrelated_products_are_left_untouched(tmp_path):
    root = str(tmp_path / "root")
    apply_transaction(plan_transaction(
        "install", "other", "4.2.0", {"keep.txt": _stage(tmp_path, "keep", b"keep")}, root=root))
    _install(root, "1.0.0", {"bin/app.exe": _stage(tmp_path, "app1", b"app-1.0.0")})
    _install(root, "1.1.0", {"bin/app.exe": _stage(tmp_path, "app2", b"app-1.1.0")})

    assert _read(os.path.join(payload_dir(root, "other"), "keep.txt")) == b"keep"
    assert read_manifest(root)["products"]["other"]["version"] == "4.2.0"
