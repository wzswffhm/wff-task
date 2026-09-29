#!/usr/bin/env python3
"""
run_model_validation.py — Harbor Windows 多模型自动化验证

按《Windows 专项 Coding Bench 数据采购》(windwos-第二版) 第七章 / 第八章，
对题包执行多模型验证并计算区分度准入。

模型配置（默认）：
    Qwen3.8-Max-0902  3 次   主要难度模型        (aliyun MaaS, Anthropic 协议)
    Opus 5            3 次   主要难度模型        (blvr, Anthropic 协议)
    GLM-5.3          >=1 次  可运行性 + 基础质量
    Kimi K3          >=1 次  可运行性 + 基础质量

准入规则（满足任一）：
    条件 1: Opus.model_score_sum > Qwen.model_score_sum
    条件 2: 两者 model_score_sum == 0 且 Opus.testcase_pass_sum > Qwen.testcase_pass_sum

只统计 VALID 运行；INVALID 必须查明原因并补跑，不得计入难度统计。

用法：
    # 用内置默认模型配置（推荐）
    python run_model_validation.py --tasks <task_dir> --out <delivery-extras/tasks>

    # 覆盖凭据（或设置环境变量 HARBOR_WINDOWS_MODEL_ENDPOINTS / 见 models.json）
    python run_model_validation.py --tasks <task_dir> --out <out> --config models.default.json

    # 只跑 Qwen + Opus 各 1 次做连通性冒烟
    python run_model_validation.py --tasks <task_dir> --out <out> --smoke

    # 只计算区分度（不调模型，读已有 model_runs 结果）
    python run_model_validation.py --score-only --out <delivery-extras/tasks>

退出码：
    0  全部通过（区分度满足）
    1  存在题不满足区分度 / 存在 INVALID 未补跑
    2  参数、配置或凭据错误
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
import time
import traceback

# ------------------------------------------------------------------ 默认模型配置
# 注意：API Key 优先从环境变量读取；此处仅为便于本地跑通的默认值。
# 生产环境请用 HARBOR_WINDOWS_ENDPOINTS_JSON 指向不受版本管理的凭据文件。

DEFAULT_ENDPOINTS = [
    {
        "key": "qwen3.8-max",
        "label": "Qwen3.8-Max-0902",
        "dir": "qwen3.8-max-0902",
        "runs": 3,
        "role": "primary",
        "base_url": "https://llm-cz4pcezs463b102x.cn-beijing.maas.aliyuncs.com/apps/anthropic",
        "model": "qwen3.8-max",
        "api_key_env": "HARBOR_WINDOWS_ALIYUN_KEY",
        "api_key": "sk-ws-H.PIDYYYX.gJ1X.MEQCIAS8rCwaANl1voz83TDM6AHmQB_a433KQGaBlQdQnyYNAiAssJCXyeegO7ZSrpTZ4KfEjEkXVvGNW1v8UIyfSZ82qg",
        "auth": "x-api-key",
        "protocol": "anthropic",
    },
    {
        "key": "opus-5",
        "label": "Opus 5",
        "dir": "opus-5",
        "runs": 3,
        "role": "primary",
        "base_url": "https://api.blvr.top",
        "model": "claude-opus-5",
        "api_key_env": "HARBOR_WINDOWS_BLVR_KEY",
        "api_key": "sk-l8hraN17mCfgGZc2En6ecsHnQKYBRHMWZGMltWApY8KzRNoD",
        "auth": "x-api-key",
        "protocol": "anthropic",
    },
    {
        "key": "glm-5.3",
        "label": "GLM-5.3",
        "dir": "glm-5.3",
        "runs": 1,
        "role": "auxiliary",
        "base_url": "https://llm-cz4pcezs463b102x.cn-beijing.maas.aliyuncs.com/apps/anthropic",
        "model": "GLM-5.3",
        "api_key_env": "HARBOR_WINDOWS_ALIYUN_KEY",
        "api_key": "sk-ws-H.PIDYYYX.gJ1X.MEQCIAS8rCwaANl1voz83TDM6AHmQB_a433KQGaBlQdQnyYNAiAssJCXyeegO7ZSrpTZ4KfEjEkXVvGNW1v8UIyfSZ82qg",
        "auth": "x-api-key",
        "protocol": "anthropic",
    },
    {
        "key": "kimi-k3",
        "label": "Kimi K3",
        "dir": "kimi-k3",
        "runs": 1,
        "role": "auxiliary",
        "base_url": "https://llm-cz4pcezs463b102x.cn-beijing.maas.aliyuncs.com/apps/anthropic",
        "model": "Kimi K3",
        "api_key_env": "HARBOR_WINDOWS_ALIYUN_KEY",
        "api_key": "sk-ws-H.PIDYYYX.gJ1X.MEQCIAS8rCwaANl1voz83TDM6AHmQB_a433KQGaBlQdQnyYNAiAssJCXyeegO7ZSrpTZ4KfEjEkXVvGNW1v8UIyfSZ82qg",
        "auth": "x-api-key",
        "protocol": "anthropic",
    },
]

MAX_TOKENS = int(os.environ.get("HARBOR_WINDOWS_MAX_TOKENS", "8192"))
REQUEST_TIMEOUT = float(os.environ.get("HARBOR_WINDOWS_TIMEOUT_SEC", "600"))
MAX_RETRIES = int(os.environ.get("HARBOR_WINDOWS_MAX_RETRIES", "3"))

# ------------------------------------------------------------------ 严重性分类

INVALID_PATTERNS = [
    (("api-key is blocked", "invalidapikey", "invalid api key"), "credential_rejected", "凭据被服务端拒绝"),
    (("invalid token", "invalid_token"), "credential_rejected", "凭据无效"),
    (("rate limit", "429", "too many requests"), "rate_limited", "触发限流"),
    (("insufficient", "quota", "balance", "arrears"), "quota_exhausted", "额度不足"),
    (("401", "403"), "auth_failed", "鉴权失败"),
    (("timeout", "timed out"), "network_timeout", "网络超时"),
    (("connection", "getaddrinfo", "ssl", "proxy"), "network_error", "网络/代理错误"),
    (("model not found", "does not exist", "no such model", "not supported"), "model_unavailable", "模型不可用"),
]

CANDIDATE_FAILURE_PATTERNS = [
    ("overloaded", "model_overloaded"),
    ("context length", "context_overflow"),
]


def classify_failure(status_code, body_text):
    """返回 (kind, region, message)。
    kind: 'invalid' | 'candidate' | 'unknown'
    region: infrastructure / model_capability
    """
    low = (body_text or "").lower()
    for needles, kind, msg in INVALID_PATTERNS:
        for n in needles:
            if n in low:
                return "invalid", "infrastructure", f"{msg} ({n})"
    for n, kind in CANDIDATE_FAILURE_PATTERNS:
        if n in low:
            return "candidate", "model_capability", n
    if status_code and status_code >= 500:
        return "invalid", "infrastructure", f"upstream_5xx_{status_code}"
    if status_code == 429:
        return "invalid", "infrastructure", "rate_limited"
    return "invalid", "infrastructure", f"http_{status_code}"


# ------------------------------------------------------------------ HTTP 调用

def call_anthropic(base_url, api_key, model, prompt, auth="x-api-key"):
    """用 Anthropic Messages 协议调用，返回 (ok, status, text, meta)。"""
    try:
        import httpx
    except ImportError:
        return False, None, "httpx 未安装：请 pip install httpx", {}

    url = base_url.rstrip("/") + "/v1/messages"
    if auth == "authorization":
        headers = {"authorization": f"Bearer {api_key}"}
    else:
        headers = {"x-api-key": api_key}
    headers["anthropic-version"] = "2023-06-01"
    headers["content-type"] = "application/json"
    payload = {
        "model": model,
        "max_tokens": MAX_TOKENS,
        "messages": [{"role": "user", "content": prompt}],
    }

    last = None
    for attempt in range(1, MAX_RETRIES + 1):
        t0 = time.time()
        try:
            r = httpx.post(url, headers=headers, json=payload, timeout=REQUEST_TIMEOUT)
            elapsed = time.time() - t0
            if r.status_code == 200:
                try:
                    doc = r.json()
                except Exception:
                    return False, r.status_code, f"非 JSON 响应: {r.text[:300]}", {"elapsed": elapsed}
                text = "".join(
                    b.get("text", "") for b in (doc.get("content") or []) if b.get("type") == "text"
                )
                usage = doc.get("usage") or {}
                return True, 200, text, {
                    "elapsed": round(elapsed, 2),
                    "input_tokens": usage.get("input_tokens"),
                    "output_tokens": usage.get("output_tokens"),
                    "stop_reason": doc.get("stop_reason"),
                    "model_returned": doc.get("model"),
                }
            last = (r.status_code, r.text[:1000], elapsed)
            kind, _, _ = classify_failure(r.status_code, r.text)
            # 凭据/模型不可用类问题重试无意义
            if kind == "invalid" and any(s in (r.text or "").lower()
                                         for s in ("api-key is blocked", "invalid token",
                                                   "invalidapi key", "model not found")):
                break
        except Exception as e:
            last = (None, f"{type(e).__name__}: {e}", time.time() - t0)
        if attempt < MAX_RETRIES:
            time.sleep(min(2 ** attempt, 15))
    if last:
        return False, last[0], last[1], {"elapsed": round(last[2], 2), "attempts": MAX_RETRIES}
    return False, None, "unknown", {}


def get_api_key(ep):
    v = os.environ.get(ep.get("api_key_env", ""), "")
    return v or ep.get("api_key", "")


# ------------------------------------------------------------------ 题面读取

def load_instruction(task_dir):
    p = os.path.join(task_dir, "instruction.md")
    if not os.path.isfile(p):
        return None
    return open(p, encoding="utf-8", errors="replace").read()


def load_spec(task_dir):
    p = os.path.join(task_dir, "tests", "swelive_spec.json")
    if not os.path.isfile(p):
        return {}
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return {}


def discover_tasks(tasks_arg):
    """--tasks 可以是单个题目目录，也可以是包含多题的目录。"""
    if os.path.isfile(os.path.join(tasks_arg, "task.toml")):
        return [os.path.basename(os.path.abspath(tasks_arg))]
    if os.path.isdir(tasks_arg):
        out = [d for d in sorted(os.listdir(tasks_arg))
               if os.path.isdir(os.path.join(tasks_arg, d))
               and os.path.isfile(os.path.join(tasks_arg, d, "task.toml"))]
        return out
    return []


# ------------------------------------------------------------------ 结果读写

def run_dir(out_root, tid, ep_dir, n):
    return os.path.join(out_root, tid, "model_runs", ep_dir, f"run-{n}")


def write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")


def write_text(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def classify_run(validation_kind, meta):
    """把一次调用结果映射成 VALID / INVALID。"""
    if validation_kind == "invalid":
        return "INVALID"
    return "VALID"


# ------------------------------------------------------------------ 单次运行

def run_once(task_dir, tid, ep, n, out_root, prompt, dry_run=False):
    rd = run_dir(out_root, tid, ep["dir"], n)
    os.makedirs(rd, exist_ok=True)

    meta = {
        "task_id": tid,
        "model_label": ep["label"],
        "model_dir": ep["dir"],
        "model_identity": ep["model"],
        "role": ep["role"],
        "run_index": n,
        "base_url": ep["base_url"],
        "started_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }

    if dry_run:
        meta["status"] = "PENDING"
        meta["note"] = "dry-run：未实际调用模型"
        write_json(os.path.join(rd, "meta.json"), meta)
        return {"status": "PENDING", "meta": meta}

    ok, status, text, call_meta = call_anthropic(
        ep["base_url"], get_api_key(ep), ep["model"], prompt, ep.get("auth", "x-api-key")
    )
    meta["completed_at_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    meta.update(call_meta)

    if ok:
        meta["status"] = "VALID"
        meta["http_status"] = 200
        write_text(os.path.join(rd, "response.md"), text)
        # 尝试从响应中提取补丁（若模型给出了 diff 代码块）
        patch = extract_patch(text)
        if patch:
            write_text(os.path.join(rd, "patch.diff"), patch)
            meta["patch_extracted"] = True
        else:
            meta["patch_extracted"] = False
        # 无平台沙箱时无法真正执行测试，逐 testcase 结果标记 NOT_RUN
        spec = load_spec(task_dir)
        per_test = {}
        for t in spec.get("FAIL_TO_PASS", []):
            per_test[t] = "NOT_RUN"
        for t in spec.get("PASS_TO_PASS", []):
            per_test[t] = "NOT_RUN"
        write_json(os.path.join(rd, "per_testcase.json"), {
            "task_id": tid, "run_index": n,
            "_note": "未接平台沙箱，无法真实执行测试；分数需由平台 harness 回填",
            "results": per_test,
        })
        write_json(os.path.join(rd, "report.json"), {
            "task_id": tid, "run_index": n, "status": "VALID",
            "score": None, "model_score_sum": None,
            "_note": "需在平台跑完 F2P/P2P 后回填 score",
        })
    else:
        kind, region, msg = classify_failure(status, text)
        if not status and "httpx 未安装" in str(text):
            kind, region, msg = "invalid", "infrastructure", "httpx 未安装"
        meta["status"] = "INVALID" if kind == "invalid" else "VALID"
        meta["http_status"] = status
        meta["failure_kind"] = kind
        meta["attribution_region"] = region
        meta["failure_reason"] = msg
        meta["response_excerpt"] = (text or "")[:1000]
        meta["retest_required"] = (kind == "invalid")
        write_json(os.path.join(rd, "error.json"), meta)
        # 归因文档
        write_text(os.path.join(rd, "badcase_attribution.md"),
                   f"# 运行失败归因 — {tid} / {ep['label']} / run-{n}\n\n"
                   f"- HTTP 状态：{status}\n"
                   f"- 分类：**{kind}**\n"
                   f"- 归因域：**{region}**\n"
                   f"- 原因：{msg}\n"
                   f"- 是否需要补跑：{'是（INVALID 必须补跑）' if kind == 'invalid' else '否（按真实结果记录）'}\n\n"
                   f"## 响应片段\n\n```\n{(text or '')[:1500]}\n```\n\n"
                   f"> 归因原则：编译失败/超时/缺测试/解析错误只是现象，必须定位到 "
                   f"题面 / 测试 / 环境-平台 / 聚合器 / 证据完整性 / 模型能力 / Hack 的根因。\n")

    write_json(os.path.join(rd, "meta.json"), meta)
    return {"status": meta["status"], "meta": meta}


def extract_patch(text):
    """从模型回复中提取 ```diff 代码块。"""
    import re
    if not text:
        return None
    m = re.search(r"```(?:diff|patch)\s*\n(.*?)```", text, re.S)
    if m and ("---" in m.group(1) or "+++" in m.group(1) or "@@" in m.group(1)):
        return m.group(1)
    return None


# ------------------------------------------------------------------ 区分度计算

def score_task(out_root, tid, endpoints):
    """读取已有 model_runs 结果，计算 model_score_sum / testcase_pass_sum 与准入结论。"""
    result = {"task_id": tid, "models": {}, "validity": {}, "admission": None}
    for ep in endpoints:
        d = os.path.join(out_root, tid, "model_runs", ep["dir"])
        score_sum = 0
        pass_sum = 0
        valid = 0
        invalid = 0
        pending = 0
        scores = []
        for n in range(1, ep["runs"] + 1):
            meta_p = os.path.join(d, f"run-{n}", "meta.json")
            if not os.path.isfile(meta_p):
                pending += 1
                continue
            try:
                m = json.load(open(meta_p, encoding="utf-8"))
            except Exception:
                pending += 1
                continue
            st = m.get("status")
            if st == "VALID":
                valid += 1
                rep_p = os.path.join(d, f"run-{n}", "report.json")
                sc = None
                if os.path.isfile(rep_p):
                    try:
                        sc = json.load(open(rep_p, encoding="utf-8")).get("score")
                    except Exception:
                        sc = None
                scores.append(sc)
                if isinstance(sc, (int, float)):
                    score_sum += sc
                pt_p = os.path.join(d, f"run-{n}", "per_testcase.json")
                if os.path.isfile(pt_p):
                    try:
                        rs = json.load(open(pt_p, encoding="utf-8")).get("results") or {}
                        pass_sum += sum(1 for v in rs.values() if str(v).upper() == "PASS")
                    except Exception:
                        pass
            elif st == "INVALID":
                invalid += 1
            else:
                pending += 1
        result["models"][ep["key"]] = {
            "label": ep["label"],
            "runs_required": ep["runs"],
            "runs_valid": valid,
            "runs_invalid": invalid,
            "runs_pending": pending,
            "model_score_sum": score_sum,
            "testcase_pass_sum": pass_sum,
            "scores": scores,
            "scores_known": all(isinstance(s, (int, float)) for s in scores) and len(scores) == ep["runs"],
        }
        result["validity"][ep["key"]] = "READY" if (valid >= ep["runs"] and invalid == 0) else (
            "RETEST_REQUIRED" if invalid else "PENDING")

    q = result["models"].get("qwen3.8-max", {})
    o = result["models"].get("opus-5", {})
    adm = {"condition": None, "passed": None, "reason": None, "blocking": []}

    if q.get("runs_valid", 0) < 3 or o.get("runs_valid", 0) < 3:
        adm["reason"] = "主模型有效运行不足 3 次，暂不可判定"
        adm["blocking"] = ["insufficient_valid_runs"]
    elif result["validity"].get("qwen3.8-max") != "READY" or result["validity"].get("opus-5") != "READY":
        adm["reason"] = "存在 INVALID 运行未补跑"
        adm["blocking"] = ["invalid_runs_not_retested"]
    elif not (q.get("scores_known") and o.get("scores_known")):
        adm["reason"] = ("3 次响应均有效，但正式分数需由平台 harness 回填（尚未执行 F2P/P2P），"
                         "故区分度暂不可计算")
        adm["blocking"] = ["scores_not_filled"]
    else:
        qs, os_ = q["model_score_sum"], o["model_score_sum"]
        if os_ > qs:
            adm["condition"] = 1
            adm["passed"] = True
            adm["reason"] = f"Opus5.model_score_sum({os_}) > Qwen.model_score_sum({qs})"
        elif qs == 0 and os_ == 0:
            qp, op = q["testcase_pass_sum"], o["testcase_pass_sum"]
            if op > qp:
                adm["condition"] = 2
                adm["passed"] = True
                adm["reason"] = f"双 0 场景，Opus5.testcase_pass_sum({op}) > Qwen({qp})"
            else:
                adm["condition"] = 2
                adm["passed"] = False
                adm["reason"] = f"双 0 且 testcase 表现无严格区分（Opus {op} vs Qwen {qp}）"
        else:
            adm["passed"] = False
            adm["reason"] = f"两者正式分和相同且不全为 0（Opus {os_} vs Qwen {qs}）"

    for aux in ("glm-5.3", "kimi-k3"):
        a = result["models"].get(aux, {})
        if a.get("runs_valid", 0) < 1:
            adm.setdefault("blocking_aux", []).append(f"{aux} 无有效运行")
    result["admission"] = adm
    return result


def write_score_report(out_root, results, schema_ver="1.3"):
    today = datetime.date.today().isoformat()
    rows = ["task_id,model,model_identity,runs_total,runs_valid,runs_invalid,runs_pending,"
            "model_score_sum,testcase_pass_sum,validity,notes"]
    for r in results:
        for k, m in r["models"].items():
            rows.append(",".join(str(x) for x in [
                r["task_id"], m["label"], "", m["runs_required"], m["runs_valid"],
                m["runs_invalid"], m["runs_pending"], m["model_score_sum"],
                m["testcase_pass_sum"], r["validity"].get(k, ""),
                (r["admission"].get("reason") or "").replace(",", "；"),
            ]))
    write_text(os.path.join(out_root, "..", "model_summary.csv"), "\n".join(rows) + "\n")

    md = [f"# 多模型验证报告\n", f"生成时间：{today}", "",
          "## 1. 区分度准入汇总", "",
          "| task_id | Qwen score_sum | Opus score_sum | 满足条件 | 结论 |", "|---|---|---|---|---|"]
    for r in results:
        q = r["models"].get("qwen3.8-max", {})
        o = r["models"].get("opus-5", {})
        a = r["admission"]
        verdict = "PASS" if a.get("passed") else ("BLOCKED" if a.get("passed") is None else "FAIL")
        md.append(f"| {r['task_id']} | {q.get('model_score_sum')} | {o.get('model_score_sum')} | "
                  f"{a.get('condition') or '-'} | {verdict} — {a.get('reason')} |")

    md += ["", "## 2. 逐模型运行状态", "",
           "| task_id | 模型 | 要求 | VALID | INVALID | PENDING | 状态 |", "|---|---|---|---|---|---|---|"]
    for r in results:
        for k, m in r["models"].items():
            md.append(f"| {r['task_id']} | {m['label']} | {m['runs_required']} | {m['runs_valid']} | "
                      f"{m['runs_invalid']} | {m['runs_pending']} | {r['validity'].get(k,'')} |")

    md += ["", "## 3. 准入规则", "",
           "```",
           "条件 1: Opus5.model_score_sum > Qwen.model_score_sum",
           "条件 2: 两者 model_score_sum == 0 且 Opus5.testcase_pass_sum > Qwen.testcase_pass_sum",
           "```", "",
           "> 只统计 VALID 运行；INVALID 必须查明原因并补跑，不得计入难度统计。",
           "> 模型门槛不能覆盖数据质量门槛：题面歧义、错误测试、环境故障、答案泄漏、Windows 价值不足时仍不得验收。",
           "> 不得为制造分差而增加题面未声明要求或冷门陷阱。", ""]
    write_text(os.path.join(out_root, "..", "model_validation_report.md"), "\n".join(md) + "\n")

    summary = {"generated_at": today, "harbor_schema": schema_ver, "tasks": results}
    write_json(os.path.join(out_root, "..", "model_validation_summary.json"), summary)


# ------------------------------------------------------------------ 主流程

def main():
    ap = argparse.ArgumentParser(description="Harbor Windows 多模型自动化验证")
    ap.add_argument("--tasks", help="题目目录（单题）或包含多题的目录")
    ap.add_argument("--out", required=True, help="delivery-extras/tasks 输出目录")
    ap.add_argument("--config", help="模型配置 JSON（默认用内置）")
    ap.add_argument("--smoke", action="store_true", help="冒烟：每模型只跑 1 次")
    ap.add_argument("--dry-run", action="store_true", help="不实际调用，只建骨架")
    ap.add_argument("--score-only", action="store_true", help="只计算区分度，不调模型")
    ap.add_argument("--prompt-file", help="自定义题面 prompt 模板（{instruction} 占位）")
    args = ap.parse_args()

    endpoints = DEFAULT_ENDPOINTS
    env_cfg = os.environ.get("HARBOR_WINDOWS_ENDPOINTS_JSON")
    cfg_path = args.config or env_cfg
    if cfg_path:
        if not os.path.isfile(cfg_path):
            print(f"错误: 配置文件不存在 {cfg_path}", file=sys.stderr)
            return 2
        try:
            cfg = json.load(open(cfg_path, encoding="utf-8"))
            # 支持裸数组 或 {"endpoints": [...]} 两种形态
            endpoints = cfg.get("endpoints", cfg) if isinstance(cfg, dict) else cfg
            if not isinstance(endpoints, list) or not endpoints:
                raise ValueError("配置中未找到非空 endpoints 列表")
        except Exception as e:
            print(f"错误: 配置解析失败 {e}", file=sys.stderr)
            return 2

    if args.smoke:
        endpoints = [dict(e, runs=1) for e in endpoints]

    out_root = os.path.abspath(args.out)
    os.makedirs(out_root, exist_ok=True)

    if args.score_only:
        tids = discover_tasks(args.tasks) if args.tasks else [
            d for d in sorted(os.listdir(out_root)) if os.path.isdir(os.path.join(out_root, d))]
        if not tids:
            print("错误: 未找到题目", file=sys.stderr)
            return 2
        results = [score_task(out_root, t, endpoints) for t in tids]
        write_score_report(out_root, results)
        print(f"区分度报告已生成（{len(tids)} 题）")
        bad, pending, ok = [], [], []
        for r in results:
            a = r["admission"]
            print(f"  {r['task_id']}: {a.get('passed')} — {a.get('reason')}")
            if a.get("passed") is True:
                ok.append(r["task_id"])
            elif a.get("passed") is False:
                bad.append(r["task_id"])
            else:
                pending.append(r["task_id"])
        print(f"\n汇总：通过={len(ok)} 不通过={len(bad)} 待定={len(pending)}")
        # 只有明确"不通过"才是验收失败；"待定"（分数未回填/有效运行不足）单独提示，不算失败
        return 1 if bad else 0

    if not args.tasks:
        print("错误: 需指定 --tasks（除非用 --score-only）", file=sys.stderr)
        return 2

    tids = discover_tasks(args.tasks)
    if not tids:
        print(f"错误: {args.tasks} 下未找到含 task.toml 的题目", file=sys.stderr)
        return 2

    # 凭据预检（提前暴露 Key 问题，避免跑一半失败）
    print("=" * 66)
    print("凭据预检")
    print("=" * 66)
    preflight_failed = {}
    for ep in endpoints:
        if args.dry_run:
            print(f"  [dry-run] {ep['label']}: 跳过预检")
            continue
        key = get_api_key(ep)
        if not key:
            print(f"  [MISSING] {ep['label']}: 未提供 API Key（env {ep.get('api_key_env')}）")
            preflight_failed[ep["key"]] = "no_key"
            continue
        ok, status, text, meta = call_anthropic(
            ep["base_url"], key, ep["model"], "Reply with exactly: OK",
            ep.get("auth", "x-api-key"))
        if ok:
            print(f"  [OK]      {ep['label']} ({ep['model']}) -> {text.strip()[:40]!r}")
        else:
            kind, region, msg = classify_failure(status, text)
            print(f"  [FAIL]    {ep['label']} ({ep['model']}) -> HTTP {status} | {msg}")
            print(f"            响应: {str(text)[:160]}")
            if kind == "invalid":
                preflight_failed[ep["key"]] = msg

    if preflight_failed:
        print("")
        print("!! 预检未通过模型: " + ", ".join(f"{k}({v})" for k, v in preflight_failed.items()))
        print("!! 这些模型的所有运行会记为 INVALID（不计入难度统计）。")
        print("!! 若确认是凭据/网络问题，修好后重跑即可；本轮仍继续生成记录。")
        print("")

    tpl = "请依据以下题面完成任务，并以 ```diff 代码块形式给出你的补丁。\n\n---\n{instruction}\n"
    if args.prompt_file and os.path.isfile(args.prompt_file):
        tpl = open(args.prompt_file, encoding="utf-8").read()

    total_ok = 0
    total_invalid = 0

    for tid in tids:
        task_dir = os.path.join(os.path.abspath(args.tasks), tid) \
            if not os.path.isfile(os.path.join(args.tasks, "task.toml")) \
            else os.path.abspath(args.tasks)
        instr = load_instruction(task_dir) or "(未找到 instruction.md)"
        prompt = tpl.replace("{instruction}", instr)
        print("=" * 66)
        print(f"题目 {tid}（{len(endpoints)} 个模型）")
        print("=" * 66)
        for ep in endpoints:
            print(f"  · {ep['label']}  x{ep['runs']}  [{ep['role']}]")
            for n in range(1, ep["runs"] + 1):
                try:
                    res = run_once(task_dir, tid, ep, n, out_root, prompt, dry_run=args.dry_run)
                except Exception:
                    res = {"status": "INVALID", "meta": {}}
                    print(f"    run-{n}: EXCEPTION\n{traceback.format_exc()}")
                st = res["status"]
                if st == "VALID":
                    total_ok += 1
                    print(f"    run-{n}: VALID")
                elif st == "INVALID":
                    total_invalid += 1
                    m = res.get("meta", {})
                    print(f"    run-{n}: INVALID — {m.get('failure_reason', 'unknown')}")
                else:
                    print(f"    run-{n}: {st}")

    results = [score_task(out_root, t, endpoints) for t in tids]
    write_score_report(out_root, results)

    print("=" * 66)
    print(f"完成：VALID={total_ok}  INVALID={total_invalid}")
    bad = []
    for r in results:
        a = r["admission"]
        print(f"  {r['task_id']}: 准入={a.get('passed')} — {a.get('reason')}")
        if a.get("passed") is False:
            bad.append(r["task_id"])
    print("")
    print("提醒：")
    print("  - 正式分需由平台 harness 执行 F2P/P2P 后回填各 run 的 report.json")
    print("  - 回填后再跑 --score-only 计算区分度")
    print("  - INVALID 运行必须查明原因并补跑")

    if total_invalid or bad:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
