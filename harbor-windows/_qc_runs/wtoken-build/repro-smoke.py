"""Reproduce exactly what the hidden suite's smoke-suite test does."""

import os
import subprocess
import sys

root = r"C:\staged-sim"
smoke = os.path.join(root, "tests", "test_wtoken_basic.py")

print("root exists       :", os.path.isdir(root))
print("smoke exists      :", os.path.isfile(smoke))
print("sys.executable    :", sys.executable)

env = dict(os.environ)
env["PYTHONPATH"] = root + os.pathsep + env.get("PYTHONPATH", "")
print("PYTHONPATH        :", env["PYTHONPATH"])

proc = subprocess.run(
    [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", smoke],
    cwd=root, capture_output=True, text=True, env=env,
)
print("returncode        :", proc.returncode)
print("---- stdout ----")
print(proc.stdout[-4000:])
print("---- stderr ----")
print(proc.stderr[-4000:])

print("=== also try with a conftest present ===")
conftest = os.path.join(root, "conftest.py")
with open(conftest, "w", encoding="utf-8") as handle:
    handle.write(
        "import pathlib\n"
        "import sys\n"
        "\n"
        "_root = str(pathlib.Path(__file__).resolve().parent)\n"
        "if _root not in sys.path:\n"
        "    sys.path.insert(0, _root)\n"
    )
proc2 = subprocess.run(
    [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", smoke],
    cwd=root, capture_output=True, text=True, env=env,
)
print("returncode        :", proc2.returncode)
print("---- stdout ----")
print(proc2.stdout[-4000:])
print("---- stderr ----")
print(proc2.stderr[-4000:])
print("REPRO_DONE")
