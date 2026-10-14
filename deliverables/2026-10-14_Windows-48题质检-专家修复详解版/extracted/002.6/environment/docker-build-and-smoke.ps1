[CmdletBinding()]
param(
    [string]$TaskRoot,
    [string]$ImageTag = 'windows-powershell-ads:pilot-0.8.0',
    [switch]$ReferenceSolution
)

$ErrorActionPreference = 'Stop'
$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
if ([string]::IsNullOrWhiteSpace($TaskRoot)) {
    $TaskRoot = Split-Path -Parent $scriptRoot
}
if ($null -eq (Get-Command docker.exe -ErrorAction SilentlyContinue)) {
    throw 'docker.exe was not found on PATH.'
}

$info = (& docker info --format '{{.OSType}}' 2>&1 | Out-String).Trim()
if ($LASTEXITCODE -ne 0) { throw "Docker daemon is unavailable: $info" }
if ($info -ne 'windows') {
    throw "Docker is using '$info' containers. Switch Docker Desktop to Windows containers and retry."
}

$buildRoot = (Resolve-Path -LiteralPath $TaskRoot).Path
$temporaryRoot = $null
if ($ReferenceSolution) {
    $temporaryRoot = Join-Path $env:TEMP ('windows-powershell-ads-reference-' + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Force -Path $temporaryRoot | Out-Null
    Get-ChildItem -LiteralPath $buildRoot -Force | Copy-Item -Destination $temporaryRoot -Recurse -Force
    & powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File (Join-Path $temporaryRoot 'solution\solve.ps1') -TaskRoot $temporaryRoot
    if ($LASTEXITCODE -ne 0) { throw "Reference solution preparation failed with exit code $LASTEXITCODE." }
    $buildRoot = $temporaryRoot
    if ($ImageTag -eq 'windows-powershell-ads:pilot-0.8.0') { $ImageTag = 'windows-powershell-ads:reference-0.8.0' }
}

$dockerfile = Join-Path $buildRoot 'environment\Dockerfile'
if (-not (Test-Path -LiteralPath $dockerfile -PathType Leaf)) { throw "Dockerfile not found: $dockerfile" }
$oldBuildKit = $env:DOCKER_BUILDKIT
$env:DOCKER_BUILDKIT = '0'
try {
    & docker build --pull=false --no-cache -t $ImageTag -f $dockerfile $buildRoot
    if ($LASTEXITCODE -ne 0) { throw "Docker build failed with exit code $LASTEXITCODE." }

    $smokeArgs = @('run', '--rm', $ImageTag, 'powershell.exe', '-NoLogo', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File', 'C:\verification\docker-smoke.ps1')
    if (-not $ReferenceSolution) { $smokeArgs += '-EnvironmentOnly' }
    & docker @smokeArgs
    if ($LASTEXITCODE -ne 0) { throw "Docker smoke failed with exit code $LASTEXITCODE." }

    $image = & docker image inspect $ImageTag --format '{{.Id}} {{.Os}} {{.Architecture}}'
    [pscustomobject]@{
        status = 'DOCKER_BUILD_AND_SMOKE_OK'
        image = $ImageTag
        image_metadata = [string]$image
        docker_ostype = $info
        dockerfile = (Resolve-Path -LiteralPath $dockerfile).Path
        validation_mode = if ($ReferenceSolution) { 'reference-solution-functional' } else { 'container-environment' }
    } | ConvertTo-Json -Depth 5
}
finally {
    if ($null -eq $oldBuildKit) { Remove-Item Env:DOCKER_BUILDKIT -ErrorAction SilentlyContinue }
    else { $env:DOCKER_BUILDKIT = $oldBuildKit }
    if ($null -ne $temporaryRoot -and (Test-Path -LiteralPath $temporaryRoot)) {
        Remove-Item -LiteralPath $temporaryRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}
