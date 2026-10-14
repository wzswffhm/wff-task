# Observe public NTFS state independently of the cleaner's returned objects/audit.
# Reads only; LastAccessTime is intentionally outside the task's preservation contract.
function Open-AtomicStreamRead {
    param([string]$StreamPath)
    if ($env:OS -ne 'Windows_NT') {
        return [IO.File]::Open($StreamPath, [IO.FileMode]::Open, [IO.FileAccess]::Read, ([IO.FileShare]::ReadWrite -bor [IO.FileShare]::Delete))
    }
    # Windows PowerShell 5.1's .NET Framework rejects ADS paths in File.Open.
    # Open the stream with Win32 and hash the same bytes through a FileStream.
    if ($null -eq ('OutsideAtomicStreamReader' -as [type])) {
        Add-Type -TypeDefinition @'
using System;
using System.IO;
using System.ComponentModel;
using System.Runtime.InteropServices;
using Microsoft.Win32.SafeHandles;
public static class OutsideAtomicStreamReader {
    [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
    private static extern SafeFileHandle CreateFile(string name, uint access, uint share, IntPtr security, uint disposition, uint flags, IntPtr template);
    public static FileStream Open(string path) {
        SafeFileHandle handle=CreateFile(path, 0x80000000, 7, IntPtr.Zero, 3, 0, IntPtr.Zero);
        if (handle.IsInvalid) { int code=Marshal.GetLastWin32Error(); handle.Dispose(); throw new Win32Exception(code); }
        try { return new FileStream(handle, FileAccess.Read); }
        catch { handle.Dispose(); throw; }
    }
}
'@
    }
    return [OutsideAtomicStreamReader]::Open($StreamPath)
}

function Set-AtomicFixtureStream {
    param([string]$Path, [string]$Name, [byte[]]$Bytes)
    $parameters=@{LiteralPath=$Path;Stream=$Name;Value=$Bytes;NoNewline=$true;ErrorAction='Stop'}
    if ((Get-Command Set-Content).Parameters.ContainsKey('AsByteStream')) { $parameters.AsByteStream=$true }
    else { $parameters.Encoding='Byte' }
    Set-Content @parameters
}

function Get-AtomicSuccessState {
    param([Parameter(Mandatory=$true)][string]$Path)
    $file = Get-FileSnapshot -Path $Path
    $times = Get-FileTimes -Path $Path
    $streams = [Collections.Generic.Dictionary[string,string]]::new([StringComparer]::OrdinalIgnoreCase)
    foreach ($entry in @(Get-Item -LiteralPath $Path -Stream * -Force -ErrorAction Stop)) {
        $name = [string]$entry.Stream
        if ($name -eq ':$DATA') { continue }
        $handle = Open-AtomicStreamRead -StreamPath ($Path + ':' + $name)
        $sha = [Security.Cryptography.SHA256]::Create()
        try { $streams.Add($name, [BitConverter]::ToString($sha.ComputeHash($handle))) }
        finally { $sha.Dispose(); $handle.Dispose() }
    }
    [pscustomobject]@{ File=$file; Times=$times; Streams=$streams }
}

function Assert-AtomicSuccessState {
    param([Parameter(Mandatory=$true)][string]$Path, [Parameter(Mandatory=$true)]$Before)
    # A missing/unreadable file/stream throws inside Add-Check and is a testcase
    # failure, never a successful deletion inferred from a suppressed read error.
    $after = Get-AtomicSuccessState -Path $Path
    Assert-True (-not $after.Streams.ContainsKey('Zone.Identifier')) 'Atomic success left the Zone.Identifier stream on disk.'
    foreach ($field in @('Hash','Length','Attributes','Identity')) {
        Assert-True ($after.File.$field -ceq $Before.File.$field) ('Atomic success changed primary file ' + $field)
    }
    foreach ($field in @('CreationTimeUtc','LastWriteTimeUtc')) {
        Assert-True ($after.Times.$field -eq $Before.Times.$field) ('Atomic success changed ' + $field)
    }
    $expectedNames = @($Before.Streams.Keys | Where-Object { $_ -ine 'Zone.Identifier' })
    Assert-Equal $after.Streams.Count $expectedNames.Count 'Atomic success changed the non-target stream set.'
    foreach ($name in $expectedNames) {
        Assert-True ($after.Streams.ContainsKey($name)) ('Atomic success removed non-target stream: ' + $name)
        Assert-True ($after.Streams[$name] -ceq $Before.Streams[$name]) ('Atomic success changed non-target stream bytes: ' + $name)
    }
}
