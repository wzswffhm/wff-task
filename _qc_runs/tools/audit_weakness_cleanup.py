# -*- coding: utf-8 -*-
"""精确区分 harbor-weakness 内的"当前有效"与"历史冗余"，并检查 git 跟踪状态。

以飞书三个记录的附件为"当前有效"基准：
  149 -> rec28himvkSA77      150 -> reczz28Jf9pZeD1T      151 -> reczz28JsandcwbA
只读。
"""
import hashlib
import json
import pathlib
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")

REPO = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task")
W = REPO / "harbor-weakness"
BASE = "QpzNb4fXSamfX6sLloBcPfHNnug"
TABLE = "tblPNrBtjFfwOowN"
META = {"149": "rec28himvkSA77", "150": "reczz28Jf9pZeD1T", "151": "reczz28JsandcwbA"}
LARK = r"C:\nvm4w\nodejs\lark-cli.ps1"
DL = REPO / "_qc_runs" / "feishu-151-dl"


def sha(p: pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def git_tracked(rel: str) -> int:
    r = subprocess.run(["git", "ls-files", "--", rel], cwd=REPO,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return len([x for x in r.stdout.splitlines() if x.strip()])


def git_ignored(rel: str) -> bool:
    r = subprocess.run(["git", "check-ignore", "-q", "--", rel], cwd=REPO, capture_output=True)
    return r.returncode == 0


# ---------- 1. 拉取飞书三题附件清单 ----------
print("=" * 104)
print("一、飞书当前附件（= 交付基准）")
print("=" * 104)
feishu = {}
for task, rid in META.items():
    r = subprocess.run([LARK, "base", "+record-get", "--base-token", BASE, "--table-id", TABLE,
                        "--record-id", rid, "--field-id", "状态", "--field-id", "交付物",
                        "--field-id", "题目附件信息", "--field-id", "标准答案附件信息",
                        "--format", "json"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    txt = r.stdout[r.stdout.find("{"):]
    try:
        d = json.loads(txt)
        row = d["data"]["data"][0]
        fids = d["data"]["field_id_list"]
        fields = d["data"]["fields"]
        rowd = dict(zip(fields, row))
        st = rowd.get("状态") or []
        def files(key):
            v = rowd.get(key) or []
            return [(x.get("name"), x.get("size")) for x in v if isinstance(x, dict)]
        feishu[task] = {"状态": st, "交付物": files("交付物"),
                        "task": files("题目附件信息"), "answer": files("标准答案附件信息")}
        print(f"  {task}  状态={st}")
        for k in ("交付物", "task", "answer"):
            for name, size in feishu[task][k]:
                print(f"        {k:<5} {name:<44} {size:,} B")
    except Exception as e:
        print(f"  {task}  解析失败: {e}\n{txt[:300]}")

# ---------- 2. 本地 zip 与飞书对照 ----------
print()
print("=" * 104)
print("二、本地 zip 与飞书附件对照")
print("=" * 104)
feishu_names = {}
for task, info in feishu.items():
    for k in ("交付物", "task", "answer"):
        for name, size in info[k]:
            if name:
                feishu_names[name] = (task, k, size)

zips = sorted(W.glob("*.zip"))
current, stale, unknown = [], [], []
for z in zips:
    tag = feishu_names.get(z.name)
    if tag:
        task, k, size = tag
        same = (z.stat().st_size == size)
        current.append((z, task, k, size, same))
    else:
        stale.append(z)

print("  【飞书当前附件，本地同名】")
for z, task, k, size, same in current:
    print(f"    ✓ {z.name:<44} {z.stat().st_size:>12,} B  属于 {task}({k})  大小一致={same}")
print()
print("  【本地有但飞书上没有（历史版本）】")
tot = 0
for z in stale:
    s = z.stat().st_size
    tot += s
    print(f"    - {z.name:<44} {s:>12,} B")
print(f"      小计 {tot/1024/1024:.1f} MB")

# ---------- 3. git 跟踪状态 ----------
print()
print("=" * 104)
print("三、关键路径的 git 状态（决定清理是否影响版本库）")
print("=" * 104)
checks = ["harbor-weakness/FIN3-WKN-148", "harbor-weakness/FIN3-WKN-149",
          "harbor-weakness/FIN3-WKN-150", "harbor-weakness/FIN3-WKN-151",
          "harbor-weakness/FIN3-WKN-149/_rejudge", "harbor-weakness/FIN3-WKN-150/_rejudge",
          "harbor-weakness/_reference", "harbor-weakness/work_fin-b01_20261004_fix5",
          "harbor-weakness/work-金融-资产管理-20261008",
          "harbor-weakness/work_fin-b01_20261005_fix7-149",
          "harbor-weakness/work-金融-私募股权投资-20261008",
          "harbor-weakness/work_fin-b01_20261006_fix3-150",
          "harbor-weakness/work-金融-商业银行-20261008"]
for rel in checks:
    p = REPO / rel
    if not p.exists():
        print(f"  {rel:<56} (不存在)")
        continue
    n, s = 0, 0
    for q in p.rglob("*"):
        if q.is_file():
            n += 1
            s += q.stat().st_size
    print(f"  {rel:<56} {n:>4}文件 {s/1024/1024:>7.1f}MB  已跟踪={git_tracked(rel):>4}  被忽略={git_ignored(rel)}")

for z in zips:
    rel = f"harbor-weakness/{z.name}"
    print(f"  {rel:<56} {'':>4}      {'':>7}    已跟踪={git_tracked(rel):>4}  被忽略={git_ignored(rel)}")
