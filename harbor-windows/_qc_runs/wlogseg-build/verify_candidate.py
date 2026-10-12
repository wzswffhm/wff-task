"""把一个候选实现放进隐藏语义套件跑一遍，逐项打印 PASS/FAIL。

用法：
    python verify_candidate.py <candidate_pkg_dir> <label>

其中 <candidate_pkg_dir> 是包含 __init__.py 的包目录（例如参考实现目录）。
本脚本只在题包构建期运行，不属于交付物。
"""

import os
import shutil
import subprocess
import sys

BUILD = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.join(os.path.dirname(os.path.dirname(BUILD)), "wfflab__wlogseg-218-v1.0.0-delivery")
PYLIBS = os.path.join(BUILD, "pylibs")


def main():
    if len(sys.argv) < 3:
        print("usage: verify_candidate.py <candidate_pkg_dir> <label>")
        return 2
    candidate = os.path.abspath(sys.argv[1])
    label = sys.argv[2]

    run_root = os.path.join(BUILD, "run-" + label)
    if os.path.isdir(run_root):
        shutil.rmtree(run_root)
    os.makedirs(run_root)
    shutil.copytree(candidate, os.path.join(run_root, "wlogseg"))
    shutil.copytree(
        os.path.join(PKG, "environment", "workspace", "assets"),
        os.path.join(run_root, "assets"),
    )
    tests_dir = os.path.join(run_root, "tests")
    os.makedirs(tests_dir)
    shutil.copy2(
        os.path.join(PKG, "verifier", "tests", "test_wlogseg_semantics.py"),
        tests_dir,
    )

    env = dict(os.environ)
    env["PYTHONPATH"] = PYLIBS + os.pathsep + run_root
    env["PYTHONDONTWRITEBYTECODE"] = "1"

    proc = subprocess.run(
        [sys.executable, "-m", "pytest", tests_dir, "-v", "--tb=line",
         "-p", "no:cacheprovider", "--no-header"],
        env=env, capture_output=True, text=True,
    )
    out = proc.stdout
    passed, failed = [], []
    for line in out.splitlines():
        if "::" not in line:
            continue
        name = line.split("::")[-1].split()[0]
        if " PASSED" in line:
            passed.append(name)
        elif " FAILED" in line or " ERROR" in line:
            failed.append(name)
    print(f"=== {label}: {len(passed)} passed, {len(failed)} failed ===")
    for name in failed:
        print("  FAIL " + name)
    tail = [ln for ln in out.splitlines() if ln.startswith("=") and ("passed" in ln or "failed" in ln)]
    for ln in tail:
        print("  " + ln)
    if proc.returncode not in (0, 1):
        print(proc.stderr[-1500:])
    return 0


if __name__ == "__main__":
    sys.exit(main())
