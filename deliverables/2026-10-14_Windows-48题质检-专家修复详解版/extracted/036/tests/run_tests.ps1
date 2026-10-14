[CmdletBinding()]
param([string]$WorkspaceRoot='C:\workspace',[string]$OutputRoot='C:\logs\verifier')
$ErrorActionPreference='Stop'
$script:VerifierStartedAt=[DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
[void][IO.Directory]::CreateDirectory($OutputRoot)
$fixture=Join-Path $OutputRoot 'fixtures';[void][IO.Directory]::CreateDirectory($fixture)
$script:RunSub='Software\RegistryPatchBench\'+[Guid]::NewGuid().ToString('N')
$script:Hive=[Microsoft.Win32.Registry]::CurrentUser
$script:Cases=[Collections.Generic.List[object]]::new()
Add-Type -TypeDefinition 'public sealed class BenchAssertion : System.Exception { public BenchAssertion(string message) : base(message) {} }'
Add-Type -Path (Join-Path $PSScriptRoot 'RegistryAclGuard.cs')
function Demand([bool]$ok,[string]$message){if(-not $ok){throw [BenchAssertion]::new($message)}}
function Op($name,$action='Set',$type='String',$value='new',$path='Profile'){
    $o=@{Path=$path;Name=$name;Action=$action};if($action -ne 'Delete'){$o.Type=$type;$o.Value=$value};return $o
}
function Read-Val($name,$path='Profile'){
    $k=$Hive.OpenSubKey($script:CaseSub+'\'+$path)
    if($path -eq ''){$k=$Hive.OpenSubKey($script:CaseSub)}
    try{
        $actual=$null;foreach($n in $k.GetValueNames()){if([StringComparer]::OrdinalIgnoreCase.Equals($n,$name)){$actual=$n;break}}
        if($null -eq $actual){return @{Exists=$false}}
        return @{Exists=$true;Kind=$k.GetValueKind($actual).ToString();Data=$k.GetValue($actual,$null,[Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames)}
    }finally{if($k){$k.Dispose()}}
}
function Snapshot {
    $k=$Hive.OpenSubKey($script:CaseSub+'\Profile')
    try{$data=[ordered]@{};foreach($n in ($k.GetValueNames()|Sort-Object)){$data[$n]=[ordered]@{Kind=$k.GetValueKind($n).ToString();Data=$k.GetValue($n,$null,[Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames)}};return $data|ConvertTo-Json -Depth 8 -Compress}finally{$k.Dispose()}
}
function Run-Patch($operations,[switch]$Preview,[switch]$Atomic,$Document=$null,$Raw=$null,$ReportTarget=$null){
    $patchFile=Join-Path $script:CaseDir ('patch-'+[Guid]::NewGuid().ToString('N')+'.json')
    $reportFile=if($ReportTarget){$ReportTarget}else{Join-Path $script:CaseDir ('report-'+[Guid]::NewGuid().ToString('N')+'.json')}
    if($null -eq $Document){$Document=@{Root=('HKCU:\'+$script:CaseSub);Operations=@($operations)}}
    if($null -ne $Raw){[IO.File]::WriteAllText($patchFile,$Raw)}else{$Document|ConvertTo-Json -Depth 15|Set-Content -LiteralPath $patchFile -Encoding utf8}
    $args=@('-NoProfile','-File',(Join-Path $WorkspaceRoot 'RegistryPatchApplier.ps1'),'-PatchPath',$patchFile,'-ReportPath',$reportFile)
    if($Preview){$args+='-Preview'};if($Atomic){$args+='-Atomic'}
    $psi=[Diagnostics.ProcessStartInfo]::new((Get-Command pwsh -ErrorAction Stop).Source)
    $psi.UseShellExecute=$false;$psi.RedirectStandardOutput=$true;$psi.RedirectStandardError=$true
    foreach($arg in $args){$psi.ArgumentList.Add([string]$arg)}
    $process=[Diagnostics.Process]::Start($psi)
    $stdout=$process.StandardOutput.ReadToEndAsync();$stderr=$process.StandardError.ReadToEndAsync()
    if(-not $process.WaitForExit(45000)){$process.Kill($true);$process.WaitForExit();throw 'Candidate subprocess timed out; execution INVALID'}
    $code=$process.ExitCode;$output=$stdout.GetAwaiter().GetResult()+$stderr.GetAwaiter().GetResult();$process.Dispose()
    $output|Out-String|Add-Content -LiteralPath (Join-Path $script:CaseDir 'candidate-output.txt') -Encoding utf8
    Write-Output ('CANDIDATE exit={0} patch={1} report={2}' -f $code,[IO.Path]::GetFileName($patchFile),[IO.Path]::GetFileName($reportFile)) | Out-Host
    $report=$null
    if(Test-Path -LiteralPath $reportFile -PathType Leaf){try{$report=Get-Content -LiteralPath $reportFile -Raw -Encoding utf8|ConvertFrom-Json}catch{}}
    return @{Code=$code;Report=$report}
}
function Check-Report($r,[int]$code,[string]$status,[int]$count,[int]$applied,[int]$failed,[int]$rolled=0){
    Demand ($r.Code -eq $code) "Exit code expected $code, got $($r.Code)"
    Demand ($null -ne $r.Report) 'JSON report missing or invalid'
    $j=$r.Report
    Demand ($j.Status -ceq $status -and $j.Processed -eq $count -and $j.Applied -eq $applied -and $j.Failed -eq $failed -and $j.RolledBack -eq $rolled) 'Report summary mismatch'
    Demand (@($j.Items).Count -eq $count) 'Report item count mismatch'
    foreach($item in $j.Items){foreach($f in 'Path','Name','Action','Status','Changed'){Demand ($item.PSObject.Properties.Name -contains $f) "Missing field $f"};if($item.Status -in 'Failed','RollbackFailed'){Demand (-not [string]::IsNullOrWhiteSpace($item.Error)) 'Missing item Error'}}
}
function Case([string]$id,[string]$group,[scriptblock]$body){
    $watch=[Diagnostics.Stopwatch]::StartNew();Write-Host "CASE BEGIN id=$id group=$group"
    $script:CaseSub=$RunSub+'\'+$id;$script:CaseDir=Join-Path $fixture $id;[void][IO.Directory]::CreateDirectory($CaseDir)
    # Fixture failures are infrastructure errors and are deliberately outside the candidate assertion catch.
    $rk=$Hive.CreateSubKey($CaseSub);$rk.SetValue('RootValue','root',[Microsoft.Win32.RegistryValueKind]::String);$rk.Dispose()
    foreach($p in 'Profile','[Literal]'){
        $k=$Hive.CreateSubKey($CaseSub+'\'+$p)
        $k.SetValue('text','old',[Microsoft.Win32.RegistryValueKind]::String)
        $k.SetValue('env','%TEMP%\unchanged',[Microsoft.Win32.RegistryValueKind]::ExpandString)
        $k.SetValue('number',[int]7,[Microsoft.Win32.RegistryValueKind]::DWord)
        $k.SetValue('bytes',[byte[]](0,255,128),[Microsoft.Win32.RegistryValueKind]::Binary)
        $k.SetValue('names',[string[]]@('one','two'),[Microsoft.Win32.RegistryValueKind]::MultiString)
        $k.SetValue('wide',[long]::MaxValue,[Microsoft.Win32.RegistryValueKind]::QWord)
        $k.SetValue('','default',[Microsoft.Win32.RegistryValueKind]::String)
        $k.SetValue('KEEP','untouched',[Microsoft.Win32.RegistryValueKind]::String);$k.Dispose()
    }
    $status='PASS';$details='All observable assertions passed.'
    try{& $body}catch [BenchAssertion]{$status='FAIL';$details=$_.Exception.Message}
    $watch.Stop();Write-Host "CASE END id=$id group=$group status=$status duration_ms=$($watch.ElapsedMilliseconds) details=$details"
    $Cases.Add(@{id=$id;group=$group;classification='Explicit';required=$true;status=$status;details=$details;duration_ms=$watch.ElapsedMilliseconds})
    $Hive.DeleteSubKeyTree($CaseSub,$false)
}
try{
Case 'ordinary-typed-write' 'F2P' {
    $r=Run-Patch @((Op 'text'),(Op 'number' 'Set' 'DWord' 23),(Op 'wide' 'Set' 'QWord' '-9223372036854775808'));Check-Report $r 0 'Succeeded' 3 3 0
    Demand ((Read-Val 'number').Kind -eq 'DWord' -and (Read-Val 'number').Data -eq 23 -and (Read-Val 'wide').Data -eq [long]::MinValue) 'Typed registry write mismatch'
}
Case 'ordinary-sequence-and-assert' 'F2P' {
    $r=Run-Patch @((Op 'text'),(Op 'TEXT' 'Assert' 'String' 'new'),(Op 'text' 'Delete'));Check-Report $r 0 'Succeeded' 3 2 0
    Demand (-not (Read-Val 'text').Exists) 'Ordinary duplicate target sequence mismatch'
}
Case 'ordinary-missing-continues' 'F2P' {
    $r=Run-Patch @((Op 'no' 'Set' 'String' 'bad' 'Missing'),(Op 'text'));Check-Report $r 2 'Failed' 2 1 1
    Demand ((Read-Val 'text').Data -ceq 'new') 'Later operation did not continue'
}
Case 'ordinary-case-and-literal' 'F2P' {
    $r=Run-Patch @((Op 'TEXT' 'Set' 'String' '中文[]' 'pRoFiLe'),(Op 'text' 'Set' 'String' 'literal' '[Literal]'));Check-Report $r 0 'Succeeded' 2 2 0
    Demand ((Read-Val 'text').Data -ceq '中文[]' -and (Read-Val 'text' '[Literal]').Data -ceq 'literal') 'Literal or case lookup mismatch'
}
Case 'no-change-and-preservation' 'P2P' {
    $before=Snapshot;$r=Run-Patch @((Op 'text' 'Set' 'String' 'old'),(Op 'missing' 'Delete'),(Op 'text' 'Assert' 'String' 'old'));Check-Report $r 0 'Succeeded' 3 0 0
    Demand ((Snapshot) -ceq $before) 'Unchanged operations altered state'
}
Case 'input-validation-before-write' 'P2P' {
    $r=Run-Patch @((Op 'text'),(Op 'bad' 'Set' 'Binary' @(0,256)));Check-Report $r 3 'Failed' 0 0 1
    Demand ((Read-Val 'text').Data -ceq 'old') 'Malformed later input applied earlier operation'
}
Case 'invalid-root-and-json' 'P2P' {
    $r=Run-Patch @() -Document @{Root='HKLM:\Software';Operations=@()};Check-Report $r 3 'Failed' 0 0 1
    $r=Run-Patch @() -Raw '{oops';Check-Report $r 3 'Failed' 0 0 1
}
Case 'ordinary-empty-and-default' 'F2P' {
    $r=Run-Patch @((Op '' 'Set' 'String' ''),(Op 'bytes' 'Set' 'Binary' @()),(Op 'names' 'Set' 'MultiString' @()));Check-Report $r 0 'Succeeded' 3 3 0
    Demand ((Read-Val '').Data -ceq '' -and (Read-Val 'bytes').Data.Length -eq 0 -and (Read-Val 'names').Data.Length -eq 0) 'Empty/default value mismatch'
}
Case 'ordinary-unrelated-state' 'F2P' {
    $r=Run-Patch @((Op 'text'));Check-Report $r 0 'Succeeded' 1 1 0
    Demand ((Read-Val 'KEEP').Data -ceq 'untouched' -and (Read-Val 'env').Data -ceq '%TEMP%\unchanged' -and (Read-Val 'bytes').Data.Length -eq 3) 'Unmentioned value changed'
}
Case 'preview-set-delete' 'P2P' {
    $before=Snapshot;$r=Run-Patch @((Op 'text'),(Op 'bytes' 'Delete')) -Preview;Check-Report $r 0 'Previewed' 2 0 0
    Demand ($r.Report.Items[0].Status -eq 'WouldSet' -and $r.Report.Items[1].Status -eq 'WouldDelete' -and -not $r.Report.Items[0].Changed) 'Preview statuses incorrect'
    Demand ((Snapshot) -ceq $before) 'Preview changed registry'
}
Case 'preview-begins-from-initial-state' 'P2P' {
    $r=Run-Patch @((Op 'text'),(Op 'TEXT' 'Assert' 'String' 'old')) -Preview;Check-Report $r 0 'Previewed' 2 0 0
    Demand ($r.Report.Items[1].Status -eq 'AssertPassed' -and (Read-Val 'text').Data -ceq 'old') 'Preview simulated earlier Set incorrectly'
}
Case 'preview-missing-and-assert-failure' 'P2P' {
    $before=Snapshot;$r=Run-Patch @((Op 'text' 'Assert' 'String' 'bad'),(Op 'x' 'Delete' 'String' '' 'Missing'),(Op 'number' 'Set' 'DWord' 123)) -Preview;Check-Report $r 2 'Failed' 3 0 2
    Demand ((Snapshot) -ceq $before) 'Failed preview mutated state'
}
Case 'preview-atomic-is-readonly' 'P2P' {
    $before=Snapshot;$r=Run-Patch @((Op '' 'Delete'),(Op 'env' 'Set' 'ExpandString' '%USERNAME%')) -Preview -Atomic;Check-Report $r 0 'Previewed' 2 0 0
    Demand ((Snapshot) -ceq $before) 'Atomic preview changed registry'
}
Case 'atomic-preflight-all-items' 'F2P' {
    $before=Snapshot;$r=Run-Patch @((Op 'text'),(Op 'x' 'Set' 'String' 'bad' 'Missing'),(Op 'bytes' 'Delete')) -Atomic;Check-Report $r 2 'Failed' 3 0 1
    Demand (($r.Report.Items.Status -join ',') -eq 'Skipped,Failed,Skipped' -and (Snapshot) -ceq $before) 'Atomic preflight wrote or omitted items'
}
Case 'atomic-rollback-set-delete-create' 'F2P' {
    $before=Snapshot;$r=Run-Patch @((Op 'text'),(Op 'bytes' 'Delete'),(Op 'brandnew'),(Op 'number' 'Assert' 'DWord' 999),(Op 'names' 'Delete')) -Atomic;Check-Report $r 2 'Failed' 5 0 1 3
    Demand ((Snapshot) -ceq $before -and $r.Report.Items[4].Status -eq 'Skipped') 'Rollback did not restore exact batch before-image'
}
Case 'atomic-rollback-multistring-binary' 'F2P' {
    $before=Snapshot;$r=Run-Patch @((Op 'bytes' 'Set' 'Binary' @(9,8)),(Op 'names' 'Set' 'MultiString' @('z')),(Op 'number' 'Assert' 'DWord' 8)) -Atomic;Check-Report $r 2 'Failed' 3 0 1 2
    Demand ((Snapshot) -ceq $before) 'Array rollback altered type, elements, or order'
}
Case 'atomic-rollback-default-expandstring' 'F2P' {
    $before=Snapshot;$r=Run-Patch @((Op '' 'Delete'),(Op 'env' 'Set' 'String' 'expanded?'),(Op 'number' 'Assert' 'DWord' 8)) -Atomic;Check-Report $r 2 'Failed' 3 0 1 2
    Demand ((Snapshot) -ceq $before) 'Default or ExpandString before-image not restored'
}
Case 'atomic-rollback-width-and-kind' 'F2P' {
    $before=Snapshot;$r=Run-Patch @((Op 'wide' 'Set' 'DWord' 4294967295),(Op 'number' 'Set' 'String' 'different-kind'),(Op 'text' 'Assert' 'String' 'OLD')) -Atomic;Check-Report $r 2 'Failed' 3 0 1 2
    Demand ((Snapshot) -ceq $before) 'Numeric width/type before-image not restored'
}
Case 'atomic-unchanged-is-not-rolledback' 'F2P' {
    $r=Run-Patch @((Op 'text' 'Set' 'String' 'old'),(Op 'wide' 'Assert' 'QWord' '9223372036854775807'),(Op 'number' 'Set' 'DWord' 20),(Op 'env' 'Assert' 'String' '%TEMP%\unchanged')) -Atomic;Check-Report $r 2 'Failed' 4 0 1 1
    Demand (($r.Report.Items.Status -join ',') -eq 'Unchanged,AssertPassed,RolledBack,Failed') 'No-op or assertion misreported as rolled back'
}
Case 'atomic-duplicate-casefold' 'P2P' {
    $before=Snapshot;$r=Run-Patch @((Op 'text'),(Op 'TEXT' 'Delete' 'String' '' 'profile')) -Atomic;Check-Report $r 3 'Failed' 0 0 1
    Demand ((Snapshot) -ceq $before) 'Duplicate target was applied'
}
Case 'preview-atomic-duplicate-default' 'P2P' {
    $r=Run-Patch @((Op ''),(Op '' 'Delete' 'String' '' 'profile')) -Preview -Atomic;Check-Report $r 3 'Failed' 0 0 1
}
Case 'atomic-success-counts' 'F2P' {
    $r=Run-Patch @((Op 'text'),(Op 'number' 'Assert' 'DWord' 7),(Op 'missing' 'Delete'),(Op 'env' 'Set' 'ExpandString' '%USERNAME%\x')) -Atomic;Check-Report $r 0 'Succeeded' 4 2 0
    Demand ((Read-Val 'env').Kind -eq 'ExpandString' -and (Read-Val 'env').Data -ceq '%USERNAME%\x') 'Atomic success expanded literal content'
}
Case 'preview-unsigned-dword-and-large-qword' 'P2P' {
    $r=Run-Patch @((Op 'number' 'Set' 'DWord' 4294967295),(Op 'wide' 'Assert' 'QWord' '9223372036854775807')) -Preview;Check-Report $r 0 'Previewed' 2 0 0
    Demand ((Read-Val 'number').Data -eq 7) 'DWORD preview mutated state'
}
Case 'preview-array-noops' 'P2P' {
    $before=Snapshot;$r=Run-Patch @((Op 'bytes' 'Set' 'Binary' @(0,255,128)),(Op 'names' 'Set' 'MultiString' @('one','two')),(Op 'env' 'Assert' 'ExpandString' '%TEMP%\unchanged')) -Preview;Check-Report $r 0 'Previewed' 3 0 0
    Demand (($r.Report.Items.Status -join ',') -eq 'Unchanged,Unchanged,AssertPassed' -and (Snapshot) -ceq $before) 'Array no-op preview mismatch'
}
Case 'root-key-and-report-order' 'F2P' {
    $r=Run-Patch @((Op 'RootValue' 'Set' 'String' 'changed' ''),(Op 'text'));Check-Report $r 0 'Succeeded' 2 2 0
    Demand ($r.Report.Items[0].Path -ceq '' -and $r.Report.Items[0].Name -ceq 'RootValue' -and (Read-Val 'RootValue' '').Data -ceq 'changed') 'Root-key or report order incorrect'
}
Case 'input-ranges-and-path-boundaries' 'P2P' {
    $boundaries=@(
        @{id='dword-underflow';op=(Op 'x' 'Set' 'DWord' -1)},
        @{id='dword-overflow';op=(Op 'x' 'Set' 'DWord' 4294967296)},
        @{id='qword-overflow';op=(Op 'x' 'Set' 'QWord' '9223372036854775808')},
        @{id='qword-underflow';op=(Op 'x' 'Set' 'QWord' '-9223372036854775809')},
        @{id='dot-segment';op=(Op 'x' 'Set' 'String' 'bad' '.\Profile')},
        @{id='dotdot-segment';op=(Op 'x' 'Set' 'String' 'bad' '..\Profile')},
        @{id='rooted-path';op=(Op 'x' 'Set' 'String' 'bad' '\Profile')},
        @{id='absolute-drive-path';op=(Op 'x' 'Set' 'String' 'bad' 'C:\Profile')},
        @{id='colon-path';op=(Op 'x' 'Set' 'String' 'bad' 'Profile:Stream')},
        @{id='nul-path';op=(Op 'x' 'Set' 'String' 'bad' ('Pro'+[char]0+'file'))},
        @{id='nul-value-name';op=(Op ('na'+[char]0+'me'))},
        @{id='multistring-nonstring';op=(Op 'x' 'Set' 'MultiString' @('ok',1))}
    )
    foreach($boundary in $boundaries){
        Write-Host "BOUNDARY BEGIN $($boundary.id)"
        $r=Run-Patch @((Op 'text'),$boundary.op);Check-Report $r 3 'Failed' 0 0 1
        Demand ((Read-Val 'text').Data -ceq 'old') "Invalid boundary $($boundary.id) mutated registry"
        Write-Host "BOUNDARY PASS $($boundary.id)"
    }
}
Case 'report-path-preflight' 'P2P' {
    $r=Run-Patch @((Op 'text')) -ReportTarget $CaseDir;Demand ($r.Code -eq 3 -and (Read-Val 'text').Data -ceq 'old') 'Unusable report path allowed a mutation'
}
Case 'atomic-empty-array-rollback' 'F2P' {
    $before=Snapshot;$r=Run-Patch @((Op 'bytes' 'Set' 'Binary' @()),(Op 'names' 'Set' 'MultiString' @()),(Op 'text' 'Assert' 'String' 'wrong')) -Atomic;Check-Report $r 2 'Failed' 3 0 1 2
    Demand ((Snapshot) -ceq $before) 'Empty array rollback mismatch'
}
Case 'atomic-preflight-unwritable' 'F2P' {
    $guard=[RegistryAclGuard]::new($CaseSub+'\[Literal]')
    try{
        $guard.DenyWrites();$before=Snapshot
        $r=Run-Patch @((Op 'text'),(Op 'text' 'Set' 'String' 'bad' '[Literal]'),(Op 'bytes' 'Delete')) -Atomic
        Check-Report $r 2 'Failed' 3 0 1
        Demand (($r.Report.Items.Status -join ',') -eq 'Skipped,Failed,Skipped' -and (Snapshot) -ceq $before -and (Read-Val 'text' '[Literal]').Data -ceq 'old') 'Atomic ACL preflight did not block the entire batch'
    }finally{$guard.Dispose()}
}
Case 'ordinary-access-denied-continues' 'F2P' {
    $guard=[RegistryAclGuard]::new($CaseSub+'\[Literal]')
    try{
        $guard.DenyWrites()
        $r=Run-Patch @((Op 'text' 'Set' 'String' 'bad' '[Literal]'),(Op 'text'))
        Check-Report $r 2 'Failed' 2 1 1
        Demand ((Read-Val 'text' '[Literal]').Data -ceq 'old' -and (Read-Val 'text').Data -ceq 'new') 'Ordinary ACL failure did not preserve denied value and continue'
    }finally{$guard.Dispose()}
}
Case 'atomic-rollback-access-denied' 'F2P' {
    # A native registry notification revokes future write access after the first actual Set.
    # Already-open handles can still roll back; both valid Windows outcomes are accepted.
    $holding=$Hive.CreateSubKey($CaseSub+'\Holding')
    $ops=[Collections.Generic.List[object]]::new();$ops.Add((Op 'text'))
    for($i=0;$i -lt 2048;$i++){$holding.SetValue("v$i",'unchanged',[Microsoft.Win32.RegistryValueKind]::String);$ops.Add((Op "v$i" 'Assert' 'String' 'unchanged' 'Holding'))}
    $holding.Dispose();$ops.Add((Op 'KEEP' 'Assert' 'String' 'mismatch'))
    $guard=[RegistryAclGuard]::new($CaseSub+'\Profile')
    try{
        $guard.AfterNextWrite();$r=Run-Patch $ops.ToArray() -Atomic;$guard.Stop()
        Demand ($guard.Applied) 'Candidate never made the required initial registry mutation'
        $state=Read-Val 'text'
        if($state.Data -ceq 'old'){
            Check-Report $r 2 'Failed' $ops.Count 0 1 1
            Demand ($r.Report.Items[0].Status -eq 'RolledBack' -and -not $r.Report.Items[0].Changed) 'Successful rollback was misreported'
        }else{
            Demand ($state.Data -ceq 'new') 'Failed rollback left unexpected data'
            Check-Report $r 2 'Failed' $ops.Count 1 2 0
            Demand ($r.Report.Items[0].Status -eq 'RollbackFailed' -and $r.Report.Items[0].Changed) 'Actual rollback failure was omitted or silently reported as success'
        }
        Demand ((Read-Val 'KEEP').Data -ceq 'untouched' -and (Read-Val 'bytes').Data.Length -eq 3) 'ACL rollback case changed unrelated values'
    }finally{$guard.Dispose()}
}

}finally{$Hive.DeleteSubKeyTree($RunSub,$false)}
$Cases|ConvertTo-Json -Depth 10|Set-Content -LiteralPath (Join-Path $OutputRoot 'cases.json') -Encoding utf8
& (Join-Path $PSScriptRoot 'aggregate_results.ps1') -Cases $Cases.ToArray() -OutputRoot $OutputRoot -StartedAt $script:VerifierStartedAt
exit $LASTEXITCODE
