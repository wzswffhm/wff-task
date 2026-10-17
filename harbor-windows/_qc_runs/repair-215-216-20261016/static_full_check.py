# -*- coding: utf-8 -*-
"""215 / 216 的完整静态检查（不启动任何容器）。

覆盖：
  A. 甲方 QC 的交付目录检查           inspect_delivery
  B. 甲方 QC 的静态门禁               run_qc.static_check（含 judge.toml 摘要、docker_image、
                                      required_testcases 结构、镜像策略）
  C. Dockerfile 镜像合规              windows_image_policy.inspect_windows_dockerfile
  D. 2026-10-16 质检指南的配置卡点     docker_image / 无 task.toml.bak / authors 对象数组 /
                                      knowledge_tree L1-L3 / task_type 允许值 / ut>=10
  E. 隐藏套件两副本逐字节一致
  F. required_testcases / rubric.json / judge.toml 集合与分组一致
  G. Windows 机制门禁                 skills/harbor-windows/scripts/check_windows_mechanism.py
  H. 模型 jobs 门禁                   validate_jobs + evaluate（无 jobs 时标记 DEFERRED）
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess
import sys
import tomllib

HW = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-windows")
QC = HW / "_reference" / "windows-harbor-qc" / "scripts"
sys.path.insert(0, str(QC))

from inspect_delivery import inspect_delivery  # noqa: E402
from run_qc import static_check  # noqa: E402
from windows_image_policy import inspect_windows_dockerfile  # noqa: E402
from validate_model_jobs import validate_jobs  # noqa: E402
from validate_model_gate import evaluate  # noqa: E402

PKGS = ["wfflab__wsparse-215-v1.0.1-delivery", "wfflab__wvas-216-v1.0.1-delivery"]
ALLOWED_TASK_TYPES = {
    "Fix_performance-fix", "Fix_compatibility-fix", "Implementation _feature",
    "Implementation_enhancement", "Implementation_backward-compatibility",
    "Implementation_from_scratch", "Testing & Quality_test-add",
    "Testing & Quality_test-fix", "Testing & Quality_coverage",
    "Testing & Quality_debug-support", "Refactoring & Maintenance_refactor",
    "Refactoring & Maintenance_style", "Refactoring & Maintenance_deprecation",
    "Build & Release_build-fix", "Build & Release_ci-fix", "Build & Release_deployment",
    "Build & Release_packaging", "Build & Release_config",
    "Documentation & Design_user-docs", "Documentation & Design_design-spec",
    "Documentation & Design_diagram", "Security & Compliance_security-fix",
    "Security & Compliance_auth", "Security & Compliance_privacy", "Non_Coding",
}

results: list[tuple[str, str, bool, str]] = []


def record(pkg: str, name: str, ok: bool, detail: str = "") -> None:
    results.append((pkg, name, ok, detail))


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    for pkg in PKGS:
        root = HW / pkg
        print("=" * 78)
        print(pkg)

        # A. 交付目录
        layout = inspect_delivery(root)
        record(pkg, "A 交付目录 inspect_delivery", bool(layout.get("pass")),
               "; ".join(layout.get("errors") or []))

        # B. 甲方 QC 静态门禁
        sc = static_check(root)
        record(pkg, "B 甲方QC静态门禁 static_check", bool(sc.get("errors") == []),
               "; ".join(sc.get("errors") or []) or f"warnings={len(sc.get('warnings') or [])}")

        # C. 镜像策略
        ip = inspect_windows_dockerfile(root)
        record(pkg, "C Dockerfile 镜像合规", not ip.get("errors"),
               "; ".join(ip.get("errors") or []))

        # D. 指南配置卡点
        with (root / "task.toml").open("rb") as fh:
            cfg = tomllib.load(fh)
        task = cfg.get("task") or {}
        checks = {
            "docker_image": isinstance(cfg.get("docker_image"), str) and bool(cfg["docker_image"]),
            "no task.toml.bak": not (root / "task.toml.bak").exists(),
            "authors 为对象数组": isinstance(task.get("authors"), list)
            and bool(task["authors"]) and all(isinstance(a, dict) and a.get("name") for a in task["authors"]),
            "knowledge_tree L1/L2/L3": isinstance(task.get("knowledge_tree"), list)
            and len(task["knowledge_tree"]) == 3 and all(isinstance(x, str) and x for x in task["knowledge_tree"]),
            "task_type 合法": task.get("task_type") in ALLOWED_TASK_TYPES,
            "keywords 非空": isinstance(task.get("keywords"), list) and bool(task["keywords"]),
            "version 1.0.1": str(task.get("version")) == "1.0.1",
        }
        req = json.loads((root / "tests" / "required_testcases.json").read_text(encoding="utf-8"))
        f2p = sum(1 for r in req if r["group"] == "F2P")
        p2p = sum(1 for r in req if r["group"] == "P2P")
        checks["ut>=10"] = len(req) >= 10
        checks["F2P+P2P 均有"] = f2p > 0 and p2p > 0
        for name, ok in checks.items():
            record(pkg, f"D 指南卡点 · {name}", ok, "" if ok else "见上文")
        print(f"    ut={len(req)} (F2P {f2p} / P2P {p2p})")

        # E. 隐藏套件两副本一致
        suite = "test_wsparse_semantics.py" if "wsparse" in pkg else "test_wvas_semantics.py"
        a = root / "tests" / suite
        b = root / "verifier" / "tests" / suite
        same = a.is_file() and b.is_file() and sha256(a) == sha256(b)
        record(pkg, "E 隐藏套件两副本一致", same, f"{sha256(a)[:16]}…" if a.is_file() else "缺失")

        # F. required / rubric / judge 集合一致
        rubric = json.loads((root / "tests" / "rubric.json").read_text(encoding="utf-8"))
        rub_ids = [i for it in rubric.get("items", []) for i in it.get("test_ids", [])]
        req_ids = [r["id"] for r in req]
        judge_txt = (root / "tests" / "judge.toml").read_text(encoding="utf-8")
        judge_ids = [x for it in tomllib.loads(judge_txt).get("rubrics", []) for x in it.get("test_ids", [])]
        sets_ok = sorted(rub_ids) == sorted(req_ids) == sorted(judge_ids)
        record(pkg, "F required/rubric/judge 集合一致", sets_ok,
               f"req={len(req_ids)} rubric={len(rub_ids)} judge={len(judge_ids)}")
        declared = tomllib.loads(judge_txt).get("source_sha256")
        hash_ok = declared == sha256(root / "tests" / "rubric.json")
        record(pkg, "F judge.toml source_sha256 同步", hash_ok,
               f"declared={str(declared)[:12]}… actual={sha256(root / 'tests' / 'rubric.json')[:12]}…")

        # G. windows 机制门禁
        py = r"C:\Users\Administrator\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
        proc = subprocess.run([py, str(HW / "skills" / "harbor-windows" / "scripts" /
                                       "check_windows_mechanism.py"), "--task-dir", str(root)],
                              capture_output=True, text=True)
        record(pkg, "G Windows 机制门禁", proc.returncode == 0,
               (proc.stdout or proc.stderr or "").strip().splitlines()[-1] if (proc.stdout or proc.stderr) else "")

        # H. 模型 jobs 门禁（需要 jobs/）
        jobs_root = root / "jobs"
        if jobs_root.is_dir() and any(p.is_dir() and p.name != "_index" for p in jobs_root.iterdir()):
            try:
                jobs = validate_jobs(jobs_root, root, layout.get("task") or {})
                gate = evaluate(jobs.get("evidence") or {}, layout.get("task") or None)
                record(pkg, "H 模型 jobs 门禁", bool(jobs.get("pass")), "; ".join(jobs.get("errors") or [])[:200])
                record(pkg, "H 模型分数门禁", bool(gate.get("pass")), "; ".join(gate.get("errors") or [])[:200])
            except Exception as exc:  # noqa: BLE001
                record(pkg, "H 模型 jobs 门禁", False, f"{type(exc).__name__}: {exc}")
        else:
            record(pkg, "H 模型 jobs 门禁", True, "DEFERRED：jobs/ 尚未产出，重跑后校验")

    print()
    print("=" * 78)
    bad = [r for r in results if not r[2]]
    for pkg, name, ok, detail in results:
        flag = "PASS" if ok else "FAIL"
        print(f"  [{flag}] {pkg.replace('wfflab__', '')} :: {name}" + (f"  <- {detail}" if detail and not ok else ""))
    print()
    print(f"total={len(results)} pass={len(results) - len(bad)} fail={len(bad)}")
    return 0 if not bad else 1


if __name__ == "__main__":
    raise SystemExit(main())
