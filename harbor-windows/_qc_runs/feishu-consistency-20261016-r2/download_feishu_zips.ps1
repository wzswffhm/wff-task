# Download current "作业压缩包" attachments for the 5 wff records (read-only).
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$Base = 'EsJebL8JJaf7g4sIbItcnMFgnvg'
$Table = 'tblRDxcGkblflMBA'
$ZipDir = 'C:\Users\Administrator\Desktop\wff-task\harbor-windows\_qc_runs\feishu-consistency-20261016-r2\zip'
New-Item -ItemType Directory -Force -Path $ZipDir | Out-Null

$Items = @(
    @{ rec = 'reczz28KwEOO3xHy'; tok = 'WRgRbLbrGoiZ7CxpCaKc6HaVnad'; name = 'wfflab__wsparse-215-v1.0.0-delivery.zip'; size = 54423465 },
    @{ rec = 'reczz28KQU8reW2k'; tok = 'RWLzbe64voPantxxB0kcEUBMnph'; name = 'wfflab__wvas-216-v1.0.0-delivery.zip'; size = 54420063 },
    @{ rec = 'reczz28MRVnWkD2v'; tok = 'KmH1bMZz4oAqSMxGGR0cbdGlnnb'; name = 'wfflab__wspawn-218-v1.0.0-delivery.zip'; size = 54511970 },
    @{ rec = 'reczz28N2IGu9XmA'; tok = 'SxwFblbU7oP9dfxGj4ucaMiGnJh'; name = 'wfflab__wcancel-219-v1.0.0-delivery.zip'; size = 54420405 },
    @{ rec = 'reczz28NUOrl6Foj'; tok = 'GQ2cbIazfovdVDx8r45ctJnYnRf'; name = 'wfflab__wciocp-220-v1.0.0-delivery.zip'; size = 54576334 }
)

Push-Location $ZipDir
foreach ($it in $Items) {
    if (Test-Path -LiteralPath $it.name) { Remove-Item -LiteralPath $it.name -Force }
    Write-Host ("[download] " + $it.name + " (expect " + $it.size + " B)")
    & lark-cli base +record-download-attachment --base-token $Base --table-id $Table `
        --record-id $it.rec --file-token $it.tok --output "./$($it.name)" --as user 2>&1 |
        Select-Object -Last 2 | ForEach-Object { Write-Host ("    " + $_) }
    $f = Get-Item -LiteralPath $it.name
    $h = (Get-FileHash -LiteralPath $it.name -Algorithm SHA256).Hash.ToLower()
    Write-Host ("  -> " + $f.Length + " B  sha256=" + $h)
    if ($f.Length -ne $it.size) { Write-Host "  [warn] size differs from feishu metadata" }
}
Pop-Location

Write-Host "[done]"
Get-ChildItem $ZipDir | Select-Object Name, Length | Format-Table -AutoSize
