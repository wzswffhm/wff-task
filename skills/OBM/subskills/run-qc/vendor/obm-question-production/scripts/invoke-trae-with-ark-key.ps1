[CmdletBinding(PositionalBinding = $false)]
param(
    [Parameter(Mandatory = $true)]
    [string[]]$TraeArguments,

    [string]$SecretFile = 'C:\Users\Administrator\.config\obm\ark-agent-plan.dpapi',

    [string]$TraeExecutable = 'C:\Users\Administrator\.local\bin\trae-cli.exe'
)

$ErrorActionPreference = 'Stop'

if (-not (Test-Path -LiteralPath $SecretFile -PathType Leaf)) {
    throw "Encrypted Agent Plan key not found: $SecretFile"
}
if (-not (Test-Path -LiteralPath $TraeExecutable -PathType Leaf)) {
    throw "Trae CLI not found: $TraeExecutable"
}

$cipher = (Get-Content -LiteralPath $SecretFile -Raw -Encoding ASCII).Trim()
if ([string]::IsNullOrWhiteSpace($cipher)) {
    throw 'Encrypted Agent Plan key file is empty.'
}

$secure = $cipher | ConvertTo-SecureString
$pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
$previousArk = [Environment]::GetEnvironmentVariable('ARK_API_KEY', 'Process')
$previousDoubao = [Environment]::GetEnvironmentVariable('DOUBAO_API_KEY', 'Process')

try {
    $plain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    [Environment]::SetEnvironmentVariable('ARK_API_KEY', $plain, 'Process')
    [Environment]::SetEnvironmentVariable('DOUBAO_API_KEY', $plain, 'Process')
    $plain = $null

    & $TraeExecutable @TraeArguments
    $exitCode = $LASTEXITCODE
    if ($null -eq $exitCode) {
        $exitCode = 0
    }
    exit $exitCode
}
finally {
    [Environment]::SetEnvironmentVariable('ARK_API_KEY', $previousArk, 'Process')
    [Environment]::SetEnvironmentVariable('DOUBAO_API_KEY', $previousDoubao, 'Process')
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
}
