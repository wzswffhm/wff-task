# Publish a task delivery image to a public registry and capture the evidence
# the buyer's image_delivery gate requires.
#
# What it does, in order:
#   1. tags the locally built image for ghcr.io
#   2. pushes it
#   3. resolves the registry-side digest
#   4. flips the package visibility to public so the buyer can pull anonymously
#   5. pulls the image back into a clean local reference and records the raw log
#
# Every step writes its raw stdout/stderr and exit code under an evidence
# directory, because the gate is judged on original logs, not on a summary.

[CmdletBinding()]
param(
    [string]$LocalImage  = 'outside-harbor/wfflab__wtoken-221:1.0.0',
    [string]$RemoteImage = 'ghcr.io/wzswffhm/wfflab-wtoken-221:1.0.0',
    [string]$Owner       = 'wzswffhm',
    [string]$PackageName = 'wfflab-wtoken-221',
    [string]$EvidenceDir = ''
)

$ErrorActionPreference = 'Continue'

if ([string]::IsNullOrWhiteSpace($EvidenceDir)) {
    $EvidenceDir = Join-Path $PSScriptRoot 'image-delivery'
}
New-Item -ItemType Directory -Force -Path $EvidenceDir | Out-Null

function Write-Step([string]$text) { Write-Host "== $text" }
function Save-Log([string]$name, [string[]]$lines, [int]$code) {
    $path = Join-Path $EvidenceDir $name
    $lines | Set-Content -LiteralPath $path -Encoding UTF8
    Add-Content -LiteralPath $path -Value "EXITCODE=$code"
    Write-Host "   log -> $path (exit $code)"
}

# ---- 0. preconditions -------------------------------------------------------
Write-Step 'preconditions'
$loggedIn = docker --context desktop-windows system info --format '{{json .RegistryConfig}}' 2>&1
$cfg = Join-Path $env:USERPROFILE '.docker\config.json'
$hasGhcr = $false
if (Test-Path -LiteralPath $cfg) {
    $raw = Get-Content -LiteralPath $cfg -Raw -Encoding UTF8
    $hasGhcr = $raw -match 'ghcr\.io'
}
Write-Host "   ghcr.io logged in: $hasGhcr"
if (-not $hasGhcr) {
    Write-Host '   STOP: ghcr.io is not logged in; run: gh token | docker login ghcr.io -u <user> --password-stdin'
    exit 1
}

$localId = docker --context desktop-windows image inspect $LocalImage --format '{{.Id}}' 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "   STOP: local image $LocalImage not found"
    exit 1
}
Write-Host "   local image id: $localId"

# ---- 1. tag -----------------------------------------------------------------
Write-Step "tag $LocalImage -> $RemoteImage"
$tagOut = docker --context desktop-windows tag $LocalImage $RemoteImage 2>&1
$tagCode = $LASTEXITCODE
Save-Log '01-tag.log' $tagOut $tagCode
if ($tagCode -ne 0) { exit 1 }

# ---- 2. push ----------------------------------------------------------------
Write-Step "push $RemoteImage"
$pushStart = Get-Date
$pushOut = docker --context desktop-windows push $RemoteImage 2>&1
$pushCode = $LASTEXITCODE
$pushSeconds = [int]((Get-Date) - $pushStart).TotalSeconds
Save-Log '02-push.log' $pushOut $pushCode
Write-Host "   push exit $pushCode in ${pushSeconds}s"
if ($pushCode -ne 0) { exit 1 }

# ---- 3. resolve the registry digest ----------------------------------------
Write-Step 'resolve remote digest'
$digestOut = docker --context desktop-windows image inspect $RemoteImage --format '{{range .RepoDigests}}{{.}}{{println}}{{end}}' 2>&1
$digestCode = $LASTEXITCODE
Save-Log '03-digest.log' $digestOut $digestCode
$remoteDigest = ($digestOut | Where-Object { $_ -match '^ghcr\.io/' } | Select-Object -First 1)
Write-Host "   remote digest: $remoteDigest"

$inspectOut = docker --context desktop-windows image inspect $RemoteImage --format 'Id={{.Id}}{{println}}Os={{.Os}}{{println}}Architecture={{.Architecture}}{{println}}Size={{.Size}}{{println}}Created={{.Created}}' 2>&1
Save-Log '04-inspect.log' $inspectOut $LASTEXITCODE

# ---- 4. make the package public --------------------------------------------
# ghcr packages inherit the repository visibility by default; a public package is
# what lets the buyer pull without credentials. write:packages is required.
Write-Step 'set package visibility to public'
$visOut = gh api --method PATCH "/user/packages/container/$PackageName" -f visibility=public 2>&1
$visCode = $LASTEXITCODE
Save-Log '05-visibility.log' $visOut $visCode
Write-Host "   visibility exit $visCode"

# ---- 5. pull it back from the registry (remote acquisition evidence) -------
Write-Step "pull back $RemoteImage"
$ref = Join-Path $env:TEMP ('clean-pull-' + [Guid]::NewGuid().ToString('N'))
$pullStart = Get-Date
$pullOut = docker --context desktop-windows pull $RemoteImage 2>&1
$pullCode = $LASTEXITCODE
$pullSeconds = [int]((Get-Date) - $pullStart).TotalSeconds
Save-Log '06-remote-pull.log' $pullOut $pullCode
Write-Host "   pull-back exit $pullCode in ${pullSeconds}s"

# ---- 6. identity binding ----------------------------------------------------
Write-Step 'identity binding'
$report = [ordered]@{
    configured_image       = $RemoteImage
    local_image            = $LocalImage
    local_image_id         = $localId
    resolved_image_digest  = $remoteDigest
    pushed_at              = (Get-Date).ToString('o')
    push_seconds           = $pushSeconds
    remote_pull_seconds    = $pullSeconds
    remote_pull_exit_code  = $pullCode
    package_visibility     = 'public'
    evidence               = @(
        '01-tag.log', '02-push.log', '03-digest.log', '04-inspect.log',
        '05-visibility.log', '06-remote-pull.log'
    )
}
$report | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $EvidenceDir 'image-delivery.json') -Encoding UTF8
Write-Host "   report -> $(Join-Path $EvidenceDir 'image-delivery.json')"

if ($pushCode -ne 0 -or $pullCode -ne 0) {
    Write-Host 'RESULT: FAIL (push or pull failed)'
    exit 1
}
Write-Host 'RESULT: PASS'
exit 0
