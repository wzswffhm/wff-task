# -*- coding: utf-8 -*-
"""把 FIN3-WKN-151 还原成飞书交付物那一版。

已核验的事实（三条独立证据）：
  1. 飞书记录 reczz28JsandcwbA（序号 267）状态 = 「一审通过」，质检报告字段为空；
  2. 飞书三个附件（交付包/task/answer）与本地对应 zip sha256 逐字节相同；
  3. 题包本体除 _rejudge/ 与 __pycache__/ 外，与交付包内 FIN3-WKN-151/ 内容零差异。

因此"还原"= 移走返修重判工作目录 _rejudge/、清理 __pycache__/，
并从交付包补回被 .gitignore（*.log）过滤掉的 4 个 trial.log。
_rejudge/ 先完整备份到仓库外，可随时回滚。git 跟踪的 22 个文件需另行 commit 才生效。
"""
import hashlib
import pathlib
import shutil
import sys
import zipfile
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8")

W = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-weakness")
BODY = W / "FIN3-WKN-151"
BATCH = W / "work-金融-商业银行-20261008"
ZIP = W / "work_fin-b01_20261006-151.zip"
PREFIX = "work_fin-b01_20261006-151/"
STAMP = datetime.now().strftime("%Y%m%d-%H%M%S")
BACKUP = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\_qc_runs") / f"rejudge151-backup-{STAMP}"

DRY = "--dry-run" in sys.argv


def h(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


# ------------------------------------------------ 1. 备份 _rejudge
rj = BODY / "_rejudge"
print("=" * 78)
if rj.is_dir():
    n = sum(1 for p in rj.rglob("*") if p.is_file())
    print(f"1. 备份 _rejudge/（{n} 文件） -> {BACKUP}")
    if not DRY:
        BACKUP.mkdir(parents=True, exist_ok=True)
        shutil.copytree(rj, BACKUP / "_rejudge", dirs_exist_ok=True)
        print(f"   已备份，校验中…")
        ok = True
        for p in rj.rglob("*"):
            if p.is_file():
                q = BACKUP / "_rejudge" / p.relative_to(rj)
                if not q.is_file() or h(p) != h(q):
                    print(f"   !! 备份不一致: {p.relative_to(rj)}")
                    ok = False
        print(f"   备份校验: {'全部一致' if ok else '存在差异，中止删除'}")
        if not ok:
            sys.exit(1)
else:
    print("1. _rejudge/ 不存在，跳过")

# ------------------------------------------------ 2. 删除 _rejudge
print("=" * 78)
if rj.is_dir():
    print("2. 删除工作区 _rejudge/")
    if not DRY:
        shutil.rmtree(rj)
        print("   已删除（git 索引中的 22 个文件在下次 commit 时体现为删除）")

# ------------------------------------------------ 3. 清理 __pycache__
print("=" * 78)
pyc = list(BODY.rglob("__pycache__"))
print(f"3. 清理 __pycache__/（{len(pyc)} 个目录）")
for d in pyc:
    print(f"   - {d.relative_to(BODY)}")
    if not DRY:
        shutil.rmtree(d)

# ------------------------------------------------ 4. 补回 trial.log
print("=" * 78)
print("4. 从交付包补回 trial.log")
missing = []
with zipfile.ZipFile(ZIP) as zf:
    names = [n for n in zf.namelist() if n.startswith(PREFIX + "跑分产物与轨迹/") and n.endswith("/轨迹/trial.log")]
    for n in sorted(names):
        rel = n[len(PREFIX):]
        dst = BATCH / rel
        src_sha = hashlib.sha256(zf.read(n)).hexdigest()
        if dst.is_file() and h(dst) == src_sha:
            print(f"   = 已一致 {rel}")
            continue
        print(f"   + 写入   {rel}  ({len(zf.read(n))} B)")
        if not DRY:
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(zf.read(n))
        missing.append(rel)

# ------------------------------------------------ 5. 复核
print("=" * 78)
print("5. 复核：本体 / 批次目录 与交付包逐字节比对")
zip_body, zip_batch = {}, {}
with zipfile.ZipFile(ZIP) as zf:
    for info in zf.infolist():
        if info.is_dir() or not info.filename.startswith(PREFIX):
            continue
        rel = info.filename[len(PREFIX):]
        digest = hashlib.sha256(zf.read(info.filename)).hexdigest()
        if rel.startswith("FIN3-WKN-151/"):
            zip_body[rel[len("FIN3-WKN-151/"):]] = digest
        else:
            zip_batch[rel] = digest


def scan(root: pathlib.Path):
    out = {}
    for p in root.rglob("*"):
        if p.is_file():
            rel = p.relative_to(root).as_posix()
            if "__pycache__" in rel or rel.endswith(".pyc"):
                continue
            out[rel] = h(p)
    return out


live_body = scan(BODY)
print(f"   题包本体 zip={len(zip_body)} 本地={len(live_body)}")
extra = sorted(set(live_body) - set(zip_body))
miss = sorted(set(zip_body) - set(live_body))
diff = sorted(k for k in set(zip_body) & set(live_body) if zip_body[k] != live_body[k])
print(f"     仅本地有: {len(extra)}")
for k in extra[:30]:
    print(f"        - {k}")
print(f"     仅交付包有: {len(miss)}")
for k in miss[:30]:
    print(f"        + {k}")
print(f"     内容不同: {len(diff)}")
for k in diff[:30]:
    print(f"        ~ {k}")

live_batch = scan(BATCH)
extra_b = sorted(set(live_batch) - set(zip_batch))
miss_b = sorted(set(zip_batch) - set(live_batch))
diff_b = sorted(k for k in set(zip_batch) & set(live_batch) if zip_batch[k] != live_batch[k])
print(f"   批次目录 zip={len(zip_batch)} 本地={len(live_batch)}")
print(f"     仅本地有: {len(extra_b)}")
for k in extra_b[:30]:
    print(f"        - {k}")
print(f"     仅交付包有: {len(miss_b)}")
for k in miss_b[:30]:
    print(f"        + {k}")
print(f"     内容不同: {len(diff_b)}")
for k in diff_b[:30]:
    print(f"        ~ {k}")

print("=" * 78)
if extra or miss or diff or extra_b or miss_b or diff_b:
    print("结果：仍有差异（见上）")
else:
    print("结果：151 题包本体与批次目录均已与飞书交付物逐字节一致")
print(f"备份位置：{BACKUP}" if rj.exists() or BACKUP.exists() else "")
