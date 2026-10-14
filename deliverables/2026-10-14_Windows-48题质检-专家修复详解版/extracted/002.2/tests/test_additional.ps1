
function Test-F2P_AtomicDestinationLock {
    $caseId='CASE-DESTLOCK'
    $dest=NG-Reset $caseId
    [IO.Directory]::CreateDirectory($dest) | Out-Null
    $marker=Join-Path $dest 'previous.txt'
    [IO.File]::WriteAllText($marker,'previous-content')
    $before=@([IO.Directory]::GetFileSystemEntries($script:NG_Stage) | Sort-Object) -join '|'
    $lock=[IO.File]::Open($marker,'Open','ReadWrite','None')
    try {$run=NG-RunSeal -CaseId $caseId -Source (Join-Path $script:NG_Cases 'CASE-1000') -Dest $dest}
    finally {$lock.Dispose()}
    if ($run.Code -eq 0) {throw 'Locked destination replacement should fail'}
    if (@([IO.Directory]::GetFiles($dest,'*','AllDirectories')).Count -ne 1 -or [IO.File]::ReadAllText($marker) -cne 'previous-content') {throw 'Locked destination was changed'}
    if ((@([IO.Directory]::GetFileSystemEntries($script:NG_Stage) | Sort-Object) -join '|') -cne $before) {throw 'Failed replacement left staging residue'}
    foreach ($view in @('Registry64','Registry32')) {
        $base=[Microsoft.Win32.RegistryKey]::OpenBaseKey('LocalMachine',$view)
        try {
            $key=$base.OpenSubKey($env:EVIDENCE_MIRROR_REGISTRY_ROOT+'\Cases\'+$caseId)
            if ($key) {$key.Dispose();throw 'Failed replacement published a record'}
        } finally {$base.Dispose()}
    }
}

function NG-InputSnapshot {
    $rows=@()
    foreach ($root in @($script:NG_Cases,(Join-Path $script:NG_Calibration 'cases'))) {
        foreach ($relative in (NG-RelativeFiles $root)) {
            $path=(NG-Ext $root)+'\'+$relative
            $info=New-Object IO.FileInfo($path)
            $rows+=($root+'|'+$relative+'|'+(NG-FileDigest $path)+'|'+(NG-SdFingerprint $path)+'|'+(NG-SaclFingerprint $path)+'|'+$info.CreationTimeUtc.Ticks+'|'+$info.LastWriteTimeUtc.Ticks+'|'+[int]$info.Attributes+'|'+(NG-FileIdentity $path))
        }
    }
    return $rows -join [Environment]::NewLine
}

function Test-P2P_SourceInputsRemainReadOnly {
    if ((NG-InputSnapshot) -cne $script:NG_SourceBefore) {throw 'Candidate changed source data, metadata, streams or hardlink state'}
}

function Test-P2P_CliContracts {
    $usage=NG-RunNative -FilePath $script:NG_EXE -Arguments @()
    if ($usage.Code -ne 2) {throw 'No-argument usage must exit 2'}
    $unknown=NG-RunNative -FilePath $script:NG_EXE -Arguments @('unknown')
    if ($unknown.Code -ne 2) {throw 'Unknown verb must exit 2'}
    $missing=NG-RunNative -FilePath $script:NG_EXE -Arguments @('report','--case','CASE-NEVER-SEALED')
    if ($missing.Code -ne 4) {throw 'Missing record must exit 4'}
    $source=Join-Path $script:NG_Cases 'CASE-1000'
    $dest=NG-Reset 'CASE-1000'
    $seal=NG-RunSeal -CaseId 'CASE-1000' -Source $source -Dest $dest
    $report=NG-RunNative -FilePath $script:NG_EXE -Arguments @('report','--case','CASE-1000')
    if ($seal.Code -ne 0 -or $report.Code -ne 0) {throw 'Ordinary seal/report did not complete'}
    if ($seal.Lines.Count -ne 4 -or $report.Lines.Count -ne 5) {throw 'CLI output line count changed'}
    $names=@('CaseId','FileCount','RootHash','MirrorRoot','CompletedUtc')
    foreach ($index in 0..3) {
        if (-not $seal.Lines[$index].StartsWith($names[$index]+'=') -or $report.Lines[$index] -cne $seal.Lines[$index]) {throw 'CLI field order or round-trip changed'}
    }
    if (-not $report.Lines[4].StartsWith('CompletedUtc=')) {throw 'Report timestamp position changed'}
}

function Test-F2P_AtomicRecordPublicationFailure {
    $caseId='CASE-PUBLISH'
    $dest=NG-Reset $caseId
    [IO.Directory]::CreateDirectory($dest) | Out-Null
    $marker=Join-Path $dest 'previous.txt'
    [IO.File]::WriteAllText($marker,'previous-content')
    $beforeStage=@([IO.Directory]::GetFileSystemEntries($script:NG_Stage) | Sort-Object) -join '|'
    $store=$env:EVIDENCE_MIRROR_REGISTRY_ROOT+'\Cases'
    $base64=[Microsoft.Win32.RegistryKey]::OpenBaseKey('LocalMachine','Registry64')
    $base32=[Microsoft.Win32.RegistryKey]::OpenBaseKey('LocalMachine','Registry32')
    $parent=$base64.CreateSubKey($store)
    $old=$parent.CreateSubKey($caseId)
    $old.SetValue('LegacyDigest','previous-record',[Microsoft.Win32.RegistryValueKind]::String)
    $oldSecurity=$old.GetAccessControl()
    $other=$base32.CreateSubKey($store+'\'+$caseId)
    $other.SetValue('LegacyDigest','previous-redirected',[Microsoft.Win32.RegistryValueKind]::String)
    $other.Dispose()
    $security=$parent.GetAccessControl()
    $blocked=$parent.GetAccessControl()
    $sid=[Security.Principal.WindowsIdentity]::GetCurrent().User
    $rights=[Security.AccessControl.RegistryRights]::SetValue -bor [Security.AccessControl.RegistryRights]::CreateSubKey -bor [Security.AccessControl.RegistryRights]::Delete
    $rule=New-Object Security.AccessControl.RegistryAccessRule($sid,$rights,[Security.AccessControl.InheritanceFlags]::ContainerInherit,[Security.AccessControl.PropagationFlags]::None,[Security.AccessControl.AccessControlType]::Deny)
    $blocked.AddAccessRule($rule)
    try {
        $parent.SetAccessControl($blocked)
        $run=NG-RunSeal -CaseId $caseId -Source (Join-Path $script:NG_Cases 'CASE-1000') -Dest $dest
    } finally {
        $security.SetSecurityDescriptorBinaryForm($security.GetSecurityDescriptorBinaryForm())
        $oldSecurity.SetSecurityDescriptorBinaryForm($oldSecurity.GetSecurityDescriptorBinaryForm())
        $parent.SetAccessControl($security)
        $old.SetAccessControl($oldSecurity)
        $old.Dispose()
        $parent.Dispose()
    }
    try {
        if ($run.Code -eq 0) {throw 'Publication denial was incorrectly reported as success'}
        if (-not [IO.File]::Exists($marker) -or [IO.File]::ReadAllText($marker) -cne 'previous-content') {throw 'Publication failure changed the prior destination'}
        if ((@([IO.Directory]::GetFileSystemEntries($script:NG_Stage) | Sort-Object) -join '|') -cne $beforeStage) {throw 'Publication failure left intermediate directories'}
        foreach ($pair in @(@($base64,'previous-record'),@($base32,'previous-redirected'))) {
            $key=$pair[0].OpenSubKey($store+'\'+$caseId)
            if (-not $key) {throw 'Publication failure deleted a prior record'}
            try {if ($key.GetValueNames().Count -ne 1 -or $key.GetValue('LegacyDigest') -cne $pair[1]) {throw 'Publication failure changed a prior record'}}
            finally {$key.Dispose()}
        }
    } finally {$base64.Dispose();$base32.Dispose()}
}

function Test-F2P_StaleRedirectedRecordAndOtherCase {
    $caseId='CASE-1000'
    $dest=NG-Reset $caseId
    $store=$env:EVIDENCE_MIRROR_REGISTRY_ROOT+'\Cases'
    foreach ($view in @('Registry32','Registry64')) {
        $root=[Microsoft.Win32.RegistryKey]::OpenBaseKey('LocalMachine',$view)
        try {
            $other=$root.CreateSubKey($store+'\CASE-UNRELATED')
            $other.SetValue('Sentinel','keep')
            $other.Dispose()
            if ($view -eq 'Registry32') {
                $stale=$root.CreateSubKey($store+'\'+$caseId)
                $stale.SetValue('Legacy','stale')
                $stale.Dispose()
            }
        } finally {$root.Dispose()}
    }
    $run=NG-RunSeal -CaseId $caseId -Source (Join-Path $script:NG_Cases $caseId) -Dest $dest
    if ($run.Code -ne 0) {throw 'Seal did not succeed'}
    foreach ($view in @('Registry32','Registry64')) {
        $root=[Microsoft.Win32.RegistryKey]::OpenBaseKey('LocalMachine',$view)
        try {
            $other=$root.OpenSubKey($store+'\CASE-UNRELATED')
            if (-not $other) {throw 'Seal deleted another case'}
            try {if ($other.GetValue('Sentinel') -cne 'keep') {throw 'Seal changed another case'}} finally {$other.Dispose()}
            if ($view -eq 'Registry32') {
                $stale=$root.OpenSubKey($store+'\'+$caseId)
                if ($stale) {$stale.Dispose();throw 'Stale redirected record remains'}
            }
        } finally {$root.Dispose()}
    }
}
