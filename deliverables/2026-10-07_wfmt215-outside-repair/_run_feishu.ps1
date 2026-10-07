$ErrorActionPreference = 'Continue'
$dir = 'C:\Users\Administrator\Desktop\wff-task\deliverables\2026-10-07_wfmt215-outside-repair'
$log = Join-Path $dir '_feishu_upload.log'
$script = 'C:\Users\Administrator\Desktop\generate-win\scripts\upload_feishu.ps1'

$params = @{
    Direction   = 'Windows/文件格式与序列化（LEB128 varint + CRC32 容器）/Python/缺陷修复'
    PromptFile  = 'C:\Users\Administrator\Desktop\wff-task\harbor-windows\wfflab__wfmt-215\instruction.md'
    OracleImage = Join-Path $dir 'evidence\oracle_nop_controls.png'
    ScoreImage  = Join-Path $dir 'evidence\score_summary.png'
    ZipPath     = Join-Path $dir 'package\wfflab__wfmt-215-v2.0.0.zip'
    Status      = '待提交'
    ConfirmWrite = $true
}

$out = ''
try {
    $out = (& $script @params 2>&1 | Out-String)
    $code = $LASTEXITCODE
} catch {
    $out = "TERMINATING: " + $_.Exception.GetType().FullName + " :: " + $_.Exception.Message
    $out += "`n--- ScriptStackTrace ---`n" + $_.ScriptStackTrace
    $code = 99
}
"=== exit=$code ===" + "`n" + $out | Out-File -LiteralPath $log -Encoding utf8
Write-Output ("exit=" + $code)
