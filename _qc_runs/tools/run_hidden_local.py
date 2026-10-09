# -*- coding: utf-8 -*-
"""隐藏语义套件本地试跑：stage workspace + hidden test → pytest。

用法：
  python run_hidden_local.py gold      # 参考解（应 18/18 全过）
  python run_hidden_local.py candidate # 候选（应 F2P 全挂、P2P 全过）
  python run_hidden_local.py qwen <dir> # 某轮模型产出的 workspace
"""
from __future__ import annotations

import pathlib
import shutil
import subprocess
import sys
import tempfile

WS = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task")
TASK = WS / "harbor-windows" / "wfflab__wchunk-216"
HIDDEN = TASK / "tests" / "hidden" / "test_wchunk_semantics.py"
PY = r"C:\Program Files\Python39\python.exe"

# 与 tests/run_tests.ps1 同口径的 slug 映射（用于打印分组结果）
F2P = {
    "test_sample_verifies", "test_sample_roundtrip_byte_identical",
    "test_sample_records_match_expected", "test_empty_sample_roundtrip",
    "test_record_alignment_is_eight_bytes", "test_crc_matches_standard_check_value",
    "test_tampered_content_is_rejected", "test_checksum_covers_header_and_records",
    "test_truncated_container_reports_truncated", "test_truncated_stream_reports_truncated",
}


def main() -> int:
    mode = sys.argv[1]
    if mode == "gold":
        src = TASK / "solution" / "reference"
    elif mode == "candidate":
        src = TASK / "environment" / "workspace"
    elif mode == "qwen":
        src = pathlib.Path(sys.argv[2]).resolve()
    else:
        raise SystemExit("mode must be gold|candidate|qwen")

    stage = pathlib.Path(tempfile.mkdtemp(prefix="wchunk-hidden-"))
    try:
        if mode == "gold":
            # 参考解只提供包代码；assets/ 与可见测试取自 workspace（与
            # run_tests.ps1 的暂存口径一致：workspace 全量 + 被测包替换）
            shutil.copytree(TASK / "environment" / "workspace", stage / "workspace",
                            dirs_exist_ok=True)
            if (stage / "workspace" / "wchunk").exists():
                shutil.rmtree(stage / "workspace" / "wchunk")
            shutil.copytree(src / "wchunk", stage / "workspace" / "wchunk")
        else:
            shutil.copytree(src, stage / "workspace", dirs_exist_ok=True)
        # run_tests.ps1 的做法：workspace 内容 + hidden 套件放进 tests/
        (stage / "workspace" / "tests").mkdir(parents=True, exist_ok=True)
        shutil.copy2(HIDDEN, stage / "workspace" / "tests" / "test_wchunk_semantics.py")
        (stage / "workspace" / "conftest.py").write_text(
            "import pathlib, sys\n"
            "_root = str(pathlib.Path(__file__).resolve().parent)\n"
            "if _root not in sys.path:\n"
            "    sys.path.insert(0, _root)\n",
            encoding="utf-8",
        )
        proc = subprocess.run(
            [PY, "-m", "pytest", "-rA", "--tb=short", "-p", "no:cacheprovider",
             "-v", "tests/test_wchunk_semantics.py"],
            cwd=stage / "workspace", text=True, encoding="utf-8", errors="replace",
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        )
        print(proc.stdout)

        # 从 -v 输出解析 `::test_name PASSED/FAILED`
        outcomes: dict[str, str] = {}
        for line in proc.stdout.splitlines():
            if "::" not in line or "PASSED" not in line and "FAILED" not in line and "ERROR" not in line:
                continue
            fn = line.split("::")[-1].split()[0]
            if "PASSED" in line:
                outcomes[fn] = "passed"
            elif "FAILED" in line:
                outcomes[fn] = "failed"
            else:
                outcomes[fn] = "error"

        f2p_fail = [f for f in F2P if outcomes.get(f) != "passed"]
        p2p = [k for k in outcomes if k not in F2P]
        p2p_fail = [k for k in p2p if outcomes[k] != "passed"]
        print(f"=== {mode} ===")
        print(f"total={len(outcomes)} passed={sum(1 for v in outcomes.values() if v == 'passed')}")
        print(f"F2P fail ({len(f2p_fail)}/10): {sorted(f2p_fail)}")
        print(f"P2P fail ({len(p2p_fail)}/{len(p2p)}): {sorted(p2p_fail)}")
        return 0
    finally:
        shutil.rmtree(stage, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
