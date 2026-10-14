function NG-BatchRegistrySnapshot([string]$CaseId) {
    $rows = @()
    foreach ($view in @('Registry64','Registry32')) {
        $root = [Microsoft.Win32.RegistryKey]::OpenBaseKey('LocalMachine',$view)
        try {
            $key = $root.OpenSubKey($env:EVIDENCE_MIRROR_REGISTRY_ROOT+'\Cases\'+$CaseId)
            if (-not $key) { $rows += "$view|ABSENT"; continue }
            try {
                $rows += "$view|PRESENT"
                foreach ($name in @($key.GetValueNames() | Sort-Object)) {
                    $value = $key.GetValue($name,$null,[Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames)
                    $rows += ($view+'|'+$name+'|'+$key.GetValueKind($name)+'|'+(ConvertTo-Json -InputObject $value -Compress))
                }
            } finally { $key.Dispose() }
        } finally { $root.Dispose() }
    }
    return $rows -join "`n"
}

function NG-BatchTreeSnapshot([string]$Root) {
    if (-not [IO.Directory]::Exists((NG-Ext $Root))) { return 'ABSENT' }
    $rows = @('PRESENT')
    foreach ($relative in (NG-RelativeFiles $Root)) {
        $path = (NG-Ext $Root)+'\'+$relative
        $info = [IO.FileInfo]::new($path)
        $rows += ($relative+'|'+(NG-FileDigest $path)+'|'+(NG-SdFingerprint $path)+'|'+(NG-SaclFingerprint $path)+'|'+$info.CreationTimeUtc.Ticks+'|'+$info.LastWriteTimeUtc.Ticks+'|'+[int]$info.Attributes+'|'+(NG-FileIdentity $path))
    }
    return $rows -join "`n"
}

function NG-BatchWritePlan($Fixture) {
    $document = [xml]'<EvidenceBatch version="1" />'
    foreach ($entry in $Fixture.Entries) {
        $element = $document.CreateElement('Case')
        $element.SetAttribute('id',$entry.Id)
        $element.SetAttribute('source',$entry.Source)
        $element.SetAttribute('dest',$entry.Dest)
        [void]$document.DocumentElement.AppendChild($element)
    }
    $document.Save($Fixture.Plan)
}

function NG-BatchFixture([switch]$Absent,[switch]$Field) {
    NG-ClearRegistry
    $tag = [guid]::NewGuid().ToString('N')
    $root = Join-Path $script:NG_Stage ('batch-'+$tag)
    [IO.Directory]::CreateDirectory($root) | Out-Null
    $fixture = [pscustomobject]@{Root=$root;Plan=(Join-Path $root 'plan.xml');Journal=(Join-Path $root 'journal');Entries=@();SourcesDetached=$false;OtherId=('OTHER-'+$tag);OtherRecord=''}
    foreach ($ordinal in 1..2) {
        $source = Join-Path $root ('source-'+$ordinal)
        [IO.Directory]::CreateDirectory($source) | Out-Null
        [IO.File]::WriteAllText((Join-Path $source 'payload.bin'),('new-'+$tag+'-'+$ordinal)*150)
        Set-Content -LiteralPath (Join-Path $source 'payload.bin') -Stream chain -Value (('stream-'+$ordinal)*100) -Encoding UTF8
        [IO.File]::SetCreationTimeUtc((Join-Path $source 'payload.bin'),[datetime]'2020-01-02T03:04:05Z')
        [IO.File]::SetLastWriteTimeUtc((Join-Path $source 'payload.bin'),[datetime]'2021-02-03T04:05:06Z')
        if ($Field -and $ordinal -eq 1) { $source = Join-Path $script:NG_Cases 'CASE-2231' }
        $destination = Join-Path $root ('dest-'+$ordinal)
        $caseId = 'BATCH-'+$tag+'-'+$ordinal
        if (-not $Absent) {
            [IO.Directory]::CreateDirectory($destination) | Out-Null
            $old = Join-Path $destination 'previous.bin'
            [IO.File]::WriteAllText($old,('old-'+$tag+'-'+$ordinal)*120)
            Set-Content -LiteralPath $old -Stream chain -Value 'original-stream' -Encoding UTF8
            New-Item -ItemType HardLink -Path (Join-Path $destination 'previous-alias.bin') -Target $old | Out-Null
            [IO.File]::SetCreationTimeUtc($old,[datetime]'2019-03-04T05:06:07Z')
            [IO.File]::SetLastWriteTimeUtc($old,[datetime]'2019-04-05T06:07:08Z')
            foreach ($view in @('Registry64','Registry32')) {
                $registry = [Microsoft.Win32.RegistryKey]::OpenBaseKey('LocalMachine',$view)
                try {
                    $key = $registry.CreateSubKey($env:EVIDENCE_MIRROR_REGISTRY_ROOT+'\Cases\'+$caseId)
                    try {
                        $key.SetValue('Text','old-'+$view,[Microsoft.Win32.RegistryValueKind]::String)
                        $key.SetValue('Expand','%SystemRoot%\unchanged',[Microsoft.Win32.RegistryValueKind]::ExpandString)
                        $key.SetValue('Many',[string[]]@('first','','last'),[Microsoft.Win32.RegistryValueKind]::MultiString)
                        $key.SetValue('Count',[int]-7,[Microsoft.Win32.RegistryValueKind]::DWord)
                        $key.SetValue('Wide',[long]1099511627781,[Microsoft.Win32.RegistryValueKind]::QWord)
                        $key.SetValue('Bytes',[byte[]]@(0,255,17,2),[Microsoft.Win32.RegistryValueKind]::Binary)
                    } finally { $key.Dispose() }
                } finally { $registry.Dispose() }
            }
        }
        $fixture.Entries += [pscustomobject]@{Id=$caseId;Source=$source;Dest=$destination;BeforeSource=(NG-BatchTreeSnapshot $source);BeforeTree=(NG-BatchTreeSnapshot $destination);BeforeRecord=(NG-BatchRegistrySnapshot $caseId)}
    }
    foreach ($view in @('Registry64','Registry32')) {
        $registry = [Microsoft.Win32.RegistryKey]::OpenBaseKey('LocalMachine',$view)
        try {
            $other = $registry.CreateSubKey($env:EVIDENCE_MIRROR_REGISTRY_ROOT+'\Cases\'+$fixture.OtherId)
            try { $other.SetValue('Sentinel','unrelated-'+$view) } finally { $other.Dispose() }
        } finally { $registry.Dispose() }
    }
    $fixture.OtherRecord = NG-BatchRegistrySnapshot $fixture.OtherId
    NG-BatchWritePlan $fixture
    return $fixture
}

function NG-BatchRun($Fixture,[string]$Verb='seal-batch') {
    $arguments = @($Verb,'--journal',$Fixture.Journal)
    if ($Verb -eq 'seal-batch') { $arguments += @('--plan',$Fixture.Plan) }
    return NG-RunNative -FilePath $script:NG_EXE -Arguments $arguments
}

function NG-BatchAssertOld($Fixture) {
    if ((NG-BatchRegistrySnapshot $Fixture.OtherId) -cne $Fixture.OtherRecord) { throw 'Batch changed an unrelated case' }
    foreach ($entry in $Fixture.Entries) {
        if (-not $Fixture.SourcesDetached -and (NG-BatchTreeSnapshot $entry.Source) -cne $entry.BeforeSource) { throw 'Batch modified a source object' }
        if ((NG-BatchTreeSnapshot $entry.Dest) -cne $entry.BeforeTree) { throw 'Batch rollback did not preserve the original NTFS objects and metadata' }
        if ((NG-BatchRegistrySnapshot $entry.Id) -cne $entry.BeforeRecord) { throw 'Batch rollback did not preserve both registry views and typed values' }
    }
}

function NG-BatchAssertMirror($Entry) {
    if (-not [IO.Directory]::Exists((NG-Ext $Entry.Dest))) { throw 'Batch destination is missing' }
    $sourceFiles = @(NG-RelativeFiles $Entry.Source)
    $destFiles = @(NG-RelativeFiles $Entry.Dest)
    if (($sourceFiles -join "`n") -cne ($destFiles -join "`n")) { throw 'Batch mirror file set differs from the source' }
    $groups = @{}
    foreach ($relative in $sourceFiles) {
        $source = (NG-Ext $Entry.Source)+'\'+$relative
        $target = (NG-Ext $Entry.Dest)+'\'+$relative
        if ((NG-FileDigest $source) -cne (NG-FileDigest $target)) { throw 'Batch main stream or ADS content mismatch' }
        $sourceDacl = NG-SdFingerprint $source
        $targetDacl = NG-SdFingerprint $target
        $sourceSacl = NG-SaclFingerprint $source
        $targetSacl = NG-SaclFingerprint $target
        if ($sourceDacl -cne $targetDacl -or $sourceSacl -cne $targetSacl) { throw "Batch security descriptors differ for $relative : DACL $sourceDacl -> $targetDacl ; SACL $sourceSacl -> $targetSacl" }
        $sourceInfo = [IO.FileInfo]::new($source)
        $targetInfo = [IO.FileInfo]::new($target)
        if ($sourceInfo.CreationTimeUtc -ne $targetInfo.CreationTimeUtc -or $sourceInfo.LastWriteTimeUtc -ne $targetInfo.LastWriteTimeUtc) { throw 'Batch timestamps changed' }
        $sourceId = NG-FileIdentity $source
        $targetId = NG-FileIdentity $target
        if ($sourceId.Split(':')[2] -ne $targetId.Split(':')[2]) { throw 'Batch hardlink count changed' }
        if ($groups.ContainsKey($sourceId) -and $groups[$sourceId] -cne $targetId) { throw 'Batch hardlink group split' }
        $groups[$sourceId] = $targetId
        foreach ($flag in @([IO.FileAttributes]::SparseFile,[IO.FileAttributes]::Compressed)) {
            if (($sourceInfo.Attributes -band $flag) -ne ($targetInfo.Attributes -band $flag)) { throw 'Batch NTFS storage flags changed' }
        }
        if ($sourceInfo.Attributes -band [IO.FileAttributes]::SparseFile) {
            if ((NG-AllocatedBytes $target) -gt 4194304) { throw 'Batch sparse file was materialized' }
        }
        if ($sourceInfo.Attributes -band [IO.FileAttributes]::Compressed) {
            $deadline = [datetime]::UtcNow.AddSeconds(60)
            do {
                $allocation = NG-AllocatedBytes $target
                if ($allocation -le ($targetInfo.Length / 4)) { break }
                Start-Sleep -Milliseconds 100
            } while ([datetime]::UtcNow -lt $deadline)
            if ($allocation -gt ($targetInfo.Length / 4)) { throw 'Batch compressed storage contract failed' }
        }
    }
}

function NG-BatchAssertRecord($Entry) {
    $registry = [Microsoft.Win32.RegistryKey]::OpenBaseKey('LocalMachine','Registry64')
    try {
        $key = $registry.OpenSubKey($env:EVIDENCE_MIRROR_REGISTRY_ROOT+'\Cases\'+$Entry.Id)
        if (-not $key) { throw 'Batch native authoritative record is missing' }
        try {
            if ((@($key.GetValueNames() | Sort-Object) -join '|') -cne 'CompletedUtc|FileCount|MirrorRoot|RootHash') { throw 'Batch record values differ from the contract' }
            if ($key.GetValueKind('FileCount') -ne 'DWord' -or $key.GetValue('FileCount') -ne @(NG-RelativeFiles $Entry.Source).Count) { throw 'Batch FileCount is wrong' }
            foreach ($name in @('RootHash','MirrorRoot','CompletedUtc')) {
                if ($key.GetValueKind($name) -ne 'String') { throw 'Batch registry value type is wrong' }
            }
            if ($key.GetValue('RootHash') -cne (NG-RootHash $Entry.Source) -or $key.GetValue('MirrorRoot') -cne $Entry.Dest) { throw 'Batch registry digest or destination is wrong' }
            $parsed = [datetime]::MinValue
            $timestamp = [string]$key.GetValue('CompletedUtc')
            if ($timestamp -cnotmatch '^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(\.\d{1,7})?(Z|\+00:00)$' -or -not [datetime]::TryParse($timestamp,[ref]$parsed)) { throw 'Batch completion timestamp is not UTC ISO 8601' }
        } finally { $key.Dispose() }
    } finally { $registry.Dispose() }
    $redirected = [Microsoft.Win32.RegistryKey]::OpenBaseKey('LocalMachine','Registry32')
    try {
        $key = $redirected.OpenSubKey($env:EVIDENCE_MIRROR_REGISTRY_ROOT+'\Cases\'+$Entry.Id)
        if ($key) { $key.Dispose(); throw 'Batch stale redirected record remains' }
    } finally { $redirected.Dispose() }
}

function NG-BatchAssertCommitted($Fixture) {
    if ((NG-BatchRegistrySnapshot $Fixture.OtherId) -cne $Fixture.OtherRecord) { throw 'Batch changed an unrelated case' }
    foreach ($entry in $Fixture.Entries) {
        if ((NG-BatchTreeSnapshot $entry.Source) -cne $entry.BeforeSource) { throw 'Batch modified a source object' }
        NG-BatchAssertMirror $entry
        NG-BatchAssertRecord $entry
    }
    $status = NG-BatchRun $Fixture 'batch-status'
    if ($status.Code -ne 0 -or ($status.Lines -join "`n") -cne 'State=COMMITTED') { throw 'Batch committed status is not observable' }
}

function NG-BatchAssertRecovered($Fixture,[string]$State='ROLLED_BACK') {
    $result = NG-BatchRun $Fixture 'recover'
    if ($result.Code -ne 0 -or ($result.Lines -join "`n") -cne ('State='+$State)) { throw 'Cross-process batch recovery did not report the correct terminal state' }
    $status = NG-BatchRun $Fixture 'batch-status'
    if ($status.Code -ne 0 -or ($status.Lines -join "`n") -cne ('State='+$State)) { throw 'Batch terminal recovery receipt is missing' }
    if ($State -eq 'ROLLED_BACK') { NG-BatchAssertOld $Fixture } else { NG-BatchAssertCommitted $Fixture }
    $allowed = @('source-1','source-2','dest-1','dest-2','journal')
    if (@([IO.Directory]::GetDirectories($Fixture.Root) | Where-Object { $allowed -notcontains [IO.Path]::GetFileName($_) }).Count) { throw 'Batch left sibling transaction directories' }
    $payloads = @()
    foreach ($entry in $Fixture.Entries) {
        foreach ($directory in @($entry.Source,$entry.Dest)) {
            if ([IO.Directory]::Exists((NG-Ext $directory))) {
                foreach ($relative in (NG-RelativeFiles $directory)) { $payloads += NG-HashFile ((NG-Ext $directory)+'\'+$relative) }
            }
        }
    }
    foreach ($path in [IO.Directory]::GetFiles((NG-Ext $Fixture.Journal),'*','AllDirectories')) {
        if ($payloads -contains (NG-HashFile $path)) { throw 'Terminal journal retains an evidence payload copy' }
    }
}

function NG-BatchCrash($Fixture,[string]$Point) {
    $signal = Join-Path $Fixture.Root ('signal-'+[guid]::NewGuid().ToString('N'))
    $start = [Diagnostics.ProcessStartInfo]::new()
    $start.FileName = $script:NG_EXE
    $start.Arguments = 'seal-batch --plan "'+$Fixture.Plan+'" --journal "'+$Fixture.Journal+'"'
    $start.UseShellExecute = $false
    $start.CreateNoWindow = $true
    $start.RedirectStandardOutput = $true
    $start.RedirectStandardError = $true
    foreach ($name in @('BENCH_API_KEY','OPENAI_API_KEY','ANTHROPIC_API_KEY')) { $start.EnvironmentVariables.Remove($name) }
    $start.EnvironmentVariables['EVIDENCE_MIRROR_PAUSE'] = $Point
    $start.EnvironmentVariables['EVIDENCE_MIRROR_SIGNAL'] = $signal
    $start.EnvironmentVariables['EVIDENCE_MIRROR_RELEASE'] = $signal+'.release'
    $process = [Diagnostics.Process]::new()
    $process.StartInfo = $start
    if (-not $process.Start()) { throw '[INVALID] Batch candidate process did not launch' }
    $stdout = $process.StandardOutput.ReadToEndAsync()
    $stderr = $process.StandardError.ReadToEndAsync()
    $observed = $false
    try {
        $deadline = [datetime]::UtcNow.AddSeconds(120)
        while (-not $process.HasExited -and [datetime]::UtcNow -lt $deadline) {
            if ([IO.File]::Exists($signal)) {
                try { $observed = [IO.File]::ReadAllText($signal) -ceq $Point } catch [IO.IOException] { $observed = $false }
                if ($observed) { break }
            }
            Start-Sleep -Milliseconds 25
        }
        if (-not $observed) { throw 'Candidate did not provide the requested live checkpoint handshake' }
        if ([IO.File]::ReadAllText($signal) -cne $Point) { throw 'Candidate checkpoint receipt is incorrect' }
        if ($Point -eq 'prepared') { NG-BatchAssertOld $Fixture }
        if ($Point.StartsWith('replaced:')) {
            $ordinal = [int]$Point.Split(':')[1]
            NG-BatchAssertMirror $Fixture.Entries[$ordinal-1]
        }
        if ($Point.StartsWith('published:')) {
            $ordinal = [int]$Point.Split(':')[1]
            NG-BatchAssertRecord $Fixture.Entries[$ordinal-1]
        }
        if ($Point -eq 'committed') { NG-BatchAssertCommitted $Fixture }
    } finally {
        $killed = -not $process.HasExited
        if ($killed) { $process.Kill() }
        $process.WaitForExit()
        [Threading.Tasks.Task]::WaitAll([Threading.Tasks.Task[]]@($stdout,$stderr))
        @{point=$Point;pid=$process.Id;checkpoint_observed=$observed;forcibly_terminated=$killed;exit_code=$process.ExitCode;stdout=$stdout.Result;stderr=$stderr.Result} | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $env:EVIDENCE_MIRROR_RESULTS ('artifacts\batch-'+[guid]::NewGuid().ToString('N')+'.json')) -Encoding UTF8
        $process.Dispose()
    }
}

function NG-BatchCrashRecover([string]$Point,[string]$State='ROLLED_BACK') {
    $fixture = NG-BatchFixture
    NG-BatchCrash $fixture $Point
    NG-BatchAssertRecovered $fixture $State
}

function Test-F2P_BatchCommitAndRecords {
    $fixture = NG-BatchFixture
    $result = NG-BatchRun $fixture
    if ($result.Code -ne 0 -or ($result.Lines -join "`n") -cne "State=COMMITTED`nCaseCount=2") { throw 'Batch success CLI contract failed' }
    NG-BatchAssertCommitted $fixture
}

function Test-F2P_BatchFieldFidelity {
    $fixture = NG-BatchFixture -Field
    if ((NG-BatchRun $fixture).Code -ne 0) { throw 'Batch field case did not commit' }
    NG-BatchAssertCommitted $fixture
}

function Test-F2P_BatchAbsentDestinations {
    $fixture = NG-BatchFixture -Absent
    NG-BatchCrash $fixture 'published:1'
    NG-BatchAssertRecovered $fixture
}

function Test-F2P_BatchDestinationLockRollback {
    $fixture = NG-BatchFixture
    $lock = [IO.File]::Open((Join-Path $fixture.Entries[1].Dest 'previous.bin'),'Open','ReadWrite','None')
    try { $result = NG-BatchRun $fixture } finally { $lock.Dispose() }
    if ($result.Code -ne 3) { throw 'Batch locked destination did not fail' }
    NG-BatchAssertOld $fixture
}

function Test-F2P_BatchSourceSharingOutcome {
    $fixture = NG-BatchFixture
    $lock = [IO.File]::Open((Join-Path $fixture.Entries[1].Source 'payload.bin'),'Open','Read','None')
    try { $result = NG-BatchRun $fixture } finally { $lock.Dispose() }
    if ($result.Code -eq 3) { NG-BatchAssertOld $fixture }
    elseif ($result.Code -eq 0) { NG-BatchAssertCommitted $fixture }
    else { throw 'Batch source sharing condition did not produce a contractual outcome' }
}

function Test-F2P_BatchPublicationDenialRollback {
    $fixture = NG-BatchFixture
    $root = [Microsoft.Win32.RegistryKey]::OpenBaseKey('LocalMachine','Registry64')
    $parent = $root.OpenSubKey($env:EVIDENCE_MIRROR_REGISTRY_ROOT+'\Cases',$true)
    $security = $parent.GetAccessControl()
    $blocked = $parent.GetAccessControl()
    $children = @($fixture.Entries | ForEach-Object {
        $child = $parent.OpenSubKey($_.Id,$true)
        [pscustomobject]@{Key=$child;Security=$child.GetAccessControl()}
    })
    $sid = [Security.Principal.WindowsIdentity]::GetCurrent().User
    $rights = [Security.AccessControl.RegistryRights]::SetValue -bor [Security.AccessControl.RegistryRights]::CreateSubKey -bor [Security.AccessControl.RegistryRights]::Delete
    $blocked.AddAccessRule([Security.AccessControl.RegistryAccessRule]::new($sid,$rights,'ContainerInherit','None','Deny'))
    try { $parent.SetAccessControl($blocked); $result = NG-BatchRun $fixture }
    finally {
        $security.SetSecurityDescriptorBinaryForm($security.GetSecurityDescriptorBinaryForm())
        $parent.SetAccessControl($security)
        foreach ($child in $children) {
            $child.Security.SetSecurityDescriptorBinaryForm($child.Security.GetSecurityDescriptorBinaryForm())
            $child.Key.SetAccessControl($child.Security)
            $child.Key.Dispose()
        }
        $parent.Dispose()
        $root.Dispose()
    }
    if ($result.Code -ne 3) { throw 'Batch denied publication did not fail' }
    NG-BatchAssertOld $fixture
}

function Test-F2P_BatchPreparedCrash { NG-BatchCrashRecover 'prepared' }
function Test-F2P_BatchFirstReplacementCrash { NG-BatchCrashRecover 'replaced:1' }
function Test-F2P_BatchSecondReplacementCrash { NG-BatchCrashRecover 'replaced:2' }
function Test-F2P_BatchFirstPublicationCrash { NG-BatchCrashRecover 'published:1' }
function Test-F2P_BatchSecondPublicationCrash { NG-BatchCrashRecover 'published:2' }
function Test-F2P_BatchCommittedCrash { NG-BatchCrashRecover 'committed' 'COMMITTED' }

function Test-F2P_BatchRecoveryWithoutSources {
    $fixture = NG-BatchFixture
    NG-BatchCrash $fixture 'published:1'
    $fixture.SourcesDetached = $true
    foreach ($entry in $fixture.Entries) {
        $resolved = [IO.Path]::GetFullPath($entry.Source)
        if (-not $resolved.StartsWith(([IO.Path]::GetFullPath($fixture.Root)+'\'),[StringComparison]::OrdinalIgnoreCase)) { throw '[INVALID] Unsafe test-owned source cleanup' }
        Remove-Item -LiteralPath $resolved -Recurse -Force
    }
    Remove-Item -LiteralPath $fixture.Plan
    NG-BatchAssertRecovered $fixture
}

function Test-F2P_BatchRecoveryRetryAfterLock {
    $fixture = NG-BatchFixture
    NG-BatchCrash $fixture 'published:1'
    $lock = [IO.File]::Open((Join-Path $fixture.Entries[0].Dest 'payload.bin'),'Open','ReadWrite','None')
    try { $result = NG-BatchRun $fixture 'recover' } finally { $lock.Dispose() }
    if ($result.Code -ne 3) { throw 'Recovery swallowed a live NTFS replacement lock' }
    NG-BatchAssertRecovered $fixture
}

function Test-F2P_BatchRecoveryIdempotence {
    $fixture = NG-BatchFixture
    NG-BatchCrash $fixture 'replaced:2'
    NG-BatchAssertRecovered $fixture
    NG-BatchAssertRecovered $fixture
}

function Test-F2P_BatchRejectOverlappingPlan {
    $fixture = NG-BatchFixture
    $fixture.Entries[1].Dest = Join-Path $fixture.Entries[0].Dest 'nested'
    NG-BatchWritePlan $fixture
    $before = NG-BatchTreeSnapshot $fixture.Entries[0].Dest
    if ((NG-BatchRun $fixture).Code -ne 3) { throw 'Overlapping plan was not rejected' }
    if ((NG-BatchTreeSnapshot $fixture.Entries[0].Dest) -cne $before -or (NG-BatchRegistrySnapshot $fixture.Entries[0].Id) -cne $fixture.Entries[0].BeforeRecord) { throw 'Invalid plan mutated an earlier case' }
}

function Test-F2P_BatchRejectDuplicateIds {
    $fixture = NG-BatchFixture
    $fixture.Entries[1].Id = $fixture.Entries[0].Id.ToLowerInvariant()
    NG-BatchWritePlan $fixture
    if ((NG-BatchRun $fixture).Code -ne 3) { throw 'Case-insensitive duplicate IDs were accepted' }
    if ((NG-BatchTreeSnapshot $fixture.Entries[0].Dest) -cne $fixture.Entries[0].BeforeTree) { throw 'Duplicate plan changed a destination' }
}

function Test-F2P_BatchJournalReuseAndStatus {
    $fixture = NG-BatchFixture
    if ((NG-BatchRun $fixture 'batch-status').Code -ne 4 -or (NG-BatchRun $fixture 'recover').Code -ne 4) { throw 'Missing journal is not distinguishable from a completed transaction' }
    if ((NG-BatchRun $fixture).Code -ne 0) { throw 'Batch did not commit' }
    $before = @($fixture.Entries | ForEach-Object { (NG-BatchTreeSnapshot $_.Dest)+(NG-BatchRegistrySnapshot $_.Id) }) -join "`n"
    if ((NG-BatchRun $fixture).Code -ne 3) { throw 'A completed journal was reused' }
    NG-BatchAssertRecovered $fixture 'COMMITTED'
    NG-BatchAssertRecovered $fixture 'COMMITTED'
    $after = @($fixture.Entries | ForEach-Object { (NG-BatchTreeSnapshot $_.Dest)+(NG-BatchRegistrySnapshot $_.Id) }) -join "`n"
    if ($before -cne $after) { throw 'Committed recovery changed identities or republished record timestamps' }
}
