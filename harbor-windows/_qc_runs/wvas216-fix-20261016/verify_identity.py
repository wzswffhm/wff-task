# -*- coding: utf-8 -*-
"""校验 216 包身份是否回到 jobs 记录的 253161fb…，并逐文件与 git 历史比对。"""
from __future__ import annotations

import hashlib
import pathlib
import subprocess
import sys

HW = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-windows")
sys.path.insert(0, str(HW / "_reference" / "windows-harbor-qc" / "scripts"))
from inspect_delivery import harbor_dirhash, task_hash  # noqa: E402

REPO = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task")
PKG = "wfflab__wvas-216-v1.0.0-delivery"
ROOT = HW / PKG
EXCLUDE = {"REFIT-2026-10-14.md", "verifier/WINDOWS_VALUE.md"}

print("dirhash  =", harbor_dirhash(ROOT))
print("task_hash=", task_hash(ROOT))
print("jobs 记录 = 253161fb10921f9744388a4530f5559dd1f828c8660516d8249ac91c7b6b0306")
print("匹配     =", harbor_dirhash(ROOT) ==
      "253161fb10921f9744388a4530f5559dd1f828c8660516d8249ac91c7b6b0306")

print("\n与 git 历史 1568cfb3 逐文件比对（排除这 2 个文件后应全部一致）：")
changed, same, missing = [], 0, []
for path in sorted(p for p in ROOT.rglob("*") if p.is_file()):
    rel = path.relative_to(ROOT).as_posix()
    if rel in EXCLUDE:
        continue
    out = subprocess.run(["git", "-C", str(REPO), "show", f"1568cfb3:harbor-windows/{PKG}/{rel}"],
                         capture_output=True)
    if out.returncode != 0:
        missing.append(rel)
        continue
    if hashlib.sha256(out.stdout).hexdigest() == hashlib.sha256(path.read_bytes()).hexdigest():
        same += 1
    else:
        changed.append(rel)
print("  相同 =", same, " 不同 =", changed, " 历史缺失 =", missing)

print("\n这 2 个文件 vs 历史版本：")
for rel in sorted(EXCLUDE):
    out = subprocess.run(["git", "-C", str(REPO), "show", f"1568cfb3:harbor-windows/{PKG}/{rel}"],
                         capture_output=True)
    if out.returncode != 0:
        print("  ", rel, "历史缺失")
        continue
    hist = hashlib.sha256(out.stdout).hexdigest()
    now = hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()
    print(f"   {rel}\n     历史={hist}\n     现在={now}\n     一致={hist == now}")
