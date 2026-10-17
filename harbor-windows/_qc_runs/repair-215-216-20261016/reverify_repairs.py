# -*- coding: utf-8 -*-
"""按飞书返修原因逐条复验 215 / 216（纯本地，不启容器）。

对应关系：
  返修第 1 条（Task 校验值与运行记录一致）→ 需要 jobs/，本轮标记 DEFERRED
  返修第 2 条（候选与隐藏测试同进程、权限与评分端未分离）
      → 复验 ACL 受限 + 受信通道 + 交叉校验 + 读写被拒反例
  返修第 3 条（基础设施故障被当普通失败）→ 复验 setup error / 空收集 → INVALID 且分数为空
  返修第 4 条（断言没验到题面要求）
      → 215 复验“实测 8192、候选报 8193”被抓住
      → 216 复验“regions 有背衬项、file_backed_regions=[]”被抓住
"""
from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task")
HW = ROOT / "harbor-windows"
BASE = HW / "_qc_runs" / "repair-215-216-20261016"
VENV = HW / "_qc_runs" / "wsparse215-fix" / "venv" / "Scripts"
PY = r"C:\Users\Administrator\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
PS = r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
WORK = BASE / "reverify"

PKGS = {
    "215": {
        "pkg": "wfflab__wsparse-215-v1.0.1-delivery",
        "ws": "wsparse", "mod": "wsparse",
        "suite": "test_wsparse_semantics.py",
        "oracle_rel": "solution/reference/wsparse",
        "oracle_cases": 20,
        "nop_f2p_fail": 10, "nop_p2p_fail": 0,
        "wrong_case": "allocated-ranges-are-the-real-extents",
    },
    "216": {
        "pkg": "wfflab__wvas-216-v1.0.1-delivery",
        "ws": "wvas", "mod": "wvas",
        "suite": "test_wvas_semantics.py",
        "oracle_rel": "solution/reference/wvas",
        "oracle_cases": 16,
        "nop_f2p_fail": 9, "nop_p2p_fail": 0,
        "wrong_case": "file-backed-regions-are-a-subset",
    },
}


def env() -> dict:
    e = dict(os.environ)
    e["PATH"] = str(VENV) + os.pathsep + e.get("PATH", "")
    e["PYTHONUTF8"] = "1"
    e["PYTHONIOENCODING"] = "utf-8"
    return e


def run_tests(pkg_dir: pathlib.Path, ws: pathlib.Path, verifier: pathlib.Path, out: pathlib.Path) -> tuple[int, dict]:
    out.mkdir(parents=True, exist_ok=True)
    cmd = [PS, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(pkg_dir / "tests" / "run_tests.ps1"),
           "-WorkspaceRoot", str(ws), "-ChecksPath", str(out / "results" / "checks.json"),
           "-TaskRoot", str(pkg_dir), "-VerifierRoot", str(verifier)]
    proc = subprocess.run(cmd, env=env(), capture_output=True, text=True)
    (out / "run.log").write_text((proc.stdout or "") + (proc.stderr or ""), encoding="utf-8", errors="replace")
    checks = {}
    cp = out / "results" / "checks.json"
    if cp.is_file():
        checks = json.loads(cp.read_text(encoding="utf-8-sig"))
    return proc.returncode, checks


def summarize(pkg_dir: pathlib.Path, checks: dict) -> dict:
    out = {}
    rows = checks.get("checks") or []
    for r in rows:
        out[r["test_id"]] = r["status"]
    iso = checks.get("isolation") or {}
    return {"statuses": out, "isolation": iso}


def main() -> int:
    if WORK.exists():
        shutil.rmtree(WORK, ignore_errors=True)
    WORK.mkdir(parents=True, exist_ok=True)
    report: dict = {}

    for tag, meta in PKGS.items():
        pkg_dir = HW / meta["pkg"]
        base_ws = pkg_dir / "environment" / "workspace"
        oracle_ws = WORK / tag / "oracle-ws"
        wrong_ws = WORK / tag / "wrong-ws"
        oracle_ws.parent.mkdir(parents=True, exist_ok=True)

        # 参考实现工作区
        shutil.copytree(base_ws, oracle_ws)
        shutil.rmtree(oracle_ws / meta["ws"], ignore_errors=True)
        shutil.copytree(pkg_dir / meta["oracle_rel"], oracle_ws / meta["ws"])

        # 错误实现工作区（返修第 4 条的点名场景）
        shutil.copytree(oracle_ws, wrong_ws)
        if tag == "215":
            f = wrong_ws / "wsparse" / "ranges.py"
            t = f.read_text(encoding="utf-8")
            t = t.replace("        return ranges",
                          "        # PROBE: 每个区间多报 1 字节（实测 8192 -> 报 8193）\n"
                          "        return [(o, l + 1) for o, l in ranges]")
            f.write_text(t, encoding="utf-8")
        else:
            f = wrong_ws / "wvas" / "vas.py"
            t = f.read_text(encoding="utf-8")
            marker = "def file_backed_regions(pid):"
            head, _, rest = t.partition(marker)
            body_end = rest.find("\ndef ")
            body = "\n    # PROBE: 谎报空列表，模拟“背衬项漏返回”\n    regions(pid)\n    return []\n"
            t = head + marker + body + (rest[body_end:] if body_end != -1 else "")
            f.write_text(t, encoding="utf-8")

        tag_rep: dict = {}
        for label, ws in (("oracle", oracle_ws), ("nop", base_ws), ("wrong", wrong_ws)):
            rc, checks = run_tests(pkg_dir, ws, pkg_dir / "verifier", WORK / tag / label)
            s = summarize(pkg_dir, checks)
            st = s["statuses"]
            entry = {
                "exit": rc,
                "pass": sum(1 for v in st.values() if v == "PASS"),
                "fail": sum(1 for v in st.values() if v == "FAIL"),
                "invalid": sum(1 for v in st.values() if v == "INVALID"),
                "isolation_enforced": s["isolation"].get("enforced"),
                "trusted_cases": s["isolation"].get("trusted_cases"),
                "failing": sorted(k for k, v in st.items() if v != "PASS"),
            }
            tag_rep[label] = entry
            print(f"[{tag}] {label:<7} exit={rc} PASS={entry['pass']} FAIL={entry['fail']} "
                  f"INVALID={entry['invalid']} isolation={entry['isolation_enforced']} "
                  f"trusted={entry['trusted_cases']}")

        # 返修第 3 条：套件一个 case 都收集不到 → INVALID 且分数为空
        empty_ver = WORK / tag / "empty-verifier" / "tests"
        empty_ver.mkdir(parents=True, exist_ok=True)
        (empty_ver / meta["suite"]).write_text("# intentionally empty\n", encoding="utf-8")
        rc, checks = run_tests(pkg_dir, oracle_ws, WORK / tag / "empty-verifier", WORK / tag / "invalid")
        agg = pkg_dir / "tests" / "aggregate_results.ps1"
        args = [PS, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(agg),
                "-ChecksPath", str(WORK / tag / "invalid" / "results" / "checks.json"),
                "-OutputPath", str(WORK / tag / "invalid" / "results" / "result.json"),
                "-TaskRoot", str(pkg_dir)]
        if (pkg_dir / "tests" / "required_testcases.json").is_file():
            args += ["-RequiredPath", str(pkg_dir / "tests" / "required_testcases.json")]
        else:
            args += ["-RubricPath", str(pkg_dir / "tests" / "rubric.json")]
        proc2 = subprocess.run(args, env=env(), capture_output=True, text=True)
        res_path = WORK / tag / "invalid" / "results" / "result.json"
        result = json.loads(res_path.read_text(encoding="utf-8-sig")) if res_path.is_file() else {}
        tag_rep["invalid_probe"] = {
            "run_exit": rc, "agg_exit": proc2.returncode,
            "run_validity": result.get("run_validity"),
            "formal_score": result.get("formal_score", "MISSING"),
            "report_status": (result.get("test") or {}).get("report", {}).get("status"),
            "report_score": (result.get("test") or {}).get("report", {}).get("score", "MISSING"),
        }
        print(f"[{tag}] 空收集探针   run_exit={rc} agg_exit={proc2.returncode} "
              f"validity={tag_rep['invalid_probe']['run_validity']} "
              f"formal_score={tag_rep['invalid_probe']['formal_score']}")

        report[tag] = tag_rep

    (BASE / "reverify.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                                        encoding="utf-8")
    print("\nwritten:", BASE / "reverify.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
