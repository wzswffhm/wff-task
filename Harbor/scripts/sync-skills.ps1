<#
.SYNOPSIS
    三向 Skill 同步脚本：GitHub(harbor repo) <-> Codex <-> DSH

.DESCRIPTION
    保持三个位置的 skill 始终同步：
    - GitHub:  C:\Users\Administrator\Desktop\harbor\.dsh\skills\  (版本控制，source of truth)
    - Codex:   C:\Users\Administrator\.codex\skills\              (Codex CLI 读取)
    - DSH:     C:\Users\Administrator\.dsh\skills\                (DSH/DeepSeek Harness 读取)

.PARAMETER Direction
    sync   - 从 repo 同步到 Codex 和 DSH（默认）
    pull   - 从 Codex 拉取到 repo，再同步到 DSH
    status - 显示三个位置的差异

.EXAMPLE
    .\sync-skills.ps1              # 从 repo 同步到 Codex + DSH
    .\sync-skills.ps1 -Direction pull  # 从 Codex 拉取变更到 repo
    .\sync-skills.ps1 -Direction status # 查看差异
#>

param(
    [ValidateSet('sync', 'pull', 'status')]
    [string]$Direction = 'sync'
)

$ErrorActionPreference = 'Stop'

# ── 路径定义 ──
$RepoDir   = "C:\Users\Administrator\Desktop\harbor\.dsh\skills"
$CodexDir  = "C:\Users\Administrator\.codex\skills"
$DshDir    = "C:\Users\Administrator\.dsh\skills"

# 要同步的 skill 列表（排除 .system、.tmp_home 等）
$ExcludeDirs = @('.system', '.tmp_home')

function Get-SkillList {
    param([string]$BaseDir)
    if (-not (Test-Path $BaseDir)) { return @() }
    Get-ChildItem -Path $BaseDir -Directory |
        Where-Object { $ExcludeDirs -notcontains $_.Name } |
        Select-Object -ExpandProperty Name
}

function Sync-SkillDir {
    param(
        [string]$Source,
        [string]$Dest,
        [string]$SkillName
    )
    $src = Join-Path $Source $SkillName
    $dst = Join-Path $Dest $SkillName

    if (-not (Test-Path $src)) {
        Write-Host "  [SKIP] $SkillName - not found in source" -ForegroundColor Yellow
        return
    }

    if (Test-Path $dst) {
        Remove-Item -Recurse -Force $dst
    }
    Copy-Item -Recurse -Force $src $dst
    Write-Host "  [OK]   $SkillName" -ForegroundColor Green
}

function Show-Status {
    Write-Host "`n=== Skill 同步状态 ===" -ForegroundColor Cyan
    Write-Host ""

    $repoSkills  = Get-SkillList $RepoDir
    $codexSkills = Get-SkillList $CodexDir
    $dshSkills   = Get-SkillList $DshDir

    $allSkills = ($repoSkills + $codexSkills + $dshSkills) | Sort-Object -Unique

    Write-Host ("{0,-25} {1,-10} {2,-10} {3,-10}" -f "Skill", "Repo", "Codex", "DSH")
    Write-Host ("{0,-25} {1,-10} {2,-10} {3,-10}" -f "-----", "----", "------", "---")

    foreach ($skill in $allSkills) {
        $inRepo  = if ($repoSkills  -contains $skill) { "  ✓" } else { "  ✗" }
        $inCodex = if ($codexSkills -contains $skill) { "  ✓" } else { "  ✗" }
        $inDsh   = if ($dshSkills   -contains $skill) { "  ✓" } else { "  ─" }
        Write-Host ("{0,-25} {1,-10} {2,-10} {3,-10}" -f $skill, $inRepo, $inCodex, $inDsh)
    }

    # Check for name mismatches (frontmatter vs directory)
    Write-Host "`n=== Frontmatter name 检查 ===" -ForegroundColor Cyan
    foreach ($skill in $repoSkills) {
        $skillFile = Join-Path $RepoDir "$skill\SKILL.md"
        if (-not (Test-Path $skillFile)) {
            $skillFile = Join-Path $RepoDir "$skill\$skill.md"
        }
        if (Test-Path $skillFile) {
            $content = Get-Content $skillFile -Raw
            if ($content -match 'name:\s*(.+)') {
                $frontName = $matches[1].Trim().Trim('"').Trim("'")
                $kebabName = $frontName.ToLower() -replace '\s+', '-'
                if ($frontName -ne $kebabName) {
                    Write-Host "  [WARN] ${skill}: frontmatter name='${frontName}' (should be kebab-case: '${kebabName}')" -ForegroundColor Yellow
                }
            }
        }
    }
    Write-Host ""
}

# ── 主逻辑 ──
switch ($Direction) {
    'status' {
        Show-Status
    }
    'sync' {
        Write-Host "`n=== 从 Repo 同步到 Codex + DSH ===" -ForegroundColor Cyan
        $skills = Get-SkillList $RepoDir
        if ($skills.Count -eq 0) {
            Write-Host "Repo 中没有找到 skill。" -ForegroundColor Yellow
            exit
        }

        # 确保目标目录存在
        foreach ($dir in @($CodexDir, $DshDir)) {
            if (-not (Test-Path $dir)) {
                New-Item -ItemType Directory -Path $dir -Force | Out-Null
            }
        }

        Write-Host "`n→ 同步到 Codex ($CodexDir):"
        foreach ($skill in $skills) {
            Sync-SkillDir -Source $RepoDir -Dest $CodexDir -SkillName $skill
        }

        Write-Host "`n→ 同步到 DSH ($DshDir):"
        foreach ($skill in $skills) {
            Sync-SkillDir -Source $RepoDir -Dest $DshDir -SkillName $skill
        }

        Write-Host "`n✓ 同步完成！共 $($skills.Count) 个 skill。" -ForegroundColor Green
    }
    'pull' {
        Write-Host "`n=== 从 Codex 拉取到 Repo ===" -ForegroundColor Cyan
        $skills = Get-SkillList $CodexDir
        if ($skills.Count -eq 0) {
            Write-Host "Codex 中没有找到 skill。" -ForegroundColor Yellow
            exit
        }

        Write-Host "`n→ 拉取到 Repo ($RepoDir):"
        foreach ($skill in $skills) {
            Sync-SkillDir -Source $CodexDir -Dest $RepoDir -SkillName $skill
        }

        Write-Host "`n→ 再同步到 DSH ($DshDir):"
        foreach ($skill in $skills) {
            Sync-SkillDir -Source $RepoDir -Dest $DshDir -SkillName $skill
        }

        Write-Host "`n✓ 拉取+同步完成！共 $($skills.Count) 个 skill。" -ForegroundColor Green
        Write-Host "  记得在 harbor 目录下 git add + commit + push 推送到 GitHub。" -ForegroundColor Yellow
    }
}
