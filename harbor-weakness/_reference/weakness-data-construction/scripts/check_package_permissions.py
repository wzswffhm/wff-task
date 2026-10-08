#!/usr/bin/env python3
"""打包后自检：zip（或目录）内的权限位、换行、残留文件、目录层级、golden 一致性。

用法:
    python check_package_permissions.py <pkg.zip 或批次目录> [<...> ...]

为什么必须从 zip 里读：Windows 上重新压缩会把条目 external_attr 写成 0，
本机文件属性正常但对方解包后 solve.sh / test.sh 没有可执行位（甲方 §8.2.2 → F08 退回）。
只读设计，不修改任何文件；退出码 0 = 无 FAIL。
"""
import hashlib
import io
import os
import sys
import zipfile

FIVE = ("instruction.md", "task.toml", "rubrics.json", "environment", "tests", "solution")
SCRIPTS = ("solution/solve.sh", "tests/test.sh")
JUNK = ("__pycache__", ".pyc", ".git/", ".DS_Store", ".venv", "__MACOSX")


class Report:
    def __init__(self, label):
        self.label = label
        self.fails = []
        self.notes = []

    def fail(self, msg):
        self.fails.append(msg)
        print("  FAIL " + msg)

    def ok(self, msg):
        print("  OK   " + msg)

    def note(self, msg):
        self.notes.append(msg)
        print("  NOTE " + msg)


def read_members(target):
    """返回 {相对路径: (mode, bytes)}；zip 与目录统一成同一视图。"""
    out = {}
    if target.lower().endswith(".zip"):
        with zipfile.ZipFile(target) as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                mode = (info.external_attr >> 16) & 0o7777
                out[info.filename.replace("\\", "/")] = (mode, zf.read(info.filename))
    else:
        for base, _dirs, files in os.walk(target):
            for name in files:
                full = os.path.join(base, name)
                rel = os.path.relpath(full, target).replace(os.sep, "/")
                mode = os.stat(full).st_mode & 0o7777
                with open(full, "rb") as fh:
                    out[rel] = (mode, fh.read())
    return out


def check_one(target):
    rep = Report(target)
    print("===== " + target)
    members = read_members(target)
    roots = {p.split("/", 1)[0] for p in members}
    if len(roots) != 1:
        rep.note(f"顶层目录不唯一：{sorted(roots)}（一题一包时应只有一个批次目录）")
    root = sorted(roots)[0]
    # 题目目录 = 含 task.toml 的那一层（避免把「跑分产物与轨迹」也当成题目）
    tasks = {p.split("/")[1] for p in members
             if p.startswith(root + "/") and p.endswith("/task.toml")}
    if not tasks:
        rep.fail("未发现批次目录/题目目录 两级层级")
        return rep

    for task in sorted(tasks):
        print(f"  -- {task}")
        for item in FIVE:
            keys = [p for p in members if p.startswith(f"{root}/{task}/{item}")]
            (rep.ok if keys else rep.fail)(f"{task}: 五件套含 {item}")
        # 脚本权限 + 换行
        for rel in SCRIPTS:
            key = f"{root}/{task}/{rel}"
            if key not in members:
                continue
            mode, data = members[key]
            if mode & 0o111:
                rep.ok(f"{task}: {rel} 权限 {oct(mode)} 带可执行位")
            else:
                rep.fail(f"{task}: {rel} 权限 {oct(mode)} 缺少可执行位（应 0755 存储在 zip 内）")
            if b"\r\n" in data:
                rep.fail(f"{task}: {rel} 含 CRLF，必须 LF")
            else:
                rep.ok(f"{task}: {rel} LF")
        # golden 双份一致
        g1 = {os.path.basename(p): d for p, (_m, d) in members.items()
              if p.startswith(f"{root}/{task}/solution/golden_output/")}
        g2 = {os.path.basename(p): d for p, (_m, d) in members.items()
              if p.startswith(f"{root}/{task}/tests/__golden_output/")}
        if not g1:
            rep.fail(f"{task}: solution/golden_output/ 为空")
        elif g1.keys() == g2.keys() and all(
                hashlib.sha256(g1[k]).digest() == hashlib.sha256(g2[k]).digest() for k in g1):
            rep.ok(f"{task}: 两份 golden 逐字节一致（{len(g1)} 个文件）")
        else:
            rep.fail(f"{task}: 两份 golden 不一致（{sorted(g1)} vs {sorted(g2)}）")

    junk = [p for p in members if any(j in p for j in JUNK)]
    (rep.ok if not junk else rep.fail)("无 __pycache__/.pyc/.git/.DS_Store 等残留" +
                                       ("" if not junk else f"：{junk[:6]}"))
    docs = [p for p in members if p.count("/") == 1 and p.endswith("交付文档.md")]
    (rep.ok if docs else rep.fail)("批次根目录有 交付文档.md")
    scores = [p for p in members if "/跑分产物与轨迹/" in p]
    (rep.ok if scores else rep.note)(
        "含 跑分产物与轨迹/" if scores else "未见 跑分产物与轨迹/（验收要求随包，请确认）")
    return rep


def main():
    targets = [a for a in sys.argv[1:] if not a.startswith("-")]
    if not targets:
        raise SystemExit(__doc__)
    bad = 0
    for target in targets:
        if not os.path.exists(target):
            print(f"===== {target}\n  FAIL 路径不存在")
            bad += 1
            continue
        bad += len(check_one(target).fails)
    print(f"\nFAIL 合计: {bad}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
