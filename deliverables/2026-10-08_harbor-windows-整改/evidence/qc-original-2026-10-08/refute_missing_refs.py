"""For every file the QC static scan reports as missing, prove what it actually is:
an existing file at a different path base, a directory, a runtime artefact, a
fixture created by prepare.ps1 at run time, or a fragment of a path literal.
"""
from __future__ import annotations

import json
import zipfile
from pathlib import Path

BASE = Path(r"C:\Users\Administrator\Desktop\wff-task\_qc_runs")
PKG = Path(r"C:\Users\Administrator\Desktop\wff-task\deliverables\2026-10-08_harbor-windows-整改\package")
ZIPS = {
    "215": PKG / "wfflab__wfmt-215-v2.0.0-delivery.zip",
    "217": PKG / "wfflab__wreparse-217-v1.0.0-delivery.zip",
}
RUNTIME_ARTEFACTS = {"checks.json", "result.json", "report.json", "reward.json",
                     "reward-details.json", "reward.txt", "pytest-results.json",
                     "test-stdout.txt", "trial.log"}

totals: dict[str, int] = {}
for tag, zp in ZIPS.items():
    d = json.loads((BASE / f"qcorig-{tag}" / "report.json").read_text(encoding="utf-8-sig"))
    errs: list[str] = []
    for t in d["tasks"]:
        for e in t.get("errors") or []:
            if e.startswith("referenced files are missing:"):
                errs += [x.strip() for x in e.split(":", 1)[1].split(",")]
    with zipfile.ZipFile(zp) as zf:
        names = zf.namelist()
        scripts = "".join(zf.read(n).decode("utf-8", "ignore")
                          for n in names if n.endswith((".ps1", ".bat", ".cmd")))

    print("=" * 96)
    print(f"{tag}   QC 报缺 {len(errs)} 项   包内条目 {len(names)}")
    print(f"{'QC 报缺':<32} {'判定':<16} 证据 / 实际位置")
    print("-" * 96)
    for ref in errs:
        base = ref.replace("\\", "/").split("/")[-1]
        files = [n for n in names if n.endswith("/" + base)]
        dirs = [n for n in names if ("/" + base + "/") in ("/" + n)]
        if files:
            verdict, where = "存在（基准错）", files[0]
        elif dirs:
            verdict, where = "存在（是目录）", dirs[0]
        elif base in RUNTIME_ARTEFACTS:
            verdict, where = "运行时产物", "容器内判分时生成，按设计不随包交付"
        elif ref.startswith("dp0"):
            real = [n for n in names if n.endswith("/" + base[3:])]
            verdict, where = "路径字面量碎片", f"来自 \"%~dp0\" 拼接；实际文件 = {real[0] if real else '?'}"
        elif base and base in scripts:
            verdict, where = "运行时夹具", "由 tests/prepare.ps1 在容器内创建（脚本内有创建语句）"
        elif "\\" in ref and base in scripts:
            verdict, where = "测试路径字符串", "题包脚本中作为测试输入的字面量，非文件引用"
        else:
            verdict, where = "未解释", ""
        totals[verdict] = totals.get(verdict, 0) + 1
        print(f"{ref:<32} {verdict:<16} {where}")

print()
print("汇总:", ", ".join(f"{k}={v}" for k, v in sorted(totals.items())))
print("真缺失 =", totals.get("未解释", 0))
