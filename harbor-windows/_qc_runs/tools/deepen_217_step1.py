"""217 加深（第一步）：新增夹具项、新增 6 条契约一致性检查、同步 Skipped 计数。

所有新检查都对应 REPARSE-CONTRACT.md 中**已声明但此前未覆盖**的行为：
  §4.3 -MaxDepth < 0 按 0 处理
  §7   invalid_argument
  §4.2 跟随模式下子项以**链接路径**为前缀
  §4.2 目标是文件时不产生子项
  §4.2 环判定只限**当前分支的祖先链**
  §8   空数组序列化为 []
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
        print(f"!! {path.name}: {label} 命中 {n} 次")
        failed = True
        return
    path.write_text(text.replace(old, new), encoding="utf-8")
    print(f"ok {path.name}: {label}")


# ---------------------------------------------------------------- 夹具新增
patch(PREP,
      "New-Item -ItemType Directory -Path $outsideRoot -Force | Out-Null",
      "New-Item -ItemType Directory -Path (Join-Path $scanRoot 'empty') -Force | Out-Null\n"
      "New-Item -ItemType Directory -Path $outsideRoot -Force | Out-Null",
      "新增空目录 empty")

patch(PREP,
      "New-Item -ItemType Junction -Path (Join-Path $scanRoot 'link-loop') -Target $scanRoot | Out-Null",
      "New-Item -ItemType Junction -Path (Join-Path $scanRoot 'link-loop') -Target $scanRoot | Out-Null\n"
      "# A second junction onto the same target as link-in: revisiting a target that is\n"
      "# not on the current branch's ancestry must NOT be reported as a cycle.\n"
      "New-Item -ItemType Junction -Path (Join-Path $scanRoot 'link-twin') -Target (Join-Path $scanRoot 'docs') | Out-Null",
      "新增 link-twin（与 link-in 同目标）")

patch(PREP,
      "$danglingLink = cmd.exe /c \"cd /d `\"$scanRoot`\" && mklink /D link-dangling missing-target 2>&1\"\n"
      "if ($LASTEXITCODE -ne 0) {\n"
      "    throw \"Failed to create relative symbolic link 'link-dangling': $danglingLink\"\n"
      "}",
      "$danglingLink = cmd.exe /c \"cd /d `\"$scanRoot`\" && mklink /D link-dangling missing-target 2>&1\"\n"
      "if ($LASTEXITCODE -ne 0) {\n"
      "    throw \"Failed to create relative symbolic link 'link-dangling': $danglingLink\"\n"
      "}\n"
      "\n"
      "# A symbolic link whose target is a FILE: with -Follow it is registered but must\n"
      "# not yield any child entries.\n"
      "$fileLink = cmd.exe /c \"cd /d `\"$scanRoot`\" && mklink link-file plain.txt 2>&1\"\n"
      "if ($LASTEXITCODE -ne 0) {\n"
      "    throw \"Failed to create file symbolic link 'link-file': $fileLink\"\n"
      "}",
      "新增 link-file（文件目标符号链接）")

# ------------------------------------------------------- Skipped 计数 6 -> 8
patch(RUN,
      "    if ([int]$never.Stats.Skipped -ne 6) {\n"
      "        return \"Stats.Skipped was $($never.Stats.Skipped); the default scan must not enter any of the 6 reparse points\"\n"
      "    }",
      "    if ([int]$never.Stats.Skipped -ne 8) {\n"
      "        return \"Stats.Skipped was $($never.Stats.Skipped); the default scan must not enter any of the 8 reparse points\"\n"
      "    }",
      "Skipped 断言 6 -> 8")

# ------------------------------------------------------------------ 新增检查
NEW_CHECKS = r'''
# ---- deepening round 1.1.0: contract clauses previously not covered ---------

Add-WReparseCheck 'negative-maxdepth-is-treated-as-zero' {
    $negative = Get-WReparseReport -Root $scanRoot -MaxDepth -5
    $zero = Get-WReparseReport -Root $scanRoot -MaxDepth 0
    if ((ConvertTo-WReparseJson -Report $negative) -ne (ConvertTo-WReparseJson -Report $zero)) {
        return 'a negative -MaxDepth must behave exactly like 0'
    }
    if (-not (Test-WReparseHasError -Report $negative -Code 'too_deep')) {
        return "no 'too_deep' error was reported for -MaxDepth < 0"
    }
    return $true
}

Add-WReparseCheck 'invalid-root-reports-invalid-argument' {
    $report = Get-WReparseReport -Root 'C:\bad<name>|x'
    if (-not (Test-WReparseHasError -Report $report -Code 'invalid_argument')) {
        return "no 'invalid_argument' error was reported for a root that cannot be normalised"
    }
    return $true
}

Add-WReparseCheck 'follow-uses-link-path-prefix' {
    if ($reportError) { return $reportError }
    $viaLink = Get-WReparseTestRecord -Report $follow -RelativePath (Join-Path 'link-in' 'readme.txt')
    if ($null -eq $viaLink) {
        return 'in follow mode, entries reached through a link must be named with the link path prefix'
    }
    if ([string]$viaLink.Kind -ne 'File') { return "link-in\readme.txt Kind was '$($viaLink.Kind)'" }
    return $true
}

Add-WReparseCheck 'follow-file-link-produces-no-children' {
    if ($reportError) { return $reportError }
    $link = Get-WReparseTestRecord -Report $follow -RelativePath 'link-file'
    if ($null -eq $link) { return 'record link-file is missing in follow mode' }
    $children = @($follow.Records | Where-Object { ([string]$_.RelativePath) -like 'link-file\*' })
    if ($children.Count -ne 0) {
        return "a link whose target is a file must not produce child entries, found $($children.Count)"
    }
    return $true
}

Add-WReparseCheck 'repeated-target-in-sibling-branch-is-not-a-cycle' {
    if ($reportError) { return $reportError }
    $twin = Get-WReparseTestRecord -Report $follow -RelativePath 'link-twin'
    if ($null -eq $twin) { return 'record link-twin is missing in follow mode' }
    $cycleForTwin = @($follow.Errors | Where-Object { [string]$_.Code -eq 'cycle' -and [string]$_.RelativePath -eq 'link-twin' })
    if ($cycleForTwin.Count -gt 0) {
        return 'a target already visited in a sibling branch is not an ancestor cycle'
    }
    $child = Get-WReparseTestRecord -Report $follow -RelativePath (Join-Path 'link-twin' 'readme.txt')
    if ($null -eq $child) { return 'link-twin must be entered: its target is not on the current ancestry chain' }
    return $true
}

Add-WReparseCheck 'empty-tree-serialises-empty-arrays' {
    $report = Get-WReparseReport -Root (Join-Path $scanRoot 'empty')
    $json = ConvertTo-WReparseJson -Report $report
    if ($json -notmatch '"Records"\s*:\s*\[\s*\]') { return 'an empty Records collection must serialise as []' }
    if ($json -notmatch '"Errors"\s*:\s*\[\s*\]') { return 'an empty Errors collection must serialise as []' }
    return $true
}

# ---- persist ---------------------------------------------------------------
'''

patch(RUN, "\n# ---- persist ---------------------------------------------------------------\n", NEW_CHECKS, "插入 6 条新检查")

# ------------------------------------------------------------------ 版本号
patch(RUN, "    task_version = '1.0.0'", "    task_version = '1.1.0'", "run_tests 版本 -> 1.1.0")

print("\nRESULT:", "部分失败" if failed else "第一步完成")
sys.exit(1 if failed else 0)
