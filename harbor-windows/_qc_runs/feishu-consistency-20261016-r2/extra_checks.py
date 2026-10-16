"""补充检查：nop 基线逐 case、invalid-slots、失败证据结构、模型身份一致性。"""
import json
import os

HW = r"C:\Users\Administrator\Desktop\wff-task\harbor-windows"
R2 = os.path.join(HW, "_qc_runs", "feishu-consistency-20261016-r2")

with open(os.path.join(R2, "jobs-summary.json"), encoding="utf-8") as fh:
    S = json.load(fh)

print("=== 1) ctl-nop / ctl-oracle 逐 case 违背情况（F2P 在基线通过 / P2P 在基线失败）===")
for pkg, e in S.items():
    if not e.get("jobs_dir"):
        print("%-32s (no jobs)" % pkg)
        continue
    for name, j in sorted(e.get("jobs", {}).items()):
        if not (name.startswith("ctl-nop") or name.startswith("ctl-oracle")):
            continue
        flag = []
        if j["f2p_pass"]:
            flag.append("F2P在基线通过=%s" % j["f2p_pass"])
        if j["p2p_fail"]:
            flag.append("P2P在基线失败=%s" % j["p2p_fail"])
        if j["f2p_missing"] or j["p2p_missing"]:
            flag.append("缺cases=f2p%s/p2p%s" % (j["f2p_missing"], j["p2p_missing"]))
        print("  %-28s %-14s %s" % (pkg, name, "; ".join(flag) if flag else "-"))

print()
print("=== 2) model 轮失败明细（哪个 case 挂）===")
for pkg, e in S.items():
    if not e.get("jobs_dir"):
        continue
    for name, j in sorted(e.get("jobs", {}).items()):
        if not name.startswith("model-"):
            continue
        fails = sorted(set(j["f2p_fail"]) | set(j["p2p_fail"]))
        print("  %-28s %-14s cases=%2d/%-2d score=%s fail=%s" % (
            pkg, name, j["cases_passed"], j["cases_total"], j["formal_score"], fails or "-"))

print()
print("=== 3) invalid-slots.json 内容 ===")
for pkg, e in S.items():
    if e.get("invalid_slots"):
        print("--- %s" % pkg)
        print(json.dumps(e["invalid_slots"], ensure_ascii=False, indent=1)[:2500])

print()
print("=== 4) 模型身份（每个包的 opus / qwen 声明）===")
for pkg, e in S.items():
    if not e.get("jobs_dir"):
        continue
    o = e["jobs"].get("model-opus-1", {}).get("agent", {})
    q = e["jobs"].get("model-qwen-1", {}).get("agent", {})
    print("  %-32s opus=%s | qwen=%s" % (pkg, o.get("model_name"), q.get("model_name")))
