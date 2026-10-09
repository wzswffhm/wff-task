"""217 加深（第六步）：修正偏差 1' 的 Errors 排序键。

第五步把 Errors 写成 Sort-Object -Property RelativePath, Code，这恰好等价于
契约 §6.3 要求的键（先 RelativePath 再 Code），导致 F2P「error-list-is-stably-sorted」
意外通过、失去初始失败性。

改为只按 Code 排序：看起来「排序过了」，实际键错误 —— 违反契约 §6.3，
且比「完全不排序」更隐蔽。题面（契约 §6.3）已声明正确键，故不越界。
"""
from __future__ import annotations

import sys
from pathlib import Path

AUDIT = Path(
    r"C:\Users\Administrator\Desktop\wff-task\harbor-windows\wfflab__wreparse-217"
    r"\environment\workspace\WReparse\Audit.ps1"
)

old = "    $errors = @($walk.Errors | Sort-Object -Property RelativePath, Code)"
new = "    $errors = @($walk.Errors | Sort-Object -Property Code)"

text = AUDIT.read_text(encoding="utf-8")
n = text.count(old)
if n != 1:
    print(f"!! Audit.ps1: 命中 {n} 次（期望 1）")
    sys.exit(1)
AUDIT.write_text(text.replace(old, new), encoding="utf-8")
print("ok Audit.ps1: 偏差1'' 的 Errors 排序键改为仅 Code（违反契约 §6.3）")

print()
print("当前候选 Audit.ps1 的排序行：")
for line in AUDIT.read_text(encoding="utf-8").splitlines():
    if "Sort-Object" in line:
        print("   ", line.strip())
print("\nRESULT: 第六步完成")
