#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_windows_mechanism.py — Windows 专属机制门禁（2026-10-14 起硬性）

背景
----
甲方质检把「题目的主要实现、错误根因或 Evaluator 是否实质依赖 Windows 平台语义」
作为采购资格判据（48 题报告 windows-value.json；专家修复步骤第 3 条：
"若需要 Windows 专属评测，新增有实际产品需求的 Windows 语义，发布新版后重新作答"）。
wfflab__wchunk-216 / wfflab__wfmt-215 / wfflab__wlogseg-218 三题被判「Windows 专属价值低」，
根因是判据只落在平台无关的字节层（容器格式 / CRC / 流式 IO），而包内
`verifier/WINDOWS_VALUE.md` 还**自己写明**"不主张 Windows 反事实价值、按通用编码能力归类"。

本脚本把该判定从"人工判断题"变成"可复算的门禁题"：
每题必须在题包内提供 `windows_mechanism.json`，逐条给出**可在题面与测试中定位**的机制证据。
缺证据、证据定位不到、或包内出现自我否认 Windows 价值的表述 —— 一律 FAIL。

判据（全部可复算，无人工判断）
------------------------------
F1  门禁产物存在（`delivery-extras/tasks/<task-id>/metadata/windows_mechanism.json`
    或题包内 `metadata/windows_mechanism.json`）。
F2  `counterfactual.answer` 必须为「否」，且有 `reason`。
      反事实问题：把目标 OS 换成 Linux/macOS，主要实现、错误根因、Evaluator 是否基本不变？
F3  `exclusive_declaration.quote` 必须在 `instruction.md` 中**逐字出现**
    （排他声明把其他操作系统排除出验收范围，是 Windows 属性的加强项）。
F4  `mechanisms` 至少 3 条；每条必须有 `name` / `instruction_quote` / `test_ref` / `f2p_case`，
    且：
      - `instruction_quote`（≥8 字符）在 `instruction.md` 中逐字出现；
      - `test_ref` 形如 `tests/run_tests.ps1#L417-L451`，文件存在、行号在文件范围内；
      - `f2p_case` 出现在 `tests/required_testcases.json` 且 `group == "F2P"`。
F5  `non_windows_must_fail` 必须指向包内真实文件，`evidence` 逐字出现，
    且 evidence 含平台判定关键字（$IsWindows / Win32NT / OSVersion / DriveFormat /
    PipeTransmissionMode / GetFileInformationByHandle 等）。
F6  包内**不得出现自我否认 Windows 价值的表述**（自认句会直接被甲方引为不合格证据）。
      判据表与扫描器在 `scripts/self_denial_scan.py`，与 `package_task_zip.py` 的
      出包前扫描共享同一份实现（两边结果必须一致）。
      F6 修过两次精度问题（2026-10-14 复核）：
        ① **词距盲区**：旧写法 `通用编码(能力|题池|题)` 要求关键词紧邻，漏掉了
           `已按同一口径**明确归入通用编码能力**，不主张` 这种中间夹字的形态；
           现行写法允许 `通用编码` 与 `能力|题池|题` 之间夹 ≤8 个任意字符。
        ② **引文误报**：把 `对应甲方要求：…「否则归入通用编码题池」` 这类
           **转述甲方条款**当成自认。现行写法加了「否定前缀 / 引用来源」两类
           可复算的子串判据；被抑制的条目可用
           `python self_denial_scan.py <目录> --include-suppressed` 逐条核对。

用法
----
    python check_windows_mechanism.py --task-dir <题包目录>
    python check_windows_mechanism.py --task-dir <题包目录> --extras <delivery-extras目录>
    python check_windows_mechanism.py --package <平铺题包根目录> --json report.json
    python check_windows_mechanism.py --task-dir <题包目录> --allow-legacy-exempt

    # 只查 F6 的自认句（含被抑制条目的核对视图）
    python self_denial_scan.py <题包目录> --include-suppressed

退出码
------
    0  该题通过机制门禁（可能含 FLAG）
    1  存在 FAIL
    2  参数或读取错误

历史包豁免
----------
默认**不豁免**。仅当显式传 `--allow-legacy-exempt` 且题包内存在
`WINDOWS_MECHANISM_EXEMPT.md`（须写明"该包按通用编码题池交付，不申报 Windows 专属能力"）
时，F1–F5 降级为 FLAG；**F6（自认句）永不免除**。
豁免存在的意义是不追溯改判历史样本（甲方口径：新需求不得追溯扣旧样本），
而不是给新题开后门。
"""

import argparse
import json
import os
import re
import sys

# F6 的扫描实现与「出包前扫描」共享同一份判据（scripts/self_denial_scan.py），
# 避免出现"门禁绿、打包红"的自相矛盾。脚本按文件路径并列存放，直接就地导入。
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from self_denial_scan import (  # noqa: E402  (必须在 sys.path 调整之后)
    EXEMPT_FILE,
    SELF_DENIAL_PATTERNS,
    scan_self_denial,
)

# ---------------------------------------------------------------- 常量

GATE_FILE_CANDIDATES = [
    os.path.join("metadata", "windows_mechanism.json"),
    "windows_mechanism.json",
]

# 排他声明：把其他操作系统排除出验收范围（加强 Windows 属性，不是免责）
EXCLUSIVE_HINTS = (
    "不需要实现其他操作系统",
    "不涉及其他操作系统",
    "仅 Windows",
    "只在 Windows",
    "不依赖其他操作系统",
    "验收使用真实 Windows",
    "真实 Windows Runtime",
)

# 平台判定关键字：环境层"非 Windows 必然失败"的复算锚点
PLATFORM_KEYWORDS = (
    "$IsWindows",
    "IsWindows",
    "Win32NT",
    "OSVersion",
    "DriveFormat",
    "OS -ne 'Windows_NT'",
    'OS -ne "Windows_NT"',
    "PipeTransmissionMode",
    "GetFileInformationByHandle",
    "RegNotifyChangeKeyValue",
    "CreateFileW",
    "CreateHardLinkW",
    "EventWaitHandle",
    "AbandonedMutexException",
    "Microsoft.Win32.Registry",
    "NTFS",
)

# 自我否认 / 通用化表述的判据表与扫描器已迁到 self_denial_scan.py（本模块 re-export）。
# 旧的 `通用编码(能力|题池|题)` 写法有词距盲区：漏掉
# `已按同一口径**明确归入通用编码能力**，不主张`（关键词之间夹了 Markdown 粗体与语气副词）。
# 现行写法允许 `通用编码` 与 `能力|题池|题` 之间夹 ≤8 个任意字符，并加了
# 「否定前缀 / 引用来源」两类上下文防误报判定。

TEST_REF_RE = re.compile(r"^(?P<path>[^#]+)(?:#L(?P<start>\d+)(?:-L?(?P<end>\d+))?)?$")


class Result:
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.notes = []

    def error(self, msg):
        self.errors.append(msg)

    def warn(self, msg):
        self.warnings.append(msg)

    def note(self, msg):
        self.notes.append(msg)

    @property
    def valid(self):
        return not self.errors


# ---------------------------------------------------------------- 工具

def read_text(path):
    try:
        with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
            return f.read()
    except OSError:
        return None


def read_json(path):
    txt = read_text(path)
    if txt is None:
        return None
    try:
        return json.loads(txt)
    except json.JSONDecodeError:
        return None


def line_count(path):
    txt = read_text(path)
    return None if txt is None else len(txt.splitlines())


def task_id_of(task_dir, gate):
    tid = (gate or {}).get("task_id")
    if tid:
        return str(tid)
    txt = read_text(os.path.join(task_dir, "task.toml")) or ""
    m = re.search(r'(?m)^\s*task_id\s*=\s*"([^"]+)"', txt)
    return m.group(1) if m else os.path.basename(os.path.normpath(task_dir))


def find_gate_file(task_dir, extras_dir, tid):
    """按优先级定位门禁产物；extras_dir 为 delivery-extras/ 根。"""
    cands = []
    if extras_dir:
        cands.append(os.path.join(extras_dir, "tasks", tid, "metadata", "windows_mechanism.json"))
        cands.append(os.path.join(extras_dir, "windows_mechanism.json"))
    for rel in GATE_FILE_CANDIDATES:
        cands.append(os.path.join(task_dir, rel))
    # 题包同级 delivery-extras/
    cands.append(os.path.join(task_dir, "delivery-extras", "tasks", tid,
                              "metadata", "windows_mechanism.json"))
    for c in cands:
        if os.path.isfile(c):
            return c
    return None


def required_cases(task_dir):
    """返回 {case_id: group}；兼容 list / {"testcases": [...]} / {"required": [...]}。"""
    path = os.path.join(task_dir, "tests", "required_testcases.json")
    data = read_json(path)
    if data is None:
        return None
    rows = data
    if isinstance(data, dict):
        for key in ("testcases", "required", "cases", "items"):
            if isinstance(data.get(key), list):
                rows = data[key]
                break
    out = {}
    if not isinstance(rows, list):
        return out
    for row in rows:
        if not isinstance(row, dict):
            continue
        cid = row.get("id") or row.get("test_id") or row.get("case_id")
        if not cid:
            continue
        group = row.get("group") or row.get("kind") or ""
        out[str(cid)] = str(group).upper()
    return out


def scan_denial_hits(task_dir):
    """F6 扫描：返回真命中（未被子串判据抑制）的自我否认表述。

    实现委托 `self_denial_scan.scan_self_denial`，与 `package_task_zip.py` 的出包前
    扫描逐字共享同一份判据表 —— 两边结果必须一致，否则会出现"门禁绿、打包红"。

    返回 [(相对路径, 行号, 片段, 说明)]，保持历史调用方的元组形态。
    """
    hits = scan_self_denial(task_dir)
    return [(h["file"], h["line"], h["text"], h["why"]) for h in hits]


# ---------------------------------------------------------------- 门禁

def check_task(task_dir, extras_dir=None, allow_legacy_exempt=False):
    res = Result()
    task_dir = os.path.abspath(task_dir)
    if not os.path.isdir(task_dir):
        res.error("题包目录不存在: %s" % task_dir)
        return res, {}

    gate_path = None
    tid_guess = None
    # 先粗定位一次拿 task_id
    tid_guess = task_id_of(task_dir, None)
    gate_path = find_gate_file(task_dir, extras_dir, tid_guess)
    gate = read_json(gate_path) if gate_path else None
    tid = task_id_of(task_dir, gate)

    exempt = False
    exempt_path = os.path.join(task_dir, EXEMPT_FILE)
    if os.path.isfile(exempt_path):
        if allow_legacy_exempt:
            exempt = True
            res.warn("历史包豁免生效（%s）：F1–F5 降级为 FLAG；F6 不免除" % EXEMPT_FILE)
            res.warn("豁免标记只作内部登记：**打包交付前必须删除 %s**，否则等同于把"
                     "『该题归通用题池』的自认交到甲方手里" % EXEMPT_FILE)
        else:
            res.warn("存在 %s，但未传 --allow-legacy-exempt，按常规门禁判定" % EXEMPT_FILE)

    def fail_or_flag(msg):
        if exempt:
            res.warn("[豁免] " + msg)
        else:
            res.error(msg)

    summary = {"task_id": tid, "gate_file": gate_path, "mechanisms": []}

    # ---- F1 门禁产物
    if gate is None:
        fail_or_flag("未找到门禁产物 windows_mechanism.json（应在 "
                     "delivery-extras/tasks/%s/metadata/ 或题包 metadata/ 下）" % tid)
    else:
        res.note("门禁产物: %s" % os.path.relpath(gate_path, task_dir).replace("\\", "/"))

    instruction = read_text(os.path.join(task_dir, "instruction.md")) or ""
    if not instruction:
        res.error("缺少或无法读取 instruction.md")

    # ---- F2 反事实判定
    cf = (gate or {}).get("counterfactual") or {}
    if gate is not None:
        answer = str(cf.get("answer", "")).strip()
        if answer not in ("否", "no", "No", "NO"):
            fail_or_flag("反事实判定未通过：counterfactual.answer=%r（必须为「否」）" % answer)
        elif not str(cf.get("reason", "")).strip():
            fail_or_flag("反事实判定缺 counterfactual.reason（必须写明为什么换 OS 后不成立）")
        else:
            res.note("反事实判定: 否 — %s" % str(cf["reason"])[:120])

    # ---- F3 排他声明
    decl = (gate or {}).get("exclusive_declaration") or {}
    quote = str(decl.get("quote", "")).strip()
    if gate is not None:
        if len(quote) < 8:
            fail_or_flag("exclusive_declaration.quote 缺失或过短（需 ≥8 字符，且逐字出现在 instruction.md）")
        elif quote not in instruction:
            fail_or_flag("排他声明未在 instruction.md 中逐字出现: %r" % quote[:80])
        else:
            res.note("排他声明已锚定 instruction.md: %s" % quote[:80])
        # 若 instruction 本身含排他语义但未登记，提示补齐
        if not quote and any(h in instruction for h in EXCLUSIVE_HINTS):
            res.warn("instruction.md 已含排他语义，但未在门禁产物中登记 exclusive_declaration.quote")

    # ---- F4 机制条目
    mechs = (gate or {}).get("mechanisms")
    if gate is not None:
        if not isinstance(mechs, list) or not mechs:
            fail_or_flag("mechanisms 缺失或为空（至少 3 条，且每条可定位到题面与测试）")
            mechs = []
        elif len(mechs) < 3:
            fail_or_flag("mechanisms 只登记 %d 条，少于 3 条" % len(mechs))
        req = required_cases(task_dir)
        if req is None:
            res.warn("无法读取 tests/required_testcases.json，跳过 f2p_case 校验")
            req = {}
        for idx, m in enumerate(mechs, 1):
            if not isinstance(m, dict):
                fail_or_flag("mechanisms[%d] 不是对象" % idx)
                continue
            name = str(m.get("name", "")).strip()
            iq = str(m.get("instruction_quote", "")).strip()
            tref = str(m.get("test_ref", "")).strip()
            case = str(m.get("f2p_case", "")).strip()
            entry = {"name": name, "instruction_quote": iq, "test_ref": tref, "f2p_case": case}
            if not name:
                fail_or_flag("mechanisms[%d] 缺 name" % idx)
            if len(iq) < 8:
                fail_or_flag("mechanisms[%d]（%s）instruction_quote 缺失或过短" % (idx, name or "?"))
            elif iq not in instruction:
                fail_or_flag("mechanisms[%d]（%s）instruction_quote 未在 instruction.md 中逐字出现: %r"
                             % (idx, name or "?", iq[:60]))
            if not tref:
                fail_or_flag("mechanisms[%d]（%s）缺 test_ref" % (idx, name or "?"))
            else:
                mm = TEST_REF_RE.match(tref)
                relpath = (mm.group("path") if mm else tref).replace("\\", "/").lstrip("/")
                fpath = os.path.join(task_dir, relpath)
                if not os.path.isfile(fpath):
                    fail_or_flag("mechanisms[%d]（%s）test_ref 指向的文件不存在: %s"
                                 % (idx, name or "?", relpath))
                elif mm and mm.group("start"):
                    total = line_count(fpath) or 0
                    start = int(mm.group("start"))
                    end = int(mm.group("end") or start)
                    if start < 1 or end > total or start > end:
                        fail_or_flag("mechanisms[%d]（%s）test_ref 行号越界: %s（文件 %d 行）"
                                     % (idx, name or "?", tref, total))
            if not case:
                fail_or_flag("mechanisms[%d]（%s）缺 f2p_case（必须绑定一条 F2P 用例）"
                             % (idx, name or "?"))
            elif req and case not in req:
                fail_or_flag("mechanisms[%d]（%s）f2p_case=%s 不在 tests/required_testcases.json 中"
                             % (idx, name or "?", case))
            elif req and req.get(case) != "F2P":
                fail_or_flag("mechanisms[%d]（%s）f2p_case=%s 的 group=%s，必须为 F2P"
                             % (idx, name or "?", case, req.get(case)))
            if len(entry["name"]) and len(entry["instruction_quote"]) and len(entry["test_ref"]):
                summary["mechanisms"].append(entry)
        if len(mechs) >= 3 and all(isinstance(x, dict) for x in mechs) and len(mechs) < 4:
            res.warn("mechanisms 仅 %d 条，建议覆盖 3 个以上机制族" % len(mechs))

    # ---- F5 非 Windows 必然失败
    nmf = (gate or {}).get("non_windows_must_fail") or {}
    if gate is not None:
        f = str(nmf.get("file", "")).strip()
        ev = str(nmf.get("evidence", "")).strip()
        if not f or not ev:
            fail_or_flag("non_windows_must_fail 缺 file/evidence（必须指向包内真实文件与逐字证据）")
        else:
            fpath = os.path.join(task_dir, f.replace("\\", "/").lstrip("/"))
            if not os.path.isfile(fpath):
                fail_or_flag("non_windows_must_fail.file 不存在: %s" % f)
            else:
                txt = read_text(fpath) or ""
                if ev not in txt:
                    fail_or_flag("non_windows_must_fail.evidence 未在 %s 中逐字出现: %r" % (f, ev[:80]))
                elif not any(k in ev for k in PLATFORM_KEYWORDS):
                    fail_or_flag("non_windows_must_fail.evidence 不含平台判定关键字（%s）: %r"
                                 % ("/".join(PLATFORM_KEYWORDS[:5]) + " …", ev[:80]))
                else:
                    res.note("非 Windows 必然失败锚点: %s → %s" % (f, ev[:60]))

    # ---- F6 自认句（永不豁免）
    hits = scan_denial_hits(task_dir)
    if hits:
        detail = "; ".join("%s:%d %s" % (h[0], h[1], h[3]) for h in hits[:6])
        res.error("包内出现自我否认 / 通用化 Windows 价值的表述（%d 处）：%s" % (len(hits), detail))
        summary["self_denial"] = [{"file": h[0], "line": h[1], "why": h[3]} for h in hits]
    else:
        res.note("未发现自我否认 Windows 价值的表述")

    return res, summary


# ---------------------------------------------------------------- CLI

def main():
    ap = argparse.ArgumentParser(description="Windows 专属机制门禁（可复算）")
    ap.add_argument("--task-dir", help="单个题包目录（含 task.toml）")
    ap.add_argument("--package", help="平铺题包根目录（其下每个含 task.toml 的子目录为一题）")
    ap.add_argument("--extras", help="delivery-extras 目录（门禁产物可能在其 tasks/<id>/metadata/ 下）")
    ap.add_argument("--json", help="把结果写入 JSON 文件")
    ap.add_argument("--allow-legacy-exempt", action="store_true",
                    help="允许历史包通过 WINDOWS_MECHANISM_EXEMPT.md 把 F1–F5 降级为 FLAG（F6 不免除）")
    args = ap.parse_args()

    if not args.task_dir and not args.package:
        print("错误: 需指定 --task-dir 或 --package", file=sys.stderr)
        return 2

    tasks = []
    if args.task_dir:
        tasks.append(os.path.abspath(args.task_dir))
    if args.package:
        pkg = os.path.abspath(args.package)
        if not os.path.isdir(pkg):
            print("错误: 目录不存在 %s" % pkg, file=sys.stderr)
            return 2
        for d in sorted(os.listdir(pkg)):
            full = os.path.join(pkg, d)
            if os.path.isdir(full) and os.path.isfile(os.path.join(full, "task.toml")):
                tasks.append(full)
        if not tasks:
            print("错误: %s 下未找到含 task.toml 的题目录" % pkg, file=sys.stderr)
            return 2

    report = {"tasks": [], "fail": 0, "pass": 0}
    for td in tasks:
        res, summary = check_task(td, args.extras, args.allow_legacy_exempt)
        icon = "PASS" if res.valid else "FAIL"
        print("=" * 88)
        print("%s  %s" % (icon, summary.get("task_id") or os.path.basename(td)))
        for n in res.notes:
            print("   [note] %s" % n)
        for w in res.warnings:
            print("   [FLAG] %s" % w)
        for e in res.errors:
            print("   [FAIL] %s" % e)
        report["tasks"].append({
            "task_dir": td,
            "task_id": summary.get("task_id"),
            "valid": res.valid,
            "errors": res.errors,
            "warnings": res.warnings,
            "notes": res.notes,
            "mechanisms": summary.get("mechanisms", []),
            "self_denial": summary.get("self_denial", []),
        })
        report["fail" if not res.valid else "pass"] += 1

    print("=" * 88)
    print("通过 %d 题 / 失败 %d 题" % (report["pass"], report["fail"]))
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print("报告已写入 %s" % args.json)
    return 1 if report["fail"] else 0


if __name__ == "__main__":
    sys.exit(main())
