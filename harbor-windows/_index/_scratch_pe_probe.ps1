# 临时调研脚本：验证 Windows MapFileAndCheckSumW 可用性，并挑选带正确校验和的真实 PE 素材。
# 不进入题包，仅用于选题取证。
$ErrorActionPreference = 'Stop'

Add-Type -Namespace WffProbe -Name ImgHlp -MemberDefinition @'
[DllImport("imagehlp.dll", CharSet = CharSet.Unicode, SetLastError = true)]
public static extern uint MapFileAndCheckSumW(string Filename, out uint HeaderSum, out uint CheckSum);
'@

function Get-RecordedCheckSum([string]$path) {
    $fs = [System.IO.File]::OpenRead($path)
    try {
        $br = New-Object System.IO.BinaryReader($fs)
        $fs.Position = 0x3C
        $eLfanew = $br.ReadInt32()
        $fs.Position = $eLfanew + 4 + 20   # PE sig + FILE_HEADER
        $magic = $br.ReadUInt16()
        $fs.Position = $eLfanew + 4 + 20 + 64
        $sum = $br.ReadUInt32()
        return [pscustomobject]@{ Magic = $magic; Recorded = $sum }
    } finally { $fs.Dispose() }
}

$candidates = Get-ChildItem 'C:\Windows\System32' -Filter *.dll -File -ErrorAction SilentlyContinue |
    Where-Object { $_.Length -ge 12KB -and $_.Length -le 90KB }

$rows = New-Object System.Collections.ArrayList
foreach ($c in $candidates) {
    try {
        $hs = 0; $cs = 0
        $rc = [WffProbe.ImgHlp]::MapFileAndCheckSumW($c.FullName, [ref]$hs, [ref]$cs)
        if ($rc -ne 0) { continue }
        $info = Get-RecordedCheckSum $c.FullName
        [void]$rows.Add([pscustomobject]@{
                Name     = $c.Name
                Size     = $c.Length
                Magic    = ('0x{0:X}' -f $info.Magic)
                Recorded = $info.Recorded
                Computed = $cs
                Match    = ($info.Recorded -eq $cs)
            })
    } catch { }
}

Write-Output ("扫描候选数: {0}" -f $rows.Count)
Write-Output "=== 记录值非 0 且与 Windows API 计算值一致的样本 ==="
$rows | Where-Object { $_.Recorded -ne 0 -and $_.Match } | Sort-Object Size | Format-Table -AutoSize
Write-Output "=== 记录值为 0 的样本（前 10）==="
$rows | Where-Object { $_.Recorded -eq 0 } | Sort-Object Size | Select-Object -First 10 | Format-Table -AutoSize
