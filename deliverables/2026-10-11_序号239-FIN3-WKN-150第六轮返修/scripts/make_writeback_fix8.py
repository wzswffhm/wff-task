# -*- coding: utf-8 -*-
"""由第五轮脚本派生第六轮 fix8 飞书回写脚本（改包名、版本校验并追加本轮新增自检项）。"""
from __future__ import annotations

import pathlib
import sys

sys.stdout.reconfigure(encoding="utf-8")

DEL = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\deliverables")
SRC = DEL / "2026-10-11_序号239-FIN3-WKN-150第五轮返修/scripts/feishu_writeback_fix7_150.py"
DST = DEL / "2026-10-11_序号239-FIN3-WKN-150第六轮返修/scripts/feishu_writeback_fix8_150.py"

OLD_CHECKS = '''        checks = {
            "version=1.0.7": b'version = "1.0.7"' in archive.read(f"{root}/FIN3-WKN-150/task.toml"),
            "summary mean gate": b'"mean": 0.' in archive.read(f"{root}/FIN3-WKN-150/跑分产物与轨迹/summary.json"),
            "four rewards": sum(name.endswith("/reward.json") for name in names) == 4,
            "no rejudge": not any("_rejudge" in name or "__pycache__" in name for name in names),
            "single second-level": all(name.split("/")[1] == "FIN3-WKN-150"
                                       for name in names if name.count("/") >= 1 and name.split("/")[1]),
        }'''

NEW_CHECKS = '''        rubric_all = archive.read(f"{root}/FIN3-WKN-150/tests/rubrics.toml").decode("utf-8")
        oracle_memo = archive.read(
            f"{root}/FIN3-WKN-150/跑分产物与轨迹/oracle/output/"
            "FIN3-WKN-150_PreIPO投资决策备忘录.md").decode("utf-8")
        checks = {
            "version=1.0.8": b'version = "1.0.8"' in archive.read(f"{root}/FIN3-WKN-150/task.toml"),
            "summary mean gate": b'"mean": 0.' in archive.read(f"{root}/FIN3-WKN-150/跑分产物与轨迹/summary.json"),
            "four rewards": sum(name.endswith("/reward.json") for name in names) == 4,
            "no rejudge": not any("_rejudge" in name or "__pycache__" in name for name in names),
            "single second-level": all(name.split("/")[1] == "FIN3-WKN-150"
                                       for name in names if name.count("/") >= 1 and name.split("/")[1]),
            "交付文档 at batch root": f"{root}/交付文档.md" in names,
            "scoring aggregation": 'aggregation = "weighted_mean"' in rubric_all,
            "oracle generation evidence": (
                f"{root}/FIN3-WKN-150/跑分产物与轨迹/oracle/轨迹/generation.log" in names
                and f"{root}/FIN3-WKN-150/跑分产物与轨迹/oracle/轨迹/generated_manifest.json" in names),
            "oracle memo no placeholder": "{med_pe" not in oracle_memo and "{fm(" not in oracle_memo,
            "oracle golden same-source": hashlib.sha256(oracle_memo.encode("utf-8")).hexdigest()
                == hashlib.sha256(archive.read(
                    f"{root}/FIN3-WKN-150/solution/golden_output/"
                    "FIN3-WKN-150_PreIPO投资决策备忘录.md").decode("utf-8").encode("utf-8")).hexdigest(),
        }'''


def main() -> int:
    text = SRC.read_text(encoding="utf-8")
    text = text.replace("第五轮 fix7 飞书附件回写", "第六轮 fix8 飞书附件回写")
    text = text.replace("fix7-150.zip", "fix8-150.zip")
    if OLD_CHECKS not in text:
        raise SystemExit("未找到待替换的 checks 区块")
    text = text.replace(OLD_CHECKS, NEW_CHECKS)
    if "import hashlib" not in text:
        text = text.replace("import json\n", "import hashlib\nimport json\n", 1)
    DST.write_text(text, encoding="utf-8", newline="\n")
    print(f"written {DST}")
    for token in ["fix8-150.zip", "hashlib", "交付文档 at batch root", "scoring aggregation",
                  "oracle generation evidence"]:
        print(f"  {token:28s} {token in text}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
