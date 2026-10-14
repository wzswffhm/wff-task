[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$WorkspaceRoot)
$ErrorActionPreference = 'Stop'

$source = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot 'workspace'))
$target = [IO.Path]::GetFullPath($WorkspaceRoot)
$targetPrefix = $target.TrimEnd('\', '/') + [IO.Path]::DirectorySeparatorChar
$sourcePrefix = $source.TrimEnd('\', '/') + [IO.Path]::DirectorySeparatorChar
if ($target -eq [IO.Path]::GetPathRoot($target) -or
    $target.Equals($source, [StringComparison]::OrdinalIgnoreCase) -or
    $source.StartsWith($targetPrefix, [StringComparison]::OrdinalIgnoreCase) -or
    $target.StartsWith($sourcePrefix, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Restore target must be a separate run workspace.'
}
if (-not (Test-Path -LiteralPath (Join-Path $source 'Lib\subprocess.py') -PathType Leaf)) {
    throw 'Pristine subprocess source is missing.'
}

$marker = Join-Path $target '.windows-subprocess-reader-error-005-workspace'
$markerValue = 'windows-subprocess-reader-error-005:0.7.0'
if (Test-Path -LiteralPath $target) {
    if (-not (Test-Path -LiteralPath $target -PathType Container)) {
        throw 'Restore target is not a directory.'
    }
    $contents = @(Get-ChildItem -LiteralPath $target -Force)
    if ($contents.Count -gt 0 -and
        (-not (Test-Path -LiteralPath $marker -PathType Leaf) -or
         (Get-Content -LiteralPath $marker -Raw).Trim() -ne $markerValue)) {
        throw 'Refusing to overwrite an unmarked workspace.'
    }
    $contents | ForEach-Object { Remove-Item -LiteralPath $_.FullName -Recurse -Force }
} else {
    New-Item -ItemType Directory -Path $target -Force | Out-Null
}
Get-ChildItem -LiteralPath $source -Force | Copy-Item -Destination $target -Recurse -Force
Set-Content -LiteralPath $marker -Value $markerValue -NoNewline
