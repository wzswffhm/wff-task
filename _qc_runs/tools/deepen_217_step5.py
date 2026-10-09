"""217 加深（第五步）：依据真机实测修正两处设计。

实测结论（Windows 11 / NTFS / Windows PowerShell 5.1）：
  1. provider 的 .Target 是 System.String[]，但 PowerShell 函数 return 会展开
     单元素数组，Windows 上重解析点只有一个目标，所以候选无论用
     $rawTarget 还是 $rawTargetValue 都得到 String -> 「Target 数组」偏差不可观测。
     处置：还原偏差 B；对应检查降级为 P2P（合法解在修复前后都必须通过）。
  2. 候选「完全不排序」时，NTFS 的枚举顺序恰好等于 Unicode 序（= ordinal），
     所以 culture 排序检查误判通过。处置：把偏差改成显式使用 Sort-Object，
     即 culture-aware 排序 —— 这才是有观测效果的缺陷。
"""
from __future__ import annotations

import sys
from pathlib import Path

TASK = Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-windows\wfflab__wreparse-217")
WS = TASK / "environment/workspace/WReparse"
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


# ------------------------------------------------- 还原偏差 B（不可观测，撤掉）
patch(WS / "Walker.ps1",
      "                -Target $rawTargetValue -ResolvedTarget $resolved -InScope $inScope `",
      "                -Target $rawTarget -ResolvedTarget $resolved -InScope $inScope `",
      "还原偏差B: Target 用已规范化的 $rawTarget（原偏差不可观测）")

# --------------------------------- 偏差 1': 候选改用 culture-aware 的 Sort-Object
# 契约 §6 要求「序数、忽略大小写」的键；Sort-Object 的默认字符串比较受宿主
# culture 影响，会把带变音符的名字按基字母排列，从而违反契约。
patch(WS / "Audit.ps1",
      """    $followMode = if ($Follow) { 'Always' } else { 'Never' }
    $walk = Invoke-WReparseWalk -Root $Root -FollowMode $followMode -MaxDepth $MaxDepth
    $records = @($walk.Records)
    $errors = @($walk.Errors)""",
      """    $followMode = if ($Follow) { 'Always' } else { 'Never' }
    $walk = Invoke-WReparseWalk -Root $Root -FollowMode $followMode -MaxDepth $MaxDepth
    $records = @($walk.Records | Sort-Object -Property RelativePath)
    $errors = @($walk.Errors | Sort-Object -Property RelativePath, Code)""",
      "偏差1': 候选改用 Sort-Object 排序（culture-aware，契约 §6.2）")

print("\nRESULT:", "部分失败" if failed else "第五步完成")
sys.exit(1 if failed else 0)
