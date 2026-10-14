param(
    [string]$Workspace = 'C:\testbed',
    [string]$Logs = 'C:\logs\verifier',
    [string]$Scratch = 'C:\bench-fixtures',
    [switch]$TrustedLocal
)
$ErrorActionPreference = 'Stop'
if (-not $TrustedLocal -and $env:WINBENCH_DISPOSABLE_CONTAINER -ne '1') {
    throw 'Untrusted evaluation requires a disposable Windows container; no host account changes allowed'
}
$runUser = $null
$accountCreated = $false
$exitCode = 4
New-Item -ItemType Directory -Path $Logs -Force | Out-Null
foreach ($name in @('reward.txt', 'reward.json', 'results.json', 'invalid.txt')) {
    $path = Join-Path $Logs $name
    if (Test-Path $path) { Remove-Item -LiteralPath $path -Force }
}
try {
    $csc = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
    if (-not (Test-Path $csc)) { throw 'Required Windows compiler missing' }
    $exe = Join-Path $Logs 'Verifier.exe'
    if (Test-Path $exe) { Remove-Item -LiteralPath $exe -Force }
    & $csc /nologo /codepage:65001 /langversion:5 /target:exe /platform:x64 /r:System.Web.Extensions.dll ('/out:' + $exe) (Join-Path $PSScriptRoot 'Verifier.cs') *> (Join-Path $Logs 'verifier-build.log')
    if ($LASTEXITCODE -ne 0) { throw 'Trusted verifier compilation failed' }
    if (-not $TrustedLocal) {
        $runUser = 'bench' + [Guid]::NewGuid().ToString('N').Substring(0, 10)
        $secret = New-Object byte[] 24
        $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
        $rng.GetBytes($secret)
        $rng.Dispose()
        $password = '[REDACTED]' + [Convert]::ToBase64String($secret)
        New-LocalUser -Name $runUser -Password (ConvertTo-SecureString $password -AsPlainText -Force) -AccountNeverExpires | Out-Null
        $accountCreated = $true
        Add-LocalGroupMember -Group 'Users' -Member $runUser
        Start-Service seclogon
        $trustedSids = @([Security.Principal.WindowsIdentity]::GetCurrent().User,
            [Security.Principal.SecurityIdentifier]::new('S-1-5-32-544'),
            [Security.Principal.SecurityIdentifier]::new('S-1-5-18'))
        foreach ($directory in @($Logs, $PSScriptRoot)) {
            $entries = @((Get-Item -LiteralPath $directory)) + @(Get-ChildItem -LiteralPath $directory -Recurse -Force)
            foreach ($entry in $entries) {
                if ($entry.PSIsContainer) { $acl = [Security.AccessControl.DirectorySecurity]::new() }
                else { $acl = [Security.AccessControl.FileSecurity]::new() }
                $acl.SetAccessRuleProtection($true, $false)
                foreach ($sid in $trustedSids) {
                    if ($entry.PSIsContainer) {
                        $rule = [Security.AccessControl.FileSystemAccessRule]::new($sid, [Security.AccessControl.FileSystemRights]::FullControl, ([Security.AccessControl.InheritanceFlags]::ContainerInherit -bor [Security.AccessControl.InheritanceFlags]::ObjectInherit), [Security.AccessControl.PropagationFlags]::None, [Security.AccessControl.AccessControlType]::Allow)
                    } else {
                        $rule = [Security.AccessControl.FileSystemAccessRule]::new($sid, [Security.AccessControl.FileSystemRights]::FullControl, [Security.AccessControl.AccessControlType]::Allow)
                    }
                    $acl.AddAccessRule($rule)
                }
                if ($entry.PSIsContainer) { [IO.Directory]::SetAccessControl($entry.FullName, $acl) }
                else { [IO.File]::SetAccessControl($entry.FullName, $acl) }
            }
        }
        New-Item -ItemType Directory -Path $Scratch, 'C:\bench-runner' -Force | Out-Null
        foreach ($directory in @($Workspace, $Scratch, 'C:\agenttmp', 'C:\bench-runner')) {
            $rights = if ($directory -eq $Workspace -or $directory -eq 'C:\bench-runner') { 'RX' } else { 'M' }
            & icacls.exe $directory /grant ($runUser + ':(OI)(CI)' + $rights) /T *> $null
            if ($LASTEXITCODE -ne 0) { throw 'Cannot grant fixture/tool access' }
        }
        $env:WINBENCH_USER = $runUser
        $env:WINBENCH_PASSWORD = [REDACTED]
        $env:WINBENCH_RECEIPT_DIR = $Logs
        $env:WINBENCH_GUARD = 'C:\bench-runner\ExecGuard.exe'
        & $csc /nologo /langversion:5 /target:exe /platform:x64 /r:System.Web.Extensions.dll ('/out:' + $env:WINBENCH_GUARD) (Join-Path $PSScriptRoot 'ExecGuard.cs') *> (Join-Path $Logs 'guard-build.log')
        if ($LASTEXITCODE -ne 0) { throw 'Execution guard compilation failed' }
        $probe = 'C:\bench-runner\GuardProbe.exe'
        & $csc /nologo /langversion:5 /target:exe /platform:x64 /r:System.Web.Extensions.dll ('/out:' + $probe) (Join-Path $PSScriptRoot 'GuardProbe.cs') *> (Join-Path $Logs 'guard-probe-build.log')
        if ($LASTEXITCODE -ne 0) { throw 'Guard probe compilation failed' }
        [IO.File]::WriteAllText((Join-Path $Logs 'private-canary.txt'), [Guid]::NewGuid().ToString('N'))
        $receiptPath = Join-Path $Logs 'guard-probe-receipt.json'
        $probeText = & $env:WINBENCH_GUARD $probe 'C:\agenttmp\unused-plan.json' $receiptPath 2> (Join-Path $Logs 'guard-probe-stderr.log')
        if ($LASTEXITCODE -ne 0 -or -not (Test-Path $receiptPath)) { throw 'Guard probe did not complete' }
        $receipt = Get-Content $receiptPath -Raw -Encoding UTF8 | ConvertFrom-Json
        $probeText | Set-Content (Join-Path $Logs 'guard-probe-stdout.log') -Encoding UTF8
        $probeResult = ($probeText -join "`n") | ConvertFrom-Json
        if ($receipt.validity -cne 'VALID' -or $receipt.exit_code -ne 0 -or $receipt.timed_out -or -not $receipt.job_cleanup_complete -or $receipt.active_processes_after_exit -lt 1) { throw 'Guard cannot reliably observe and clean child processes' }
        if (-not $probeResult.read_denied -or -not $probeResult.write_denied -or -not $probeResult.tests_denied) { throw 'Candidate can access trusted scoring assets' }
        if ($probeResult.candidate_sid -eq [Security.Principal.WindowsIdentity]::GetCurrent().User.Value) { throw 'Candidate and verifier share an identity' }
        if (Get-Process -Id $probeResult.child_pid -ErrorAction SilentlyContinue) { throw 'Guard left its probe child running' }
        if (Test-Path $probeResult.heartbeat) { Remove-Item -LiteralPath $probeResult.heartbeat -Force }
    }
    $buildExit = & (Join-Path $PSScriptRoot 'build-candidate.ps1') -Workspace $Workspace -Log (Join-Path $Logs 'candidate-build.log')
    $env:WINBENCH_CANDIDATE_BUILD = if ($buildExit -eq 0) { 'OK' } else { 'FAILED' }
    & $exe (Join-Path $Workspace 'bin\WinPublish.exe') (Join-Path $Logs 'results.json') $Scratch | Tee-Object -FilePath (Join-Path $Logs 'test.log')
    if ($LASTEXITCODE -ne 0) { throw 'Verifier reports INVALID execution' }
    $result = Get-Content -LiteralPath (Join-Path $Logs 'results.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    $manifest = Get-Content (Join-Path $PSScriptRoot 'required_testcases.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    $ids = @($manifest | ForEach-Object { $_.id })
    $actualIds = @($result.testcases | ForEach-Object { $_.id })
    if ($ids.Count -eq 0 -or @($ids | Select-Object -Unique).Count -ne $ids.Count -or $result.required.Count -ne $ids.Count -or $actualIds.Count -ne $ids.Count -or @($actualIds | Select-Object -Unique).Count -ne $ids.Count) { throw 'Required testcase count/uniqueness mismatch' }
    if (Compare-Object ($ids | Sort-Object) ($result.required | Sort-Object)) { throw 'Required testcase list changed' }
    if (Compare-Object ($ids | Sort-Object) ($actualIds | Sort-Object)) { throw 'Required testcase execution incomplete' }
    foreach ($case in $result.testcases) {
        $expected = @($manifest | Where-Object { $_.id -ceq $case.id })
        if ($expected.Count -ne 1 -or $case.group -cne $expected[0].group -or $case.status -cnotin @('PASS','FAIL')) { throw 'Invalid testcase group or terminal status' }
    }
    $expectedScore = if (@($result.testcases | Where-Object { $_.status -cne 'PASS' }).Count -eq 0) { 1 } else { 0 }
    if ($result.validity -cne 'VALID' -or -not ($result.score -is [int] -or $result.score -is [long]) -or $result.score -ne $expectedScore) { throw 'No valid complete binary score' }
    [IO.File]::WriteAllText((Join-Path $Logs 'reward.txt'), [string]$result.score, [Text.Encoding]::ASCII)
    $exitCode = 0
} catch {
    [IO.File]::WriteAllText((Join-Path $Logs 'invalid.txt'), $_.Exception.ToString(), [Text.Encoding]::UTF8)
    Write-Error $_ -ErrorAction Continue
} finally {
    Remove-Item Env:\WINBENCH_PASSWORD -ErrorAction SilentlyContinue
    if ($accountCreated) {
        try { Remove-LocalUser -Name $runUser -ErrorAction Stop }
        catch {
            [IO.File]::WriteAllText((Join-Path $Logs 'invalid.txt'), 'Isolated account cleanup failed')
            $exitCode = 4
        }
    }
    if ($exitCode -ne 0) { Remove-Item -LiteralPath (Join-Path $Logs 'reward.txt') -ErrorAction SilentlyContinue }
}
exit $exitCode


