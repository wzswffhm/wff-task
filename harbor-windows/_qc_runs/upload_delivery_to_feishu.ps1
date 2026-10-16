[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Task,      # 215 / 216 / 219 / 220
    [Parameter(Mandatory = $true)][string]$RecordId,
    [switch]$ConfirmWrite,
    [switch]$SkipBig
)

# 把交付 ZIP 与两张证据截图写入飞书多维表对应记录（整体赋值，保证格内只有新件）。
#
# 沿用 deliverables\2026-10-14_wvas216-替换\scripts\feishu-216-upload-native.ps1 的既有结论：
#   +record-upload-attachment 走 base/v3 在本环境 404，改走原生接口；
#   小文件(<=20MB): POST /open-apis/drive/v1/medias/upload_all
#   大文件(>20MB) : upload_prepare -> upload_part xN -> upload_finish
#   再 PUT /open-apis/bitable/v1/apps/<app>/tables/<tbl>/records/<rec>
#   body {"fields":{"<字段>":[{"file_token":"..."}]}}
#
# 本文件必须以 UTF-8 带 BOM 保存。
#
# 用法：
#   .\upload_delivery_to_feishu.ps1 -Task 215 -RecordId reczz28KwEOO3xHy                # 只读预演
#   .\upload_delivery_to_feishu.ps1 -Task 215 -RecordId reczz28KwEOO3xHy -ConfirmWrite  # 真正上传

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$BaseToken = 'EsJebL8JJaf7g4sIbItcnMFgnvg'
$TableId   = 'tblRDxcGkblflMBA'
$PyExe     = 'C:\Users\Administrator\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe'
$SingleMax = 20MB
$Slice     = 'C:\Users\Administrator\Desktop\wff-task\deliverables\2026-10-14_wvas216-替换\scripts\slice_for_upload.py'

$HW = 'C:\Users\Administrator\Desktop\wff-task\harbor-windows'
$Spec = @{
    '215' = @{ build = 'wsparse-build'; zip = 'wfflab__wsparse-215-v1.0.0-delivery.zip' }
    '216' = @{ build = 'wvas-build';    zip = 'wfflab__wvas-216-v1.0.0-delivery.zip' }
    '219' = @{ build = 'wcancel-build'; zip = 'wfflab__wcancel-219-v1.0.0-delivery.zip' }
    '220' = @{ build = 'wciocp-build';  zip = 'wfflab__wciocp-220-v1.0.0-delivery.zip' }
    '218' = @{ build = 'wspawn-build';  zip = 'wfflab__wspawn-218-v1.0.0-delivery.zip' }
}[$Task]
if (-not $Spec) { throw "未知 task: $Task" }

$imgDir = Join-Path $HW ("_qc_runs\{0}\evidence\images" -f $Spec.build)
$zipDir = Join-Path $HW ("_qc_runs\{0}\zip" -f $Spec.build)
$Work   = Join-Path $env:TEMP ("feishu{0}-parts" -f $Task)

$Targets = @(
    [ordered]@{ field = 'oracle/nop截图'; path = (Join-Path $imgDir 'oracle_nop_controls.png'); image = $true },
    [ordered]@{ field = '分数截图';       path = (Join-Path $imgDir 'score_summary.png');       image = $true },
    [ordered]@{ field = '作业压缩包';     path = (Join-Path $zipDir $Spec.zip);                 image = $false }
)

function Invoke-Api([string[]]$Arguments) {
    $ErrorActionPreference = 'Continue'
    $raw = (& lark-cli @Arguments 2>&1 | Out-String)
    $start = $raw.IndexOf('{'); $end = $raw.LastIndexOf('}')
    if ($start -lt 0 -or $end -le $start) { throw "lark-cli 未返回 JSON: $raw" }
    $doc = $raw.Substring($start, $end - $start + 1) | ConvertFrom-Json
    if ($doc.ok -eq $false) { throw ("lark-cli 报错: " + ($doc.error | ConvertTo-Json -Compress -Depth 8)) }
    return $doc
}

function Write-Json([string]$Dir, [string]$Name, [object]$Payload) {
    [System.IO.File]::WriteAllText((Join-Path $Dir $Name), ($Payload | ConvertTo-Json -Compress -Depth 20),
                                   (New-Object System.Text.UTF8Encoding($false)))
}

function Invoke-In([string]$Dir, [string[]]$Arguments) {
    Push-Location $Dir
    [Environment]::CurrentDirectory = $Dir
    try { return Invoke-Api $Arguments } finally { Pop-Location }
}

function Get-ImageSize([string]$Path) {
    $code = 'import sys;from PIL import Image;im=Image.open(sys.argv[1]);print(im.width, im.height)'
    $out = (& $PyExe -c $code $Path 2>&1 | Out-String).Trim()
    if ($out -match '^(\d+)\s+(\d+)$') { return @([int]$Matches[1], [int]$Matches[2]) }
    return @($null, $null)
}

Write-Host '=============================================================================='
Write-Host ("Task {0}  ->  {1} / {2} / {3}" -f $Task, $BaseToken, $TableId, $RecordId)
Write-Host ("模式：{0}" -f $(if ($ConfirmWrite) { '上传' } else { '只读预演' }))
Write-Host '=============================================================================='

if ($ConfirmWrite -and (Test-Path -LiteralPath $Work)) { Remove-Item -LiteralPath $Work -Recurse -Force }
if ($ConfirmWrite) { New-Item -ItemType Directory -Path $Work -Force | Out-Null }

$tokens = [ordered]@{}
foreach ($t in $Targets) {
    if (-not (Test-Path -LiteralPath $t.path -PathType Leaf)) { throw "缺少文件: $($t.path)" }
    $f = Get-Item -LiteralPath $t.path
    $dir = Split-Path -Parent $f.FullName
    $big = $f.Length -gt $SingleMax
    Write-Host ("`n[素材] {0}  ({1:N0} B, {2})" -f $f.Name, $f.Length, $(if ($big) { '分片上传' } else { 'upload_all' }))

    if ($SkipBig -and $big) { Write-Host '  [skip] 按 -SkipBig 跳过大文件'; continue }

    if (-not $ConfirmWrite) {
        $tokens[$t.field] = '<token>'
        continue
    }

    if (-not $big) {
        Write-Json $dir '.media.json' ([ordered]@{ file_name = $f.Name; parent_type = 'bitable_file'; parent_node = $BaseToken; size = $f.Length })
        try {
            $doc = Invoke-In $dir @('api', 'POST', '/open-apis/drive/v1/medias/upload_all', '--as', 'user',
                                    '--file', "file=./$($f.Name)", '--data', '@.media.json', '--format', 'json')
            $tokens[$t.field] = [string]$doc.data.file_token
            Write-Host ("  file_token = {0}" -f $tokens[$t.field])
        } finally { Remove-Item -LiteralPath (Join-Path $dir '.media.json') -Force -ErrorAction SilentlyContinue }
        continue
    }

    Write-Json $dir '.prep.json' ([ordered]@{ file_name = $f.Name; parent_type = 'bitable_file'; parent_node = $BaseToken; size = $f.Length })
    try {
        $prep = Invoke-In $dir @('api', 'POST', '/open-apis/drive/v1/medias/upload_prepare', '--as', 'user',
                                 '--data', '@.prep.json', '--format', 'json')
    } finally { Remove-Item -LiteralPath (Join-Path $dir '.prep.json') -Force -ErrorAction SilentlyContinue }
    $uploadId = [string]$prep.data.upload_id
    $blockNum = [int]$prep.data.block_num
    $blockSize = [int]$prep.data.block_size
    Write-Host ("  upload_id = {0}  block_num = {1}  block_size = {2}" -f $uploadId, $blockNum, $blockSize)

    $parts = (& $PyExe $Slice $f.FullName $Work $blockSize 2>&1 | Out-String).Trim()
    Write-Host ("  已切成 {0} 片" -f $parts)

    for ($seq = 0; $seq -lt $blockNum; $seq++) {
        $partName = "part_{0:000}.bin" -f $seq
        Write-Json $Work ("p$seq.json") ([ordered]@{ upload_id = $uploadId; seq = $seq })
        try {
            Invoke-In $Work @('api', 'POST', '/open-apis/drive/v1/medias/upload_part', '--as', 'user',
                              '--file', "file=./$partName", '--params', "@p$seq.json", '--format', 'json') | Out-Null
        } finally { Remove-Item -LiteralPath (Join-Path $Work "p$seq.json") -Force -ErrorAction SilentlyContinue }
        Write-Host ("    seq {0}/{1} ok" -f $seq, ($blockNum - 1))
    }

    Write-Json $Work '.fin.json' ([ordered]@{ upload_id = $uploadId; block_num = $blockNum })
    try {
        $fin = Invoke-In $Work @('api', 'POST', '/open-apis/drive/v1/medias/upload_finish', '--as', 'user',
                                 '--data', '@.fin.json', '--format', 'json')
    } finally { Remove-Item -LiteralPath (Join-Path $Work '.fin.json') -Force -ErrorAction SilentlyContinue }
    $tokens[$t.field] = [string]$fin.data.file_token
    Write-Host ("  file_token = {0}" -f $tokens[$t.field])
}

$fields = [ordered]@{}
foreach ($t in $Targets) {
    if (-not $tokens.Contains($t.field)) { continue }
    $entry = [ordered]@{ file_token = $tokens[$t.field] }
    if ($t.image -and $ConfirmWrite) {
        $wh = Get-ImageSize $t.path
        if ($wh[0]) { $entry['image_width'] = $wh[0]; $entry['image_height'] = $wh[1] }
    }
    $fields[$t.field] = @($entry)
}

if (-not $ConfirmWrite) {
    Write-Host ('  [dry-run] body = ' + (([ordered]@{ fields = $fields }) | ConvertTo-Json -Compress -Depth 20))
    Write-Host "`n预演完成。加 -ConfirmWrite 才会真正上传。"
    exit 0
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Write-Json $scriptDir '.record.json' ([ordered]@{ fields = $fields })
try {
    $res = Invoke-In $scriptDir @('api', 'PUT', ("/open-apis/bitable/v1/apps/{0}/tables/{1}/records/{2}" -f $BaseToken, $TableId, $RecordId),
                                 '--as', 'user', '--data', '@.record.json', '--format', 'json')
    Write-Host ("`n  记录已更新 code={0}" -f $res.code)
} finally { Remove-Item -LiteralPath (Join-Path $scriptDir '.record.json') -Force -ErrorAction SilentlyContinue }

if (Test-Path -LiteralPath $Work) { Remove-Item -LiteralPath $Work -Recurse -Force -ErrorAction SilentlyContinue }

Write-Host "`n[回读验证]"
$g = Invoke-Api @('base', '+record-get', '--as', 'user', '--base-token', $BaseToken,
                  '--table-id', $TableId, '--record-id', $RecordId, '--format', 'json')
$flds = @($g.data.fields); $row = @(@($g.data.data)[0])
$cells = [ordered]@{}
for ($i = 0; $i -lt $flds.Count; $i++) { $cells[$flds[$i]] = if ($i -lt $row.Count) { $row[$i] } else { $null } }

$ok = $true
foreach ($t in $Targets) {
    if (-not $tokens.Contains($t.field)) { continue }
    $cell = @($cells[$t.field] | Where-Object { $_ })
    $leaf = Split-Path -Leaf $t.path
    $size = (Get-Item -LiteralPath $t.path).Length
    $exact = @($cell | Where-Object { $_.name -eq $leaf -and [int64]$_.size -eq $size })
    $state = if ($exact.Count -eq 1 -and $cell.Count -eq 1) { '匹配且唯一' } else { '**异常**' }
    $names = @($cell | ForEach-Object { "$($_.name)($($_.size))" })
    Write-Host ("  {0,-14}: {1}（格内 {2} 件: {3}）" -f $t.field, $state, $cell.Count, ($names -join ', '))
    if ($exact.Count -ne 1 -or $cell.Count -ne 1) { $ok = $false }
}
Write-Host ("`n结论：{0}" -f $(if ($ok) { '全部附件均已上传且格内唯一' } else { '**存在不一致**' }))
if (-not $ok) { exit 1 }
