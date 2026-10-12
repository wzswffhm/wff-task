# -*- coding: utf-8 -*-
"""飞书 fix3 vs 本地 fix5 批次 zip 归一化对比。

飞书 fix3 结构: 批次/{FIN3-WKN-150/, 交付文档.md, 跑分产物与轨迹/}   (第二层混放 = 质检#7 违规)
本地 fix5 结构: 批次/FIN3-WKN-150/{五件套, 交付文档.md, 跑分产物与轨迹/} (已整改)

归一化：两者统一映射为 'FIN3-WKN-150/<相对路径>' 后对比。
"""
import hashlib
import pathlib
import sys
import zipfile

sys.stdout.reconfigure(encoding="utf-8")

H = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-weakness")
FS = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\_qc_runs\feishu-150-verify")


def norm(z, is_fix5):
    m = {}
    with zipfile.ZipFile(z) as zf:
        for i in zf.infolist():
            if i.is_dir():
                continue
            parts = i.filename.split("/")
            if is_fix5:
                # 批次/FIN3-WKN-150/<rest>
                rel = "FIN3-WKN-150/" + "/".join(parts[2:])
            else:
                # 批次/<第二层...>：第二层可能是 FIN3-WKN-150（题目内文件）
                # 或 交付文档.md / 跑分产物与轨迹（第二层混放 = 质检#7 违规）
                if parts[1] == "FIN3-WKN-150":
                    rel = "FIN3-WKN-150/" + "/".join(parts[2:])
                else:
                    rel = "FIN3-WKN-150/" + "/".join(parts[1:])
            m[rel] = hashlib.sha256(zf.read(i.filename)).hexdigest()[:16]
    return m


a = norm(FS / "fs_150_delivery_fix3.zip", False)
b = norm(H / "work_fin-b01_20261006_fix5-150.zip", True)
only_a = sorted(set(a) - set(b))
only_b = sorted(set(b) - set(a))
diff = sorted(k for k in set(a) & set(b) if a[k] != b[k])

print("=== 归一化后对比（按 FIN3-WKN-150/ 相对路径）===")
print(f"  飞书 fix3 = {len(a)} 文件   本地 fix5 = {len(b)} 文件")
print(f"\n  仅飞书有 ({len(only_a)}):")
for k in only_a:
    print(f"      - {k}")
print(f"\n  仅本地有 ({len(only_b)}):")
for k in only_b:
    print(f"      + {k}")
print(f"\n  内容不同 ({len(diff)}):")
for k in diff:
    print(f"      ~ {k}")

# 分类
cats = {
    "质检#4/#5 金标": [k for k in diff if "golden" in k or "reproduce.py" in k or "投资决策备忘录" in k],
    "质检#6 判据": [k for k in diff if "rubrics" in k],
    "版本 bump": [k for k in diff if k.endswith("task.toml")],
    "质检#8 交付文档": [k for k in diff if "交付文档" in k],
    "质检#1/#6 判分产物": [k for k in diff if "reward" in k or "summary" in k],
}
print("\n=== 差异分类 ===")
covered = set()
for name, ks in cats.items():
    covered |= set(ks)
    mark = "OK" if ks else "-"
    print(f"  [{mark}] {name}: {len(ks)}")
    for k in ks:
        print(f"        {k}")
other = [k for k in diff if k not in covered]
print(f"  [其他] {len(other)}")
for k in other:
    print(f"        {k}")
