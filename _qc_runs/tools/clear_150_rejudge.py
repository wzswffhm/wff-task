# -*- coding: utf-8 -*-
"""备份并清空 FIN3-WKN-150 的 _rejudge 旧判分产物，使 runner 重新跑。

改 rubrics 判据后必须重跑 judge，runner 的 read_state 需为 pending。
"""
import json
import pathlib
import shutil
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")

W = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-weakness")
TASK = W / "FIN3-WKN-150"
EXEC = ["oracle", "qwen3.8-max-0902", "claude-opus-4-8", "gpt-5.6-sol"]
BACKUP = W / "_qc_runs" / f"rejudge150-before-tighten-{time.strftime('%Y%m%d-%H%M%S')}"

# 1. 备份
if not BACKUP.is_dir():
    shutil.copytree(TASK / "_rejudge", BACKUP,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
print(f"备份到: {BACKUP}")
n = sum(1 for _ in BACKUP.rglob("*") if _.is_file())
print(f"  备份文件数: {n}")

# 2. 备份改前的 rubrics.toml（若尚未单独备份）
rj = TASK / "tests" / "rubrics.toml"
bak_rub = BACKUP.parent / "rubrics.toml.before-tighten"
if rj.is_file() and not bak_rub.is_file():
    # 注意：rubrics 已改，这里备份的是改后版本；改前版本从 git 恢复
    print(f"  （rubrics 改前版本可从 git: git show HEAD:harbor-weakness/FIN3-WKN-150/tests/rubrics.toml）")

# 3. 清空 _rejudge（让 runner 重新跑）
rj_dir = TASK / "_rejudge"
if rj_dir.is_dir():
    shutil.rmtree(rj_dir)
print(f"已清空: {rj_dir}  (exists={rj_dir.is_dir()})")

# 4. 验证
for e in EXEC:
    ver = rj_dir / e / "verifier"
    rj_f = ver / "reward.json"
    rem_f = ver / "reward_exit_message.json"
    print(f"  {e}: reward.json={rj_f.is_file()}  exit_msg={rem_f.is_file()}  (应为 False False)")

print("\n备份完成，runner 将重新判分。")
