param([Parameter(Mandatory=$true)][string]$Action,[Parameter(Mandatory=$true)][string]$Descriptor)
$ErrorActionPreference = 'Stop'
$data = Get-Content -LiteralPath $Descriptor -Raw | ConvertFrom-Json
$root = [IO.Path]::GetFullPath($data.root)
$allowed = [IO.Path]::GetFullPath('C:\OutsideHarborRuns\')
if (-not $root.StartsWith($allowed,[StringComparison]::OrdinalIgnoreCase) -or $root.TrimEnd('\') -eq $allowed.TrimEnd('\')) { throw 'Invalid sandbox root' }
if ($data.user -notmatch '^ohb_[a-f0-9]{12}$') { throw 'Invalid evaluation user' }
if ($Action -eq 'create') {
    $password = [REDACTED] $data.passwordDpapi
    $user = New-LocalUser -Name $data.user -Password $password -AccountNeverExpires -PasswordNeverExpires -Description 'Temporary Outside Harbor evaluation account'
    Add-LocalGroupMember -SID 'S-1-5-32-545' -Member $user
    $sid = $user.SID.Value
    New-Item -ItemType Directory -Path $root -Force | Out-Null
    $acl = Get-Acl -LiteralPath $root
    $acl.SetAccessRuleProtection($true,$false)
    foreach ($principal in @('S-1-5-18','S-1-5-32-544',$sid)) {
        $identity = [Security.Principal.SecurityIdentifier]::new($principal)
        $rule = [Security.AccessControl.FileSystemAccessRule]::new($identity,'FullControl','ContainerInherit,ObjectInherit','None','Allow')
        $acl.AddAccessRule($rule)
    }
    Set-Acl -LiteralPath $root -AclObject $acl
    # The user has no outbound network, including programs it launches during verification.
    New-NetFirewallRule -Name ('OHB-' + $data.user) -DisplayName ('OHB isolated account ' + $data.user) -Direction Outbound -Action Block -Profile Any -LocalUser ('D:(A;;CC;;;' + $sid + ')') | Out-Null
    if ($data.registryRoot) {
        foreach ($view in @([Microsoft.Win32.RegistryView]::Registry32,[Microsoft.Win32.RegistryView]::Registry64)) {
            $hive = [Microsoft.Win32.RegistryKey]::OpenBaseKey([Microsoft.Win32.RegistryHive]::LocalMachine,$view)
            $key = $hive.CreateSubKey($data.registryRoot)
            $security = $key.GetAccessControl()
            $rule = [Security.AccessControl.RegistryAccessRule]::new([Security.Principal.SecurityIdentifier]::new($sid),'FullControl','ContainerInherit','None','Allow')
            $security.AddAccessRule($rule); $key.SetAccessControl($security)
            $key.Dispose(); $hive.Dispose()
        }
    }
    $data | Add-Member -NotePropertyName sid -NotePropertyValue $sid -Force
    $data | ConvertTo-Json | Set-Content -LiteralPath $Descriptor -Encoding utf8
    Write-Output 'Sandbox account, scoped ACL and outbound block created.'
    exit 0
}
if ($Action -eq 'password') {
    $password = [REDACTED] $data.passwordDpapi
    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($password)
    try { [Console]::Write([Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)) }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer) }
    exit 0
}
if ($Action -eq 'cleanup') {
    Get-CimInstance Win32_Process | ForEach-Object {
        try {
            $owner = Invoke-CimMethod -InputObject $_ -MethodName GetOwner -ErrorAction Stop
            if ($owner.User -eq $data.user) { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
        } catch {}
    }
    Remove-NetFirewallRule -Name ('OHB-' + $data.user) -ErrorAction SilentlyContinue
    if ($data.registryRoot) {
        foreach ($view in @([Microsoft.Win32.RegistryView]::Registry32,[Microsoft.Win32.RegistryView]::Registry64)) {
            $hive = [Microsoft.Win32.RegistryKey]::OpenBaseKey([Microsoft.Win32.RegistryHive]::LocalMachine,$view)
            $hive.DeleteSubKeyTree($data.registryRoot,$false); $hive.Dispose()
        }
    }
    $profile = Get-CimInstance Win32_UserProfile | Where-Object SID -eq $data.sid
    if ($profile -and -not $profile.Loaded) { $profile | Remove-CimInstance }
    Remove-LocalUser -Name $data.user -ErrorAction SilentlyContinue
    if (Get-LocalUser -Name $data.user -ErrorAction SilentlyContinue) { throw 'Account residue' }
    if (Get-NetFirewallRule -Name ('OHB-' + $data.user) -ErrorAction SilentlyContinue) { throw 'Firewall residue' }
    if (Test-Path -LiteralPath $root) { Remove-Item -LiteralPath $root -Recurse -Force }
    Write-Output 'Sandbox account, firewall, registry and directory cleanup complete.'
    exit 0
}
throw 'Unknown sandbox action'
