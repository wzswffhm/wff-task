"""217 加深（第三步补丁）：偏差 A 需同时放宽 manifest 的 FunctionsToExport。

原因：tests/run_tests.ps1 导入的是 WReparse.psd1（manifest）。manifest 的
FunctionsToExport 会过滤 psm1 的 Export-ModuleMember，只改 psm1 不产生可观测
偏差。契约 §2 要求「导出且仅导出六个函数」，因此把 manifest 一并放宽为 '*'。
"""
from __future__ import annotations

import sys
from pathlib import Path

TASK = Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-windows\wfflab__wreparse-217")
PSD1 = TASK / "environment/workspace/WReparse/WReparse.psd1"
failed = False


def patch(path: Path, old: str, new: str, label: str) -> None:
    global failed
    text = path.read_text(encoding="utf-8")
    n = text.count(old)
    if n != 1:
        print(f"!! {path.name}: {label} 命中 {n} 次（期望 1）")
        failed = True
        return
    path.write_text(text.replace(old, new), encoding="utf-8")
    print(f"ok {path.name}: {label}")


patch(PSD1,
      """    FunctionsToExport = @(
        'Get-WReparseReport'
        'ConvertTo-WReparseJson'
        'Get-WReparseSchemaVersion'
        'Test-WReparseWithinRoot'
        'Get-WReparseCanonicalPath'
        'Resolve-WReparseLinkTarget'
    )""",
      """    FunctionsToExport = '*'""",
      "偏差A(补): manifest FunctionsToExport 放宽为 '*'（契约 §2）")

print("\nRESULT:", "部分失败" if failed else "第三步补丁完成")
sys.exit(1 if failed else 0)
