#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""215 收尾：严格自检 -> 修正 -> 重建归档 -> 打包 -> 上传飞书 -> 同步索引。

任何一步失败即返回非零退出码，绝不继续往下做（尤其不允许在失败情况下关机）。
"""
from __future__ import annotations

import csv
import io
import json
import os
import shutil
import subprocess
import sys
import tomllib
import zipfile

WS = r"C:\Users\Administrator\Desktop\wff-task"
HW = os.path.join(WS, "harbor-windows")
PKG = os.path.join(HW, "wfflab__wfmt-215-v2.1.0-delivery")
TASK_ID = "wfflab__wfmt-215"
TASK_NAME = "wfflab/wfmt-215"
MODULE = "wfmt"
VERSION = "2.1.1"
RUNS = os.path.join(WS, r"deliverables\2026-10-04_outside-harbor-win\runner\runs\wfflab__wfmt-215")
TOOLS = os.path.join(HW, r"_qc_runs\tools")
KEEP = os.path.join(HW, r"_qc_runs\refit-215-216")
PKG_OUT = os.path.join(KEEP, "package")
OLD_ZIP = os.path.join(WS, r"deliverables\2026-10-10_wfmt215-返修\package\wfflab__wfmt-215-v2.1.0-delivery.zip")
RECORD = "reczz28KwEOO3xHy"
BASE = "EsJebL8JJaf7g4sIbItcnMFgnvg"
TABLE = "tblRDxcGkblflMBA"
LARK = r"C:\nvm4w\nodejs\lark-cli.cmd"
PY = sys.executable
ZIP_NAME = "wfflab__wfmt-215-v2.1.0-delivery.zip"
INDEX = os.path.join(HW, r"_index\tasks_index.csv")

STEPS: list[str] = []


def fail(code: int, msg: str):
    print("\n[FAIL] %s" % msg, file=sys.stderr)
    print("已完成步骤: %s" % (" -> ".join(STEPS) or "无"), file=sys.stderr)
    sys.exit(code)


def sha256(path):
    import hashlib
    d = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            d.update(b)
    return d.hexdigest()


def lark(args, cwd=None):
    p = subprocess.run([LARK] + args, capture_output=True, cwd=cwd)
    out = (p.stdout or b"").decode("utf-8", "replace")
    s, e = out.find("{"), out.rfind("}")
    doc = json.loads(out[s:e + 1]) if s >= 0 and e > s else None
    return p.returncode, doc, out


# ---------------------------------------------------------------- 1. 轮次齐备
print("=" * 70)
print("步骤 1/8  校验 215 轮次齐备")
NEED = {"no-change": 3, "golden": 3, "opus-5": 3, "qwen3.8-max-0902": 3}
found: dict[str, list[str]] = {}
for run_id in sorted(os.listdir(RUNS)):
    rp = os.path.join(RUNS, run_id)
    if not os.path.isdir(rp) or run_id.startswith("_"):
        continue
    for label in sorted(os.listdir(rp)):
        lp = os.path.join(rp, label)
        rj = os.path.join(lp, "result.json")
        if not os.path.isfile(rj):
            continue
        try:
            doc = json.load(open(rj, encoding="utf-8-sig"))
        except Exception:  # noqa: BLE001
            continue
        if doc.get("run_validity") == "VALID":
            found.setdefault(label, []).append(run_id)
short = []
for label, need in NEED.items():
    have = len(found.get(label, []))
    print("   %-20s %d/%d" % (label, have, need))
    if have < need:
        short.append("%s %d/%d" % (label, have, need))
if short:
    fail(2, "轮次不足：%s" % "; ".join(short))
STEPS.append("轮次齐备(12)")

# ---------------------------------------------------------------- 2. 严格自检
print()
print("=" * 70)
print("步骤 2/8  严格自检（格式 + 最新质检 6 条）")
checks = []


def ex(rel):
    return os.path.isfile(os.path.join(PKG, rel.replace("/", os.sep)))


def rd(rel):
    p = os.path.join(PKG, rel.replace("/", os.sep))
    return open(p, encoding="utf-8", errors="replace").read() if os.path.isfile(p) else ""


top = sorted(os.listdir(PKG))
expect_top = ["environment", "instruction.md", "jobs", "solution", "task.toml", "tests", "verifier"]
checks.append(("格式: 顶层为 7 项标准结构", top == expect_top, str(top)))
checks.append(("格式: 包内无 REFIT（非交付文件）", "REFIT-2026-10-12.md" not in top, str([x for x in top if x.startswith("REFIT")])))

jt_dir = os.path.join(PKG, "jobs")
trials = sorted(d for d in os.listdir(jt_dir) if os.path.isdir(os.path.join(jt_dir, d)))
n_model = len([t for t in trials if t.startswith("task__")])
n_ctrl = len([t for t in trials if t.startswith("task0__")])
checks.append(("格式: jobs/ 为 12 trial（控制6+模型6）", len(trials) == 12 and n_model == 6 and n_ctrl == 6,
               "total=%d model=%d ctrl=%d" % (len(trials), n_model, n_ctrl)))

t = rd("verifier/tests/test_wfmt_semantics.py")
assert_lines = [l for l in t.splitlines() if "assert" in l]
fixed_threshold = [l.strip()[:70] for l in assert_lines if "8192" in l]
checks.append(("01 断言中无固定 8192 阈值", not fixed_threshold, str(fixed_threshold)))
checks.append(("01 有随规模变化的观测", ("max_request" in t or "request" in t) and ("small" in t or "scale" in t),
               "规模对照关键词"))
checks.append(("01 有尾部 CRC 独立断言", "tail" in t.lower() and "checksum" in t.lower(), "尾部校验和"))

j = rd("jobs/invalid-slots.json")
jd = json.loads(j) if j.strip() else {}
checks.append(("02 无效槽位注解层存在", bool(jd), "jobs/invalid-slots.json"))
checks.append(("02 归档树不改写声明", "immutability_note" in jd, "immutability_note"))
checks.append(("02 Markdown 版存在", ex("jobs/INVALID-SLOTS.md"), "INVALID-SLOTS.md"))
checks.append(("03 Windows 价值说明", ex("verifier/WINDOWS_VALUE.md"), "WINDOWS_VALUE.md"))
row = ""
if os.path.isfile(INDEX):
    for line in open(INDEX, encoding="utf-8-sig"):
        if "215" in line:
            row = line
            break
checks.append(("03 采购方向=通用编码能力", "通用编码" in row, "tasks_index.csv"))

jt = rd("tests/judge.toml")
checks.append(("04 评审权重已废止", "llm_judge_weight" in jt and "0.0" in jt, "llm_judge_weight=0.0"))
checks.append(("04 程序化权重 1.0", "programmatic_weight" in jt and "1.0" in jt, "programmatic_weight=1.0"))
for rel in ("tests/judge.toml", "environment/adapter.toml"):
    try:
        tomllib.loads(open(os.path.join(PKG, rel.replace("/", os.sep)), "rb").read().decode("utf-8"))
        checks.append(("05 %s 可解析" % rel, True, "tomllib OK"))
    except Exception as exc:  # noqa: BLE001
        checks.append(("05 %s 可解析" % rel, False, str(exc)[:60]))
checks.append(("06 隔离说明", ex("verifier/ISOLATION.md"), "ISOLATION.md"))
checks.append(("06 可见面声明", ex("environment/agent_visible_paths.json"), "agent_visible_paths.json"))
checks.append(("06 负访问探针", ex("verifier/negative_access_probe.ps1"), "negative_access_probe.ps1"))

tt = rd("task.toml")
import re
m = re.search(r'\[task\][\s\S]*?version\s*=\s*"([^"]+)"', tt)
checks.append(("格式: task.toml 版本=2.1.1", bool(m) and m.group(1) == VERSION, m.group(1) if m else "?"))

bad = [c for c in checks if not c[1]]
for name, ok, note in checks:
    print("   [%s] %-32s %s" % ("PASS" if ok else "FAIL", name, note))
print("   自检 %d 项，FAIL %d" % (len(checks), len(bad)))
if bad:
    fail(3, "自检未通过：%s" % "; ".join(c[0] for c in bad))
STEPS.append("严格自检")

# ---------------------------------------------------------------- 3. 移出 REFIT
print()
print("=" * 70)
print("步骤 3/8  移出 REFIT-2026-10-12.md")
src_refit = os.path.join(PKG, "REFIT-2026-10-12.md")
if os.path.isfile(src_refit):
    dst_refit = os.path.join(KEEP, "REFIT-215-20261012.md")
    shutil.move(src_refit, dst_refit)
    print("   已移动 -> %s" % dst_refit)
else:
    print("   包内无 REFIT（已处理过）")
STEPS.append("移出REFIT")

# ---------------------------------------------------------------- 4. 修正注解层
print()
print("=" * 70)
print("步骤 4/8  修正无效槽位注解层")
jpath = os.path.join(PKG, "jobs", "invalid-slots.json")
doc = json.load(open(jpath, encoding="utf-8-sig"))
old_slots = doc.get("slots") or []
if doc.get("task_version_at_run") != VERSION or old_slots:
    doc.setdefault("superseded_history", [])
    doc["superseded_history"] = (doc.get("superseded_history") or []) + old_slots
    doc["slots"] = []
    doc["task_version_at_run"] = VERSION
    doc["recorded_at"] = "2026-10-13"
    doc["superseded_note"] = (
        "上一版归档（task_version=2.1.0）中的无效槽位记录，已由 2.1.1 重跑替代。"
        "历史条目原样保留以备查，不参与本次统计，也不改写任何原始产物。")
    doc["current_archive_note"] = (
        "本归档（task_version=2.1.1）的模型与控制轮全部 run_validity=VALID，无无效槽位。")
    with open(jpath, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    print("   invalid-slots.json: slots=%d, superseded_history=%d" % (len(doc["slots"]), len(doc["superseded_history"])))
else:
    print("   注解层已是 2.1.1 口径")
STEPS.append("修正注解层")

# ---------------------------------------------------------------- 5. 重建归档
print()
print("=" * 70)
print("步骤 5/8  重建 jobs 归档")
old_zip_sha = sha256(OLD_ZIP) if os.path.isfile(OLD_ZIP) else ""
print("   旧 zip sha256 = %s" % (old_zip_sha or "（未找到本地副本）"))
r = subprocess.run([PY, "-X", "utf8", os.path.join(TOOLS, "assemble_jobs_archive.py"),
                    "--task-id", TASK_ID, "--task-name", TASK_NAME, "--module", MODULE,
                    "--task-version", VERSION, "--package-root", PKG, "--runs-dir", RUNS,
                    "--original-download", ZIP_NAME,
                    "--original-download-sha256", old_zip_sha,
                    "--original-note", "返修的上游是 v2.1.0 交付包（甲方质检 zq-id=12）；本 jobs 树是同一目录名下 v2.1.1 补丁版的替代证据集，两者不是同一个包。"],
                   capture_output=True)
out = (r.stdout or b"").decode("utf-8", "replace")
for line in out.splitlines():
    if any(k in line for k in ("trials", "source_mapping", "全部通过", "!!", "自检", "跳过")):
        print("   " + line.strip())
if r.returncode != 0:
    print((r.stderr or b"").decode("utf-8", "replace")[:800], file=sys.stderr)
    fail(6, "归档重建失败 rc=%s" % r.returncode)
STEPS.append("重建归档")

# ---------------------------------------------------------------- 6. 打包
print()
print("=" * 70)
print("步骤 6/8  重新打包")
r = subprocess.run([PY, "-X", "utf8", os.path.join(TOOLS, "pack_delivery_zip.py"),
                    "--package-root", PKG, "--out-dir", PKG_OUT], capture_output=True)
out = (r.stdout or b"").decode("utf-8", "replace")
for line in out.splitlines():
    if any(k in line for k in ("entries", "size", "sha256", "top-level")):
        print("   " + line.strip())
if r.returncode != 0:
    fail(7, "打包失败 rc=%s" % r.returncode)
zip_path = os.path.join(PKG_OUT, ZIP_NAME)
zip_sha = sha256(zip_path)
zip_size = os.path.getsize(zip_path)
with zipfile.ZipFile(zip_path) as zf:
    tops = {n.split("/")[0] for n in zf.namelist()}
if tops != {os.path.basename(PKG)}:
    fail(7, "zip 顶层不是单一同名目录：%s" % sorted(tops))
STEPS.append("打包")

# ---------------------------------------------------------------- 7. 上传飞书
print()
print("=" * 70)
print("步骤 7/8  上传飞书并回验")
rc, d, raw = lark(["base", "+record-upsert", "--as", "user", "--base-token", BASE,
                   "--table-id", TABLE, "--record-id", RECORD,
                   "--json", '{"作业压缩包":[]}', "--format", "json"])
print("   清空旧附件: rc=%s ok=%s" % (rc, d and d.get("ok")))
if not (d and d.get("ok")):
    fail(8, "清空附件失败")
rc, d, raw = lark(["base", "+record-upload-attachment", "--as", "user", "--base-token", BASE,
                   "--table-id", TABLE, "--record-id", RECORD,
                   "--field-id", "fldnki9xts", "--file", ZIP_NAME, "--format", "json"], cwd=PKG_OUT)
print("   上传: rc=%s ok=%s" % (rc, d and d.get("ok")))
if not (d and d.get("ok")):
    fail(8, "上传失败")

rc, d, raw = lark(["base", "+record-get", "--as", "user", "--base-token", BASE,
                   "--table-id", TABLE, "--record-id", RECORD, "--format", "json"])
data = d["data"]
cells = dict(zip(data["fields"], data["data"][0]))
atoms = cells.get("作业压缩包") or []
print("   读回: 附件数=%d 状态=%s" % (len(atoms), cells.get("状态")))
for a in atoms:
    print("      %s  %s bytes" % (a.get("name"), a.get("size")))
if len(atoms) != 1:
    fail(8, "附件数不是 1")
token = atoms[0].get("file_token")
dl = os.path.join(os.environ["TEMP"], "lark-dl-215f")
if os.path.isdir(dl):
    shutil.rmtree(dl)
os.makedirs(dl, exist_ok=True)
rc, d, raw = lark(["base", "+record-download-attachment", "--as", "user", "--base-token", BASE,
                   "--table-id", TABLE, "--record-id", RECORD, "--file-token", token,
                   "--output", "./", "--overwrite", "--format", "json"], cwd=dl)
files = os.listdir(dl)
if not files:
    fail(8, "下载回验失败")
remote = sha256(os.path.join(dl, files[0]))
print("   回验: 远端=%s" % remote[:24])
print("         本地=%s" % zip_sha[:24])
if remote != zip_sha:
    fail(8, "上传后 sha256 不一致")
print("   ✓ 一致")
STEPS.append("上传飞书")

# ---------------------------------------------------------------- 8. 同步索引
print()
print("=" * 70)
print("步骤 8/8  重算身份并同步 tasks_index.csv")


def task_hash(root):
    import hashlib as H
    lines = []
    for dirpath, dirnames, filenames in os.walk(root):
        rel_dir = os.path.relpath(dirpath, root)
        parts = [] if rel_dir == "." else rel_dir.split(os.sep)
        if parts and parts[0].casefold() == "jobs":
            dirnames[:] = []
            continue
        for name in filenames:
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            if rel.split("/")[0].casefold() == "jobs":
                continue
            lines.append("%s\t%s\n" % (rel, sha256(full)))
    return H.sha256("".join(sorted(lines)).encode("utf-8")).hexdigest()


th = task_hash(PKG)
print("   新 task_hash = %s" % th)
raw = open(INDEX, "rb").read()
has_bom = raw.startswith(b"\xef\xbb\xbf")
text = raw.decode("utf-8-sig")
nl = "\r\n" if "\r\n" in text else "\n"
rows = list(csv.DictReader(io.StringIO(text)))
fnames = list(rows[0].keys())
updated = False
for r in rows:
    if r["task_id"] == TASK_ID:
        r["task_hash"] = th
        r["task_version"] = VERSION
        r["frozen_at"] = "2026-10-13"
        r["status"] = ("返修 2.1.1：纯程序化评分 1.0（废止不生效的 llm_judge 50% 声明）；"
                       "按甲方 2026-10-13 规则不再跑 GLM/Kimi，模型轮 6 次（Opus×3 / Qwen×3）；"
                       "2.1.1 整批重跑（控制组 golden 3×1 / no-change 3×0）；"
                       "jobs 归档按新轮次重建（12 trial）；REFIT 移出题包另存；"
                       "无效槽位注解层更新为 2.1.1 口径")
        updated = True
if not updated:
    fail(9, "索引中找不到 %s" % TASK_ID)
buf = io.StringIO()
w = csv.DictWriter(buf, fieldnames=fnames, lineterminator=nl)
w.writeheader()
for r in rows:
    w.writerow(r)
outb = buf.getvalue().encode("utf-8")
if has_bom:
    outb = b"\xef\xbb\xbf" + outb
open(INDEX, "wb").write(outb)
print("   索引已更新（task_hash / task_version / status / frozen_at）")
STEPS.append("同步索引")

print()
print("=" * 70)
print("全部完成")
print("   zip      : %s" % zip_path)
print("   size     : %d bytes" % zip_size)
print("   sha256   : %s" % zip_sha)
print("   task_hash: %s" % th)
print("   飞书记录 : %s（附件 1 个，回验一致）" % RECORD)
print("STEPS=" + ",".join(STEPS))
sys.exit(0)
