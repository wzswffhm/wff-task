"""217 加深（第三步 / L3 -> L4）：向候选实现注入 4 处**新的**契约偏差。

设计依据（全部对应契约中**已声明**的条款，不新增题面未声明的要求）：
  偏差 A  §2   模块「导出且仅导出」六个函数        -> 改成 Export-ModuleMember -Function *
  偏差 B  §3.1 Target 是「目标串」（string）        -> 直接赋 provider 原始值（symlink 下是 string[]）
  偏差 C  §7   「未给 -Follow 时不得产生 cycle 与 broken_target」 -> 未跟随也解析目标
  偏差 D  §3.1 「InScope 仅 reparse 条目有意义；其余恒为 false」 -> 普通条目也计算 InScope

另有两处偏差在本轮之前已存在、本轮不改（它们由新增夹具变得更难）：
  §6.1/§6.2 候选不排序（Golden 用自实现的 culture-free 归并排序）
  §3       候选报告多出 GeneratedAt 字段
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


# ---------------------------------------------------------------- 偏差 A（§2）
# 「模块导出且仅导出契约 §2 列出的六个函数」
patch(WS / "WReparse.psm1",
      """Export-ModuleMember -Function @(
    'Get-WReparseReport'
    'ConvertTo-WReparseJson'
    'Get-WReparseSchemaVersion'
    'Test-WReparseWithinRoot'
    'Get-WReparseCanonicalPath'
    'Resolve-WReparseLinkTarget'
)""",
      """Export-ModuleMember -Function *""",
      "偏差A: 导出面由六个函数放宽为全部函数（契约 §2）")

# -------------------------------------------------------------- 偏差 B（§3.1）
# Target 字段类型是 string（「目标串」）；provider 对符号链接返回 string[]。
patch(WS / "Walker.ps1",
      "                -Target $rawTarget -ResolvedTarget $resolved -InScope $inScope `",
      "                -Target $rawTargetValue -ResolvedTarget $resolved -InScope $inScope `",
      "偏差B: Target 直接落 provider 原值（可能是 string[]，契约 §3.1）")

# ---------------------------------------------------------------- 偏差 C（§7）
# 「未给 -Follow 时不得产生 cycle 与 broken_target」：把目标存在性检查提到
# Follow 判定之前，使默认扫描也会记 broken_target。
patch(WS / "Walker.ps1",
      """            if (-not $State.Follow) {
                $State.Skipped++
                continue
            }
            if ($null -eq $resolved) {
                Add-WReparseError -State $State -RelativePath $relative -Code 'broken_target' `
                    -Message 'The reparse target could not be resolved.'
                continue
            }
            if (-not (Test-Path -LiteralPath $resolved)) {
                Add-WReparseError -State $State -RelativePath $relative -Code 'broken_target' `
                    -Message 'The reparse target does not exist.'
                continue
            }""",
      """            if ($null -eq $resolved) {
                Add-WReparseError -State $State -RelativePath $relative -Code 'broken_target' `
                    -Message 'The reparse target could not be resolved.'
                if (-not $State.Follow) { $State.Skipped++ }
                continue
            }
            if (-not (Test-Path -LiteralPath $resolved)) {
                Add-WReparseError -State $State -RelativePath $relative -Code 'broken_target' `
                    -Message 'The reparse target does not exist.'
                if (-not $State.Follow) { $State.Skipped++ }
                continue
            }
            if (-not $State.Follow) {
                $State.Skipped++
                continue
            }""",
      "偏差C: 默认扫描也会解析目标并记 broken_target（契约 §7）")

# -------------------------------------------------------------- 偏差 D（§3.1）
# 「InScope 仅 reparse 条目有意义；其余恒为 false」
patch(WS / "Walker.ps1",
      """        [void]$State.Records.Add((New-WReparseRecord -RelativePath $relative -Kind $kind `
            -Depth $Depth -Size $size))""",
      """        [void]$State.Records.Add((New-WReparseRecord -RelativePath $relative -Kind $kind `
            -InScope (Test-WReparseWithinRoot -Path $realChild -Root $State.Root) -Depth $Depth -Size $size))""",
      "偏差D: 普通条目也写入 InScope（契约 §3.1 要求恒为 false）")

# --------------------------------------------------------------- 自检与报告
print()
for label, path in (("候选 psm1", WS / "WReparse.psm1"), ("候选 Walker", WS / "Walker.ps1")):
    txt = path.read_text(encoding="utf-8")
    print(f"{label}: {len(txt)} 字符")

print("\nRESULT:", "部分失败" if failed else "第三步完成（4 处新偏差已注入候选）")
sys.exit(1 if failed else 0)
