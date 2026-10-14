[CmdletBinding()]
param([Parameter(Mandatory)][string]$WorkspaceRoot, [Parameter(Mandatory)][string]$OutputPath)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $OutputPath
New-Item -ItemType Directory -Force -Path $root | Out-Null
$runner = Join-Path $PSScriptRoot 'run_tests.ps1'
$reports = @()
$commitEvidence = [ordered]@{}
try {
    $shells = @(
        @{ Name = 'windows-powershell-5.1'; Command = (Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'); Major = 5; Minor = 1 },
        @{ Name = 'powershell-7'; Command = 'C:\Program Files\PowerShell\7\pwsh.exe'; Major = 7; Minor = -1 }
    )
    foreach ($shell in $shells) {
        $command = Get-Command $shell.Command -ErrorAction Stop
        $shellCommand = $command.Source
        $version = & $shellCommand -NoLogo -NoProfile -NonInteractive -Command '$PSVersionTable.PSVersion.ToString()'
        if ($LASTEXITCODE -ne 0 -or ([version]$version).Major -ne $shell.Major -or ($shell.Minor -ge 0 -and ([version]$version).Minor -ne $shell.Minor)) { throw ('Required shell unavailable: ' + $shell.Name) }
        $directory = Join-Path $root $shell.Name
        New-Item -ItemType Directory -Force -Path $directory | Out-Null
        $resultPath = Join-Path $directory 'result.json'
        # A candidate is allowed to write to the error stream. Windows PowerShell
        # 5.1 turns a redirected child process' stderr into a terminating
        # RemoteException in this scope, which would abort the whole matrix before
        # any per-test evidence is written. Keep the redirect but run the child
        # under 'Continue'; the exit code and result.json below stay the only
        # acceptance criteria for the runtime.
        $savedPreference = $ErrorActionPreference
        try {
            $ErrorActionPreference = 'Continue'
            & $shellCommand -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $runner -WorkspaceRoot $WorkspaceRoot -OutputPath $resultPath *> (Join-Path $directory 'runner.log')
            $code = $LASTEXITCODE
        }
        finally {
            $ErrorActionPreference = $savedPreference
        }
        if ($code -ne 0 -or -not (Test-Path -LiteralPath $resultPath)) { throw ('Runtime matrix failed: ' + $shell.Name) }
        $report = Get-Content -LiteralPath $resultPath -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($report.status -eq 'INVALID') { throw ('Runtime matrix invalid: ' + $shell.Name) }
        $probePath = Join-Path $directory 'atomic-commit-evidence.json'
        if (Test-Path -LiteralPath $probePath) {
            $commitEvidence[$shell.Name] = Get-Content -LiteralPath $probePath -Raw -Encoding UTF8 | ConvertFrom-Json
            $commitEvidence | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath (Join-Path $root 'atomic-commit-evidence.json') -Encoding UTF8
        }
        $reports += $report
    }
    . (Join-Path $PSScriptRoot 'merge_runtime_reports.ps1')
    $rubric = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'rubric.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    $result = Merge-RuntimeReports -Reports $reports -Rubric $rubric
    $checks = @($result.checks)
    $failed = @($checks | Where-Object { -not $_.passed })
    $cases = foreach ($check in $checks) {
        $id = [Security.SecurityElement]::Escape([string]$check.test_id)
        $category = [Security.SecurityElement]::Escape([string]$check.category)
        $failure = if ($check.passed) { '' } else { '<failure message="' + [Security.SecurityElement]::Escape([string]$check.failure_reason) + '" />' }
        '<testcase name="' + $id + '" classname="' + $category + '">' + $failure + '</testcase>'
    }
    $xml = '<testsuite tests="' + $checks.Count + '" failures="' + $failed.Count + '">' + ($cases -join '') + '</testsuite>'
    [IO.File]::WriteAllText((Join-Path $root 'junit.xml'), $xml, (New-Object Text.UTF8Encoding($false)))
    $result | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $OutputPath -Encoding UTF8
    exit 0
} catch {
    @{task_id='windows-powershell-ads-001';status='INVALID';reward=0.0;programmatic_score=0.0;
      resolved=$false;invalid_reason=$_.Exception.Message;runtime_matrix_complete=$false} |
        ConvertTo-Json | Set-Content -LiteralPath $OutputPath -Encoding UTF8
    exit 2
}
