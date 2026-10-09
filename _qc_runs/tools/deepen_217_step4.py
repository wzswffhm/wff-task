"""217 加深（第四步）：新增夹具 + 6 条新契约一致性检查。

新增检查全部对应 REPARSE-CONTRACT.md / instruction.md 中**已声明**的条款：

  1 sorting-is-culture-independent            §6.1/§6.2 排序主键为序数、忽略大小写，
                                                        不得使用受 culture 影响的排序
  2 module-exports-exactly-six-functions      §2 导出且仅导出六个函数
  3 target-is-serialised-as-string            §3.1 Target 是「目标串」（string）
  4 report-has-exactly-contract-fields        §3 报告字段为 SchemaVersion/Root/Records/Errors/Stats
  5 no-follow-produces-no-cycle-or-broken-target §7 未给 -Follow 时不得产生 cycle 与 broken_target
  6 inscope-is-false-for-non-reparse-entries  §3.1 InScope 仅 reparse 条目有意义，其余恒为 false

夹具新增 3 个普通文件（Z / Ä / ö 前缀名），其 ordinal 顺序与 culture 顺序相反。
文件名用字符码构造，避免脚本编码影响字面量。
"""
from __future__ import annotations

import sys
from pathlib import Path

TASK = Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-windows\wfflab__wreparse-217")
PREP = TASK / "tests/prepare.ps1"
RUN = TASK / "tests/run_tests.ps1"
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


# ------------------------------------------------------------------- 夹具新增
patch(PREP,
      "Set-Content -LiteralPath (Join-Path $scanRoot 'plain.txt') -Value 'plain' -NoNewline -Encoding ASCII\n",
      "Set-Content -LiteralPath (Join-Path $scanRoot 'plain.txt') -Value 'plain' -NoNewline -Encoding ASCII\n"
      "\n"
      "# Names whose ordinal ordering differs from their culture-aware ordering.\n"
      "# The contract fixes the sort key to ordinal-ignore-case, so a host whose\n"
      "# culture collates by base letter would order these differently. The names\n"
      "# are built from code points so that the fixture never depends on the\n"
      "# encoding of this script.\n"
      "Set-Content -LiteralPath (Join-Path $scanRoot ([string][char]0x005A + '.txt')) -Value 'ascii-z' -NoNewline -Encoding ASCII\n"
      "Set-Content -LiteralPath (Join-Path $scanRoot ([string][char]0x00C4 + '.txt')) -Value 'umlaut-a' -NoNewline -Encoding ASCII\n"
      "Set-Content -LiteralPath (Join-Path $scanRoot ([string][char]0x00F6 + '.txt')) -Value 'umlaut-o' -NoNewline -Encoding ASCII\n",
      "新增 3 个非 ASCII/序数敏感夹具文件（Z / Ä / ö）")

# ------------------------------------------------------------------- 新增检查
NEW_CHECKS = r'''
# ---- deepening round 1.2.0: contract clauses previously not covered ---------
# Each check restates a rule the behaviour contract already makes authoritative;
# no new requirement is introduced.

Add-WReparseCheck 'sorting-is-culture-independent' {
    if ($reportError) { return $reportError }
    $asciiZ = [string][char]0x005A + '.txt'
    $umlautA = [string][char]0x00C4 + '.txt'
    $umlautO = [string][char]0x00F6 + '.txt'
    $paths = @($never.Records | ForEach-Object { [string]$_.RelativePath })
    $indexOf = @{}
    for ($i = 0; $i -lt $paths.Count; $i++) { if (-not $indexOf.ContainsKey($paths[$i])) { $indexOf[$paths[$i]] = $i } }
    foreach ($name in @($asciiZ, $umlautA, $umlautO)) {
        if (-not $indexOf.ContainsKey($name)) { return "record '$name' is missing from the report" }
    }
    if ($indexOf[$asciiZ] -ge $indexOf[$umlautA] -or $indexOf[$umlautA] -ge $indexOf[$umlautO]) {
        return ("records are not in ordinal order around the non-ASCII names " +
                "($asciiZ at $($indexOf[$asciiZ]), $umlautA at $($indexOf[$umlautA]), $umlautO at $($indexOf[$umlautO])); " +
                "the contract requires an ordinal-ignore-case key, so a culture-aware sort is not acceptable")
    }
    return $true
}

Add-WReparseCheck 'module-exports-exactly-six-functions' {
    $expected = @(
        'Get-WReparseReport', 'ConvertTo-WReparseJson', 'Get-WReparseSchemaVersion',
        'Test-WReparseWithinRoot', 'Get-WReparseCanonicalPath', 'Resolve-WReparseLinkTarget'
    )
    $actual = @(Get-Command -Module 'WReparse' -CommandType Function -ErrorAction SilentlyContinue |
        ForEach-Object { [string]$_.Name })
    if ($actual.Count -eq 0) { return 'the module surface could not be inspected (Get-Command -Module WReparse returned nothing)' }
    $extra = @($actual | Where-Object { $expected -notcontains $_ })
    if ($extra.Count -gt 0) {
        return "the module exports functions outside the contract surface: $($extra -join ', ')"
    }
    $missing = @($expected | Where-Object { $actual -notcontains $_ })
    if ($missing.Count -gt 0) { return "the module does not export: $($missing -join ', ')" }
    return $true
}

Add-WReparseCheck 'target-is-serialised-as-string' {
    if ($reportError) { return $reportError }
    $link = Get-WReparseTestRecord -Report $never -RelativePath 'link-rel'
    if ($null -eq $link) { return 'record link-rel is missing' }
    if ($null -ne $link.Target -and $link.Target -isnot [string]) {
        return "link-rel Target has type '$($link.Target.GetType().FullName)'; the contract defines Target as a single target string"
    }
    return $true
}

Add-WReparseCheck 'report-has-exactly-contract-fields' {
    if ($reportError) { return $reportError }
    $expected = @('SchemaVersion', 'Root', 'Records', 'Errors', 'Stats')
    $actual = @($never.PSObject.Properties | ForEach-Object { [string]$_.Name })
    $extra = @($actual | Where-Object { $expected -notcontains $_ })
    if ($extra.Count -gt 0) {
        return "the report carries fields the contract does not define: $($extra -join ', ')"
    }
    $missing = @($expected | Where-Object { $actual -notcontains $_ })
    if ($missing.Count -gt 0) { return "the report is missing contract fields: $($missing -join ', ')" }
    return $true
}

Add-WReparseCheck 'no-follow-produces-no-cycle-or-broken-target' {
    if ($reportError) { return $reportError }
    foreach ($code in @('cycle', 'broken_target')) {
        $hits = @($never.Errors | Where-Object { [string]$_.Code -eq $code })
        if ($hits.Count -gt 0) {
            return "a default (non-follow) scan produced '$code'; without -Follow the contract forbids cycle and broken_target"
        }
    }
    return $true
}

Add-WReparseCheck 'inscope-is-false-for-non-reparse-entries' {
    if ($reportError) { return $reportError }
    foreach ($path in @('plain.txt', 'docs', 'hardlink.txt')) {
        $record = Get-WReparseTestRecord -Report $never -RelativePath $path
        if ($null -eq $record) { return "record $path is missing" }
        if ($record.InScope -ne $false) {
            return "$path has Kind '$($record.Kind)' but InScope=$($record.InScope); InScope is only meaningful for reparse entries and is false otherwise"
        }
    }
    return $true
}

# ---- persist ---------------------------------------------------------------
'''

patch(RUN, "\n# ---- persist ---------------------------------------------------------------\n",
      NEW_CHECKS, "插入 6 条新检查")

# ------------------------------------------------------------------ 版本号
patch(RUN, "    task_version = '1.1.0'", "    task_version = '1.2.0'", "run_tests 版本 -> 1.2.0")

print()
print("夹具文件（prepare.ps1）与检查（run_tests.ps1）已更新")
print("RESULT:", "部分失败" if failed else "第四步完成")
sys.exit(1 if failed else 0)
