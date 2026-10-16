"""汇总各包 jobs 记录：F2P 在空跑基线的表现、对照齐全性、模型身份、无效运行。

只读，不修改任何文件。
"""
import json
import os
import sys

HW = r"C:\Users\Administrator\Desktop\wff-task\harbor-windows"
PACKAGES = [
    "wfflab__wsparse-215-v1.0.0-delivery",
    "wfflab__wvas-216-v1.0.0-delivery",
    "wfflab__wspawn-218-v1.0.0-delivery",
    "wfflab__wcancel-219-v1.0.0-delivery",
    "wfflab__wciocp-220-v1.0.0-delivery",
    "wfflab__wtoken-221-v1.0.0-delivery",
]
OUT = os.path.join(HW, "_qc_runs", "feishu-consistency-20261016-r2", "jobs-summary.json")


def load_json(path):
    try:
        with open(path, encoding="utf-8-sig") as fh:
            return json.load(fh)
    except Exception:
        return None


def job_cases(job_dir):
    """返回 (逐 case {test_id: passed}, run_validity, formal_score, source)。"""
    for rel in (r"verifier\report.json", r"result.json", r"verifier\result.json"):
        p = os.path.join(job_dir, rel)
        if not os.path.exists(p):
            continue
        doc = load_json(p)
        if not isinstance(doc, dict):
            continue
        cases = doc.get("cases")
        if isinstance(cases, list) and cases:
            out = {}
            for c in cases:
                if isinstance(c, dict) and "test_id" in c:
                    out[c["test_id"]] = bool(c.get("passed"))
            return out, doc.get("run_validity"), doc.get("formal_score"), rel
        # Harbor job result 形态：test.report.score
        test = doc.get("test")
        if isinstance(test, dict) and isinstance(test.get("report"), dict):
            rep = test["report"]
            return {}, rep.get("status"), rep.get("score"), rel
    return {}, None, None, None


def main():
    report = {}
    for pkg in PACKAGES:
        root = os.path.join(HW, pkg)
        jobs = os.path.join(root, "jobs")
        entry = {"jobs_dir": os.path.isdir(jobs)}
        req_path = os.path.join(root, "tests", "required_testcases.json")
        req = load_json(req_path) or []
        f2p = [r["id"] for r in req if str(r.get("group", "")).upper() == "F2P"]
        p2p = [r["id"] for r in req if str(r.get("group", "")).upper() == "P2P"]
        entry["required_counts"] = {"F2P": len(f2p), "P2P": len(p2p), "total": len(req)}
        if not entry["jobs_dir"]:
            report[pkg] = entry
            continue

        names = sorted(os.listdir(jobs))
        jobs_info = {}
        for name in names:
            jd = os.path.join(jobs, name)
            if not os.path.isdir(jd) or name == "_index":
                continue
            cases, validity, score, src = job_cases(jd)
            cfg = load_json(os.path.join(jd, "config.json")) or {}
            agent = cfg.get("agent") if isinstance(cfg.get("agent"), dict) else {}
            model = None
            for key in ("model", "model_name", "name"):
                if agent.get(key):
                    model = agent.get(key)
                    break
            jobs_info[name] = {
                "cases_passed": sum(1 for v in cases.values() if v),
                "cases_total": len(cases),
                "f2p_pass": sorted(k for k in f2p if cases.get(k)),
                "f2p_fail": sorted(k for k in f2p if k in cases and not cases.get(k)),
                "f2p_missing": sorted(k for k in f2p if k not in cases),
                "p2p_fail": sorted(k for k in p2p if k in cases and not cases.get(k)),
                "p2p_missing": sorted(k for k in p2p if k not in cases),
                "run_validity": validity,
                "formal_score": score,
                "source": src,
                "agent": agent,
            }
        entry["jobs"] = jobs_info
        inv = os.path.join(jobs, "invalid-slots.json")
        if os.path.exists(inv):
            entry["invalid_slots"] = load_json(inv)
        entry["config"] = load_json(os.path.join(jobs, "config.json"))
        report[pkg] = entry

    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)

    # 控制台摘要
    lines = []
    for pkg, e in report.items():
        lines.append("==== %s  required=%s" % (pkg, e.get("required_counts")))
        if not e.get("jobs_dir"):
            lines.append("   (no jobs/)")
            continue
        for name in sorted(e.get("jobs", {})):
            j = e["jobs"][name]
            lines.append("   %-15s cases=%2d/%-2d validity=%s score=%s agent=%s" % (
                name, j["cases_passed"], j["cases_total"], j["run_validity"],
                j["formal_score"], json.dumps(j["agent"], ensure_ascii=False)))
            if name.startswith("ctl-nop") and (j["f2p_pass"] or j["f2p_missing"]):
                lines.append("       F2P passed in nop: %s" % (j["f2p_pass"] or "-"))
                if j["f2p_missing"]:
                    lines.append("       F2P missing: %s" % j["f2p_missing"])
        if e.get("invalid_slots"):
            lines.append("   invalid-slots.json: %s" % json.dumps(e["invalid_slots"], ensure_ascii=False)[:400])
    text = "\n".join(lines)
    print(text)
    with open(os.path.join(os.path.dirname(OUT), "jobs-summary.txt"), "w", encoding="utf-8") as fh:
        fh.write(text + "\n")


if __name__ == "__main__":
    main()
