# -*- coding: utf-8 -*-
"""重跑前准备：
 1) 备份当前归档判分产物（旧判据那批，保留以供对比）
 2) 删除 rejudge-stage 的 tests 缓存（它是 09:19:29 的旧 rubrics.toml）
 3) 从题包本体重新拷贝 tests（12:37:30 收紧后的新判据）
 4) 验证 stage 判据 sha 已换新
"""
import hashlib
import pathlib
import shutil
import sys
import datetime

sys.stdout.reconfigure(encoding="utf-8")

H = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-weakness")
BODY_TESTS = H / "FIN3-WKN-150" / "tests"
ARCH = H / "work-金融-私募股权投资-20261008" / "FIN3-WKN-150" / "跑分产物与轨迹"
STAGE_TESTS = pathlib.Path(r"C:\Users\Administrator\.wff-creds\rejudge-stage\FIN3-WKN-150\tests")
Q = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\_qc_runs")
EXEC = ["oracle", "qwen3.8-max-0902", "claude-opus-4-8", "gpt-5.6-sol"]
NEW_SHA = "16f1bfc2df43fb09"


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()[:16]


def mtime(p):
    return datetime.datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")


print("=" * 96)
print("步骤 1/3：备份当前归档判分产物（旧判据批次）")
print("=" * 96)
ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
BK = Q / f"rejudge150-v1-oldjudge-{ts}"
n = 0
for ex in EXEC:
    for fn in ("reward.json", "reward-details.json"):
        s = ARCH / ex / fn
        if s.is_file():
            d = BK / ex / fn
            d.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(s, d)
            n += 1
            print(f"  备份 {ex}/{fn}  {s.stat().st_size:,} B")
s = ARCH / "summary.json"
if s.is_file():
    BK.mkdir(parents=True, exist_ok=True)
    shutil.copy2(s, BK / "summary.json")
    n += 1
    print(f"  备份 summary.json  {s.stat().st_size:,} B")
print(f"  -> {BK}  （共 {n} 个文件）")

print()
print("=" * 96)
print("步骤 2/3：替换 stage 的 tests 缓存")
print("=" * 96)
old = STAGE_TESTS / "rubrics.toml"
print(f"  替换前 stage rubrics.toml: sha={sha(old)}  mtime={mtime(old)}")
print(f"     含'量化拆解'={'量化拆解' in old.read_text(encoding='utf-8')}")
if STAGE_TESTS.is_dir():
    shutil.rmtree(STAGE_TESTS)
    print(f"  已删除旧缓存 {STAGE_TESTS}")
shutil.copytree(BODY_TESTS, STAGE_TESTS,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
print(f"  已从题包本体重新拷贝 tests -> {STAGE_TESTS}")

print()
print("=" * 96)
print("步骤 3/3：验证")
print("=" * 96)
new = STAGE_TESTS / "rubrics.toml"
txt = new.read_text(encoding="utf-8")
ok_sha = sha(new) == NEW_SHA
ok_r29 = "量化拆解" in txt
ok_r30 = "跨期变化的量化幅度" in txt
print(f"  stage rubrics.toml: sha={sha(new)}  mtime={mtime(new)}  (期望 {NEW_SHA})")
print(f"    R29 量化拆解      = {ok_r29}")
print(f"    R30 跨期量化幅度  = {ok_r30}")
print(f"    sha 与本体一致    = {sha(new) == sha(BODY_TESTS / 'rubrics.toml')}")
# 逐文件核对 stage vs 本体，确认无遗漏差异
diff = []
for p in BODY_TESTS.rglob("*"):
    if p.is_file() and "__pycache__" not in p.parts:
        rel = p.relative_to(BODY_TESTS)
        q2 = STAGE_TESTS / rel
        if not q2.is_file() or sha(q2) != sha(p):
            diff.append(rel.as_posix())
print(f"    stage 与本体 tests 差异文件: {diff if diff else '无（完全一致）'}")
allok = ok_sha and ok_r29 and ok_r30 and not diff
print()
print(f"  >>> {'准备就绪，可以重跑' if allok else '仍有问题，勿启动重跑'}")
sys.exit(0 if allok else 1)
