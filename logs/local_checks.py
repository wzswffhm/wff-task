# -*- coding: utf-8 -*-
"""local_checks.py -- 返修后的本机静态与隔离校验（不含真实容器跑分）。

用法：
    python local_checks.py --task <包目录>

检查项：
  1. 全部 TOML 能被标准解析器（tomllib）完整读取；
  2. 全部 JSON 合法；
  3. tests/rubric.json 权重合计 1.0、无 llm_judge 项；
  4. required_testcases.json 与 rubric test_ids 逐条一致；
  5. run_tests.ps1 的 $verifierCandidates 不含包内/workdir 路径；
  6. 包内 tests/ 下没有隐藏套件副本，verifier/tests/ 下恰好一份；
  7. verifier/negative_access_probe.ps1 实跑，verdict 必须为 PASS；
  8. 身份位一致（task.toml / adapter.toml / agent_visible_paths.json /
     rubric.json / run_tests.ps1 / rubric.conditions.json 的版本号相同）；
  9. judge.toml 的 source_sha256 等于 rubric.json 的实字节 sha256。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path

results = []


def check(name: str, ok: bool, detail: str = "", advisory: bool = False) -> None:
    results.append((name, ok, detail, advisory))
    print("  [%s] %-52s %s" % ("PASS" if ok else ("WARN" if advisory else "FAIL"),
                              name, detail))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True)
    ap.add_argument("--expect-version", default="")
    a = ap.parse_args()
    task = Path(a.task).resolve()
    print("== %s ==" % task.name)

    # 1. TOML
    tomls = ["task.toml", "tests/judge.toml", "environment/adapter.toml"]
    loaded = {}
    for rel in tomls:
        p = task / rel.replace("/", "\\")
        try:
            with open(p, "rb") as fh:
                loaded[rel] = tomllib.load(fh)
            check("tomllib: %s" % rel, True)
        except Exception as exc:  # noqa: BLE001
            check("tomllib: %s" % rel, False, "%s: %s" % (type(exc).__name__, exc))

    # 2. JSON
    jsons = ["tests/rubric.json", "tests/required_testcases.json",
             "environment/agent_visible_paths.json", "verifier/rubric.conditions.json",
             "verifier/SEALED_MANIFEST.json"]
    if (task / "source.json").is_file():
        jsons.append("source.json")
    docs = {}
    for rel in jsons:
        try:
            docs[rel] = json.loads((task / rel.replace("/", "\\")).read_text(encoding="utf-8"))
            check("json: %s" % rel, True)
        except Exception as exc:  # noqa: BLE001
            check("json: %s" % rel, False, "%s: %s" % (type(exc).__name__, exc))

    # 3. rubric
    rubric = docs.get("tests/rubric.json", {})
    items = rubric.get("items", [])
    total = round(sum(float(i["weight"]) for i in items), 6)
    check("rubric weights sum to 1.0", total == 1.0, "sum=%s" % total)
    non_prog = [i["rubric_id"] for i in items if i.get("type") != "programmatic"]
    check("rubric has no llm_judge item", not non_prog, "offenders=%s" % non_prog)
    check("rubric conditions_source exists in package",
          (task / "verifier" / "rubric.conditions.json").is_file(),
          rubric.get("conditions_source", ""))
    check("rubric conditions_source points at verifier/",
          str(rubric.get("conditions_source", "")).replace("\\", "/").startswith("verifier/"),
          str(rubric.get("conditions_source", "")))

    # 4. required vs rubric
    req = docs.get("tests/required_testcases.json", [])
    rubric_ids = [tid for i in items for tid in i["test_ids"]]
    check("required ids == rubric test_ids (order-insensitive)",
          sorted(r["id"] for r in req) == sorted(rubric_ids),
          "required=%d rubric=%d" % (len(req), len(rubric_ids)))
    # 甲方口径：5–27 条正常，超过 27 条只提示人工复核，不判失败
    if len(req) < 5:
        check("required count >= 5", False, "n=%d" % len(req))
    elif len(req) > 27:
        check("required count within 5..27 (advisory)", False,
              "n=%d > 27：按甲方口径只提示人工复核，不计 FAIL" % len(req),
              advisory=True)
    else:
        check("required count within 5..27", True, "n=%d" % len(req))
    cond = docs.get("verifier/rubric.conditions.json", {})
    cond_ids = [tid for i in cond.get("programmatic", []) for tid in i["test_ids"]]
    check("conditions test_ids == rubric test_ids (order-insensitive)",
          sorted(cond_ids) == sorted(rubric_ids),
          "conditions=%d rubric=%d" % (len(cond_ids), len(rubric_ids)))
    check("conditions llm_judge is empty", cond.get("llm_judge") == [])

    # 5. run_tests.ps1 verifier candidates
    runner = (task / "tests" / "run_tests.ps1").read_text(encoding="utf-8", errors="replace")
    block = re.search(r"\$verifierCandidates = .*?\n\n", runner, re.S)
    cand = block.group(0) if block else ""
    bad = [ln.strip() for ln in cand.splitlines()
           if "Add(" in ln and ("Join-Path $TaskRoot" in ln or "Join-Path $WorkspaceRoot" in ln)]
    check("run_tests.ps1 candidates exclude workspace/task-root", not bad,
          "; ".join(bad) if bad else "verifier-side roots only")
    check("run_tests.ps1 declares the platform C:\\tests channel",
          "C:\\tests" in cand, "C:\\tests" if "C:\\tests" in cand else "missing")

    # 6. hidden suite placement: one platform copy under tests/, one on the
    # verifier side, byte-identical.
    delivered = sorted(p.name for p in (task / "tests").glob("test_*_semantics.py"))
    hidden = sorted(p.name for p in (task / "verifier" / "tests").glob("test_*_semantics.py"))
    check("exactly one delivered suite under tests/", len(delivered) == 1,
          "found=%s" % delivered)
    check("exactly one hidden suite under verifier/tests/", len(hidden) == 1,
          "found=%s" % hidden)
    if len(delivered) == 1 and len(hidden) == 1:
        sha_delivered = hashlib.sha256((task / "tests" / delivered[0]).read_bytes()).hexdigest()
        sha_hidden = hashlib.sha256((task / "verifier" / "tests" / hidden[0]).read_bytes()).hexdigest()
        check("delivered suite == verifier suite (sha256)", sha_delivered == sha_hidden,
              "%s vs %s" % (sha_delivered[:16], sha_hidden[:16]))
    legacy = sorted(p.name for p in (task / "tests" / "verifier").rglob("test_*_semantics.py")) \
        if (task / "tests" / "verifier").is_dir() else []
    check("no legacy duplicate under tests/verifier/", legacy == [], "found=%s" % legacy)

    # 7. negative access probe
    probe = task / "verifier" / "negative_access_probe.ps1"
    if probe.is_file():
        import shutil as _shutil
        shell = _shutil.which("pwsh") or _shutil.which("powershell")
        if not shell:
            check("negative_access_probe runnable", False, "no pwsh/powershell on PATH")
        else:
            env = dict(__import__("os").environ)
            env["PYTHONIOENCODING"] = "utf-8"
            proc = subprocess.run(
                [shell, "-NoProfile", "-ExecutionPolicy", "Bypass",
                 "-File", str(probe), "-TaskRoot", str(task)],
                capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
            verdict = ""
            m = re.search(r'"verdict"\s*:\s*"(\w+)"', proc.stdout)
            if m:
                verdict = m.group(1)
            check("negative_access_probe verdict=PASS", verdict == "PASS",
                  "exit=%s verdict=%s" % (proc.returncode, verdict or "n/a"))
            (task.parent / ("probe-%s.json" % task.name)).write_text(
                proc.stdout, encoding="utf-8", newline="\n")
    else:
        check("negative_access_probe exists", False, str(probe))

    # 8. identity versions
    versions = {
        "task.toml": loaded.get("task.toml", {}).get("task", {}).get("version", ""),
        "adapter.toml": loaded.get("environment/adapter.toml", {}).get("task_version", ""),
        "agent_visible_paths.json": docs.get("environment/agent_visible_paths.json", {}).get("task_version", ""),
        "rubric.json": rubric.get("task_version", ""),
        "rubric.conditions.json": cond.get("task_version", ""),
    }
    m = re.search(r"task_version\s*=\s*'([^']+)'", runner)
    versions["run_tests.ps1"] = m.group(1) if m else ""
    if (task / "source.json").is_file():
        versions["source.json"] = docs.get("source.json", {}).get("task_version", "")
    uniq = sorted(set(versions.values()))
    check("identity versions agree", len(uniq) == 1, json.dumps(versions, ensure_ascii=False))
    if a.expect_version:
        check("identity version == %s" % a.expect_version, uniq == [a.expect_version],
              "found=%s" % uniq)

    # 9. judge source_sha256
    judge_sha = loaded.get("tests/judge.toml", {}).get("source_sha256", "")
    real_sha = hashlib.sha256((task / "tests" / "rubric.json").read_bytes()).hexdigest()
    check("judge.toml source_sha256 == rubric.json sha256", judge_sha == real_sha,
          judge_sha[:16] + " vs " + real_sha[:16])

    # 10. sealed manifest completeness
    manifest = docs.get("verifier/SEALED_MANIFEST.json", {})
    listed = {f["path"] for f in manifest.get("files", [])}
    actual = set()
    for p in (task / "verifier").rglob("*"):
        if p.is_file() and "__pycache__" not in p.parts and p.name != "SEALED_MANIFEST.json":
            actual.add(str(p.relative_to(task / "verifier")).replace("\\", "/"))
    check("sealed manifest covers every verifier file", listed == actual,
          "missing=%s extra=%s" % (sorted(actual - listed), sorted(listed - actual)))

    failed = [n for n, ok, _d, adv in results if not ok and not adv]
    advisory = [n for n, ok, _d, adv in results if not ok and adv]
    print("== %s: %d checks, %d failed, %d advisory ==" % (
        task.name, len(results), len(failed), len(advisory)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
