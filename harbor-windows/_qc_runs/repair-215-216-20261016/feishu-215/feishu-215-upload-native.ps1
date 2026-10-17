[CmdletBinding()]
param(
    [switch]$ConfirmWrite
)

# 用原生 OpenAPI 把三个附件写进飞书 216 槽位记录 reczz28KQU8reW2k。
#
# 为什么不用 lark-cli 的 typed 命令：
#   +record-upload-attachment / +record-remove-attachment 在 1.0.85 与 1.0.98 上都返回
#   "HTTP 404: 404 page not found"。按其 --dry-run 的三步编排，第 1 步
#   GET /open-apis/base/v3/.../fields/<field> 与第 3 步 POST .../append_attachments 都走
#   base/v3，而该路径在本环境 404（单独 GET 也 404）；对照的 bitable/v1 路径存在。
#   因此改走原生接口：
#     小文件(<=20MB): POST /open-apis/drive/v1/medias/upload_all  (multipart, parent_type=bitable_file)
#     大文件(>20MB):  POST /open-apis/drive/v1/medias/upload_prepare -> upload_part x N -> upload_finish
#   两者都产出 file_token，再用一次
#     PUT /open-apis/bitable/v1/apps/<app>/tables/<tbl>/records/<rec>
#   body {"fields":{"<字段>":[{"file_token":"..."}]}} 整体赋值写回。
#   整体赋值（而非追加）天然保证「格内只有新件」。
#
# PS 5.1 下 --data / --params 的 JSON 都必须「写文件 + @<相对名>」，
# 直接当参数传会被剥掉内层引号；--file 也只接受当前目录下的相对路径。
#
# 本文件必须以 UTF-8 带 BOM 保存。
#
# 用法：
#   .\feishu-216-upload-native.ps1                # 只读预演
#   .\feishu-216-upload-native.ps1 -ConfirmWrite  # 真正上传

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$BaseToken = 'EsJebL8JJaf7g4sIbItcnMFgnvg'
$TableId   = 'tblRDxcGkblflMBA'
$RecordId  = 'reczz28KwEOO3xHy'
$PyExe     = 'C:\Users\Administrator\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe'
$SingleMax = 20MB

$deliv = 'C:\Users\Administrator\Desktop\wff-task\harbor-windows\_delivery-101'
$ImgDir = 'C:\Users\Administrator\Desktop\wff-task\harbor-windows\_qc_runs\repair-215-216-20261016\feishu-215\images'
$Work  = Join-Path $env:TEMP 'feishu215-parts'

$Targets = @(
    [ordered]@{ field = 'oracle/nop截图'; path = (Join-Path $ImgDir 'oracle_nop_controls.png'); image = $true },
    [ordered]@{ field = '分数截图';       path = (Join-Path $ImgDir 'score_summary.png');       image = $true },
    [ordered]@{ field = '作业压缩包';     path = (Join-Path $deliv 'wfflab__wsparse-215-v1.0.1-delivery.zip'); image = $false }
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
    [System.IO.File]::WriteAllText((Join-Path $Dir $Name), ($Payload | ConvertTo-Json -Compress -Depth 20), (New-Object System.Text.UTF8Encoding($false)))
}

# --file/--data/--params 的相对路径语义要求调用时的工作目录就是文件所在目录。
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
Write-Host ("把三个附件写入 {0} / {1} / {2}" -f $BaseToken, $TableId, $RecordId)
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
    Write-Host ("`n[素材] {0}  ({1} B, {2})" -f $f.Name, $f.Length, $(if ($big) { '分片上传' } else { 'upload_all' }))

    if (-not $ConfirmWrite) {
        if ($big) {
            Write-Host ("  [dry-run] POST /open-apis/drive/v1/medias/upload_prepare  size={0}" -f $f.Length)
            Write-Host  "  [dry-run] POST /open-apis/drive/v1/medias/upload_part  x ceil(size/4194304)"
            Write-Host  "  [dry-run] POST /open-apis/drive/v1/medias/upload_finish"
        } else {
            Write-Host ("  [dry-run] POST /open-apis/drive/v1/medias/upload_all  file=./{0} size={1}" -f $f.Name, $f.Length)
        }
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

    # 大文件：prepare -> 切片 -> upload_part x N -> finish
    Write-Json $dir '.prep.json' ([ordered]@{ file_name = $f.Name; parent_type = 'bitable_file'; parent_node = $BaseToken; size = $f.Length })
    try {
        $prep = Invoke-In $dir @('api', 'POST', '/open-apis/drive/v1/medias/upload_prepare', '--as', 'user',
                                 '--data', '@.prep.json', '--format', 'json')
    } finally { Remove-Item -LiteralPath (Join-Path $dir '.prep.json') -Force -ErrorAction SilentlyContinue }
    $uploadId = [string]$prep.data.upload_id
    $blockNum = [int]$prep.data.block_num
    $blockSize = [int]$prep.data.block_size
    Write-Host ("  upload_id = {0}  block_num = {1}  block_size = {2}" -f $uploadId, $blockNum, $blockSize)

    # 切片交给独立脚本：PS 5.1 把多行代码经 -c 传给 python.exe 会破坏换行与双引号
    $parts = (& $PyExe (Join-Path $PSScriptRoot 'slice_for_upload.py') $f.FullName $Work $blockSize 2>&1 | Out-String).Trim()
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

Write-Host "`n[写回记录] PUT /open-apis/bitable/v1/apps/<app>/tables/<tbl>/records/<rec>"
$fields = [ordered]@{}
foreach ($t in $Targets) {
    $entry = [ordered]@{ file_token = $tokens[$t.field] }
    if ($t.image -and $ConfirmWrite) {
        $wh = Get-ImageSize $t.path
        if ($wh[0]) { $entry['image_width'] = $wh[0]; $entry['image_height'] = $wh[1] }
        Write-Host ("  {0,-14} image {1}x{2}" -f $t.field, $wh[0], $wh[1])
    }
    $fields[$t.field] = @($entry)
}

if (-not $ConfirmWrite) {
    Write-Host ('  [dry-run] body = ' + (([ordered]@{ fields = $fields }) | ConvertTo-Json -Compress -Depth 20))
    Write-Host "`n预演完成。加 -ConfirmWrite 才会真正上传。"
    exit 0
}

Write-Json $PSScriptRoot '.record.json' ([ordered]@{ fields = $fields })
try {
    $res = Invoke-In $PSScriptRoot @('api', 'PUT', ("/open-apis/bitable/v1/apps/{0}/tables/{1}/records/{2}" -f $BaseToken, $TableId, $RecordId),
                                    '--as', 'user', '--data', '@.record.json', '--format', 'json')
    Write-Host ("  记录已更新 code={0}" -f $res.code)
} finally { Remove-Item -LiteralPath (Join-Path $PSScriptRoot '.record.json') -Force -ErrorAction SilentlyContinue }

if (Test-Path -LiteralPath $Work) { Remove-Item -LiteralPath $Work -Recurse -Force -ErrorAction SilentlyContinue }

Write-Host "`n[回读验证]"
$g = Invoke-Api @('base', '+record-get', '--as', 'user', '--base-token', $BaseToken,
                  '--table-id', $TableId, '--record-id', $RecordId, '--format', 'json')
$cells = [ordered]@{}
$flds = @($g.data.fields); $row = @(@($g.data.data)[0])
for ($i = 0; $i -lt $flds.Count; $i++) { $cells[$flds[$i]] = if ($i -lt $row.Count) { $row[$i] } else { $null } }

$ok = $true
foreach ($t in $Targets) {
    $cell = @($cells[$t.field] | Where-Object { $_ })
    $leaf = Split-Path -Leaf $t.path
    $size = (Get-Item -LiteralPath $t.path).Length
    $exact = @($cell | Where-Object { $_.name -eq $leaf -and [int64]$_.size -eq $size })
    $state = if ($exact.Count -eq 1 -and $cell.Count -eq 1) { '匹配且唯一' } else { '**异常**' }
    $names = @($cell | ForEach-Object { "$($_.name)($($_.size))" })
    Write-Host ("  {0,-14}: {1}（格内 {2} 件: {3}）" -f $t.field, $state, $cell.Count, ($names -join ', '))
    if ($exact.Count -ne 1 -or $cell.Count -ne 1) { $ok = $false }
}
Write-Host ("`n结论：{0}" -f $(if ($ok) { '三个附件均已上传且格内唯一' } else { '**存在不一致**' }))
if (-not $ok) { exit 1 }
