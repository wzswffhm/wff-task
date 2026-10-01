#!/usr/bin/env python3
"""
grade.py —— 程序化二值评分骨架

参考来源：Windows_SWE_d70d30df 27 题现包的 tests/grade.py（已验证可用）

规范要求（第六章 6.2 / 第十章 10.3）：
  - required F2P 全过 且 required P2P 全过 且 无 required 失败 → score = 1.0
  - 否则 → score = 0.0
  - 缺失 / SKIP / 解析失败 / 环境异常 → INVALID（**不写 reward 产物**，exit 2）
  - **禁止**权重、部分分、LLM Judge

用法：
    python grade.py <log_path> <logs_root>

产物（写入 <logs_root>/verifier/）：
    report.json          诊断报告（INVALID 时也会写）
    reward.txt           0 或 1（仅 VALID 时写）
    reward.json          {"reward": 0|1}（仅 VALID 时写）
    reward-details.json  评分依据（仅 VALID 时写）
"""

import datetime
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time

_t0 = time.time()
TESTS = os.path.dirname(os.path.abspath(__file__))
SPEC_PATH = os.path.join(TESTS, "swelive_spec.json")
spec = json.load(open(SPEC_PATH, encoding="utf-8"))

log_path = sys.argv[1]
logs_root = sys.argv[2]

# 全局预算：防止各阶段累加超出调用方 timeout
GRADE_BUDGET = int(os.environ.get("SWELIVE_GRADE_BUDGET_SEC", "900"))
PARSER_BUDGET = max(30, GRADE_BUDGET // 3)

log = open(log_path, encoding="utf-8", errors="replace").read()


# ------------------------------------------------------------------ 证据哈希

def _sha256(path):
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            for block in iter(lambda: f.read(1024 * 1024), b""):
                h.update(block)
    except OSError:
        return None
    return h.hexdigest()


def _source_commit():
    """优先环境变量；其次读取 C:\\testbed 的 git HEAD；最后回落到 spec 记录。"""
    value = os.environ.get("SWELIVE_SOURCE_COMMIT")
    if value:
        return value
    candidates = [
        shutil.which("git.exe"),
        shutil.which("git"),
        r"C:\git\cmd\git.exe",
        r"C:\Program Files\Git\cmd\git.exe",
    ]
    for executable in dict.fromkeys(p for p in candidates if p):
        try:
            return subprocess.check_output(
                [executable, "-C", r"C:\testbed", "rev-parse", "HEAD"],
                text=True, stderr=subprocess.DEVNULL, timeout=10,
            ).strip()
        except Exception:
            continue
    # host 侧评分没有 Windows checkout；task metadata 对一次运行不可变，
    # 因此回落记录值而不是静默丢弃 provenance。
    return spec.get("base_commit") or spec.get("verification_evidence", {}).get("source_commit")


# ------------------------------------------------------------------ 解析器

class _Budget(Exception):
    pass


def _with_alarm(sec, fn, *a):
    """在 wall-clock alarm 下运行 fn。某些数据集的 log_parser 正则回溯会灾难性爆炸，
    宁可给出部分判定也不要整个任务失败。"""
    try:
        import signal
    except ImportError:
        return fn(*a), False
    if not hasattr(signal, "SIGALRM"):
        return fn(*a), False

    def _fire(*_):
        raise _Budget()

    old = signal.signal(signal.SIGALRM, _fire)
    signal.alarm(sec)
    try:
        return fn(*a), False
    except _Budget:
        return None, True
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)


ns = {}
exec(spec["log_parser"], ns)
parser_timeout = False
n_rounds = 0

if "parser" not in ns:
    print("[grade] log_parser 未定义 parser()", file=sys.stderr)
    status = {}
else:
    chunks = re.split(r"===SWELIVE_ROUND \d+===", log)
    chunks = [c for c in chunks[1:] if c.strip()] if len(chunks) > 1 else [log]
    n_rounds = len(chunks)

    def _parse_rounds():
        """跨轮次 worst-first 聚合：曾失败即失败；仅跳过即跳过；否则通过。"""
        rank = {"fail": 3, "error": 3, "skip": 2, "skipped": 2}
        agg = {}
        for ch in chunks:
            for k, v in (ns["parser"](ch) or {}).items():
                sv = str(v).strip().lower()
                score = 3 if ("fail" in sv and "pass" not in sv) else rank.get(sv, 0)
                if k not in agg or score > agg[k][0]:
                    agg[k] = (score, v)
        return {k: v for k, (_, v) in agg.items()}

    status, parser_timeout = _with_alarm(PARSER_BUDGET, _parse_rounds)
    status = status or {}
    if parser_timeout:
        print("[grade] dataset log_parser 超过 %ds — 给出部分判定" % PARSER_BUDGET, file=sys.stderr)


def norm(v):
    """按上游 evaluation.py 的子串语义归一：
    pass 归 pass，fail 归 fail，SKIP/ERROR 归 other。"""
    v = str(v).strip().lower()
    if "pass" in v and "fail" in v:
        return "both"
    if "pass" in v:
        return "pass"
    if "fail" in v:
        return "fail"
    return "other"


norm_status = {k: norm(v) for k, v in status.items()}


# ------------------------------------------------------------------ 名称匹配
# 若被测日志来自 PowerShell 控制台且存在固定宽度换行，需要在此处做 unwrap。
# 若目标仓库日志是干净输出，可直接用精确匹配，删除下面 _derives/_first_artifact/resolve。

def _derives(clean, wrapped):
    i = j = 0
    n, m = len(clean), len(wrapped)
    while i < n and j < m:
        c = wrapped[j]
        if c == clean[i]:
            i += 1; j += 1
        elif c in "\r\n " or (i > 0 and c == clean[i - 1]):
            j += 1
        else:
            return False
    while j < m and (wrapped[j] in "\r\n " or (i > 0 and wrapped[j] == clean[i - 1])):
        j += 1
    return i == n and j == m


def _first_artifact(s):
    for i, c in enumerate(s):
        if c in "\r\n " or (i > 0 and c == s[i - 1]):
            return i
    return len(s)


import bisect
_parsed_names = sorted(norm_status)
_match_deadline = _t0 + GRADE_BUDGET
match_budget_hit = False


def resolve(req):
    """把 spec 里的 required 名字映射到日志中实际解析出的名字。
    先用精确匹配，再唯一后缀匹配，最后做 unwrap 前缀索引（避免 O(n²)）。"""
    global match_budget_hit
    if req in norm_status:
        return req
    suffix_hits = [name for name in _parsed_names
                   if name.endswith("::" + req) or name.endswith("/" + req)]
    if len(suffix_hits) == 1:
        return suffix_hits[0]
    bare = req.lstrip("\r\n ")
    k = _first_artifact(bare)
    if k >= len(bare):
        return None
    if time.time() > _match_deadline:
        match_budget_hit = True
        return None
    pref = bare[:k]
    n_bare = len(bare)
    lo = bisect.bisect_left(_parsed_names, pref)
    while lo < len(_parsed_names) and _parsed_names[lo].startswith(pref):
        cand = _parsed_names[lo]
        if len(cand) <= n_bare and _derives(cand, req):
            return cand
        lo += 1
    return None


unwrapped = 0


def classify(names):
    """success = 解析为 pass ∩ required；failure = 解析为 fail ∩ required。
    从未出现的 required 名字既不算 success 也不算 failure —— 它是 MISSING（→ INVALID）。"""
    global unwrapped
    ok, bad, other, miss = [], [], [], []
    for t in names:
        hit = resolve(t)
        if hit is None:
            miss.append(t)
            continue
        if hit != t:
            unwrapped += 1
        st = norm_status[hit]
        if st == "both":
            ok.append(t); bad.append(t)
        elif st == "pass":
            ok.append(t)
        elif st == "fail":
            bad.append(t)
        else:
            other.append(t)
    return sorted(ok), sorted(bad), sorted(other), sorted(miss)


# ------------------------------------------------------------------ 判定

f2p, p2p = spec["FAIL_TO_PASS"], spec["PASS_TO_PASS"]
f2p_ok, f2p_bad, f2p_other, f2p_miss = classify(f2p)
p2p_ok, p2p_bad, p2p_other, p2p_miss = classify(p2p)

f2p_all_pass = set(f2p).issubset(set(f2p_ok))
p2p_all_pass = set(p2p).issubset(set(p2p_ok))

candidate_failure_match = re.search(
    r"^===SWELIVE_CANDIDATE_FAILURE\s+([^=]+)===$", log, re.MULTILINE
)
candidate_failure = candidate_failure_match.group(1).strip() if candidate_failure_match else None

# 候选编译失败 / 新 API 无法 import —— 在环境预检通过后是**合法 0 分**。
# 缺工具、缺报告、patch 失败、解析失败仍然是 INVALID。
evidence_complete = (
    (bool(status) and not parser_timeout and not match_budget_hit)
    or bool(candidate_failure)
)
infrastructure_valid = bool(candidate_failure) or (
    evidence_complete and not (f2p_other or f2p_miss or p2p_other or p2p_miss)
)

run_evidence = {
    "generated_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "run_id": os.environ.get("AP_JOB_ID") or os.environ.get("SWELIVE_RUN_ID"),
    "phase": os.environ.get("SWELIVE_PHASE", "model"),
    "source_commit": _source_commit(),
    "image_digest": os.environ.get("SWELIVE_IMAGE_DIGEST"),
    "image_ref": os.environ.get("SWELIVE_IMAGE_REF") or spec.get("image_ref"),
    "log_sha256": _sha256(log_path),
    "spec_sha256": _sha256(SPEC_PATH),
    "test_patch_sha256": _sha256(os.path.join(TESTS, "test_patch.diff")),
}

report = {
    "instance_id": spec["instance_id"],
    "task_version": spec.get("task_version"),
    "resolved": (not candidate_failure) and infrastructure_valid
                and f2p_all_pass and p2p_all_pass and not f2p_bad and not p2p_bad,
    "FAIL_TO_PASS": {"success": f2p_ok, "failure": f2p_bad, "other": f2p_other, "missing": f2p_miss},
    "PASS_TO_PASS": {"success": p2p_ok, "failure": p2p_bad, "other": p2p_other, "missing": p2p_miss},
    "f2p_total": len(f2p), "p2p_total": len(p2p),
    "f2p_all_pass": f2p_all_pass, "p2p_all_pass": p2p_all_pass,
    "evidence_complete": evidence_complete,
    "infrastructure_valid": infrastructure_valid,
    "candidate_failure": candidate_failure,
    "parser_timeout": parser_timeout,
    "match_budget_hit": match_budget_hit,
    "rounds": n_rounds,
    "parsed_tests": len(norm_status),
    "unwrapped_names": unwrapped,
    "run_evidence": run_evidence,
    # 单次报告无法证明 3 base + 3 oracle；此字段仅说明平台是否提供了跨运行晋升校验所需字段。
    "promotion_evidence_fields_complete": all(
        run_evidence.get(name) for name in
        ("run_id", "source_commit", "image_digest", "log_sha256", "spec_sha256", "test_patch_sha256")
    ),
}

verifier_dir = os.path.join(logs_root, "verifier")
os.makedirs(verifier_dir, exist_ok=True)
with open(os.path.join(verifier_dir, "report.json"), "w", encoding="utf-8") as f:
    json.dump(report, f, indent=2, ensure_ascii=False)

# 缺失/跳过的 required 测试与解析失败是**无效评测证据**，不是合法的模型 0 分。
# 保留 report.json 供诊断，但**刻意不写 reward 产物**，使 Verifier 以基础设施故障退出。
if not infrastructure_valid:
    print("[grade] incomplete required-test evidence", file=sys.stderr)
    sys.exit(2)

score = 1.0 if report["resolved"] else 0.0
criterion = {
    "score": score,
    "criteria": {
        "name": "windows_bench_regression",
        "value": score,
        "raw": report,
        "weight": 1.0,
        "description": (
            "Candidate compilation or task test collection failed after the environment preflight."
            if candidate_failure else
            "All required FAIL_TO_PASS and PASS_TO_PASS tests were observed and passed."
        ),
    },
    "kind": "programmatic",
}
with open(os.path.join(verifier_dir, "reward.txt"), "w", encoding="utf-8") as f:
    f.write(format(score, ".12g"))
with open(os.path.join(verifier_dir, "reward.json"), "w", encoding="utf-8") as f:
    json.dump({"reward": score}, f, separators=(",", ":"))
with open(os.path.join(verifier_dir, "reward-details.json"), "w", encoding="utf-8") as f:
    json.dump({"reward": [criterion]}, f, indent=2, ensure_ascii=False)

print("[grade] parsed=%d unwrapped=%d F2P %d/%d fail=%d other=%d missing=%d "
      "P2P %d/%d fail=%d other=%d missing=%d resolved=%s" % (
          len(norm_status), unwrapped, len(f2p_ok), len(f2p), len(f2p_bad),
          len(f2p_other), len(f2p_miss), len(p2p_ok), len(p2p), len(p2p_bad),
          len(p2p_other), len(p2p_miss), report["resolved"]))
sys.exit(0 if report["resolved"] else 1)
