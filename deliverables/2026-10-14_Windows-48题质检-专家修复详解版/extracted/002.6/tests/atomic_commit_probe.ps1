# Public filesystem fault injection; never hooks a candidate function or inspects source.
function Invoke-AtomicCommitProbe([string]$FixtureDir) {
    if (-not ('OutsideAdsObservation' -as [type])) {
        Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
using System.Threading;
using Microsoft.Win32.SafeHandles;
public sealed class OutsideAdsObservation : IDisposable {
    [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
    static extern SafeFileHandle CreateFileW(string p, uint access, uint share, IntPtr security, uint mode, uint flags, IntPtr template);
    public static SafeFileHandle LockStream(string path) {
        var handle = CreateFileW(path, 0x80000000, 3, IntPtr.Zero, 3, 0, IntPtr.Zero);
        if (handle.IsInvalid) { int code=Marshal.GetLastWin32Error(); handle.Dispose(); throw new System.ComponentModel.Win32Exception(code); }
        return handle;
    }
    volatile bool stop;
    public volatile bool Removed;
    Thread thread;
    public OutsideAdsObservation(string path) {
        thread = new Thread(() => {
            while (!stop) {
                using (var h = CreateFileW(path, 0x80, 7, IntPtr.Zero, 3, 0, IntPtr.Zero)) {
                    if (h.IsInvalid && Marshal.GetLastWin32Error() == 2) { Removed=true; break; }
                }
                Thread.Yield();
            }
        });
        thread.IsBackground=true; thread.Start();
    }
    public void Dispose() { stop=true; thread.Join(2000); }
}
'@
    }
    $first=Join-Path $FixtureDir 'commit-first.txt'
    $second=Join-Path $FixtureDir 'commit-second.txt'
    foreach ($file in @($first,$second)) {
        [IO.File]::WriteAllText($file,'atomic-main')
        Set-Content -LiteralPath $file -Stream Zone.Identifier -Value 'ZoneId=3' -Encoding UTF8
        Set-Content -LiteralPath $file -Stream Keep -Value 'must-survive' -Encoding UTF8
    }
    $before=@(Get-FileSnapshot $first; Get-FileSnapshot $second)
    $times=@(Get-FileTimes $first; Get-FileTimes $second)
    # Reading/writing the second stream remains possible; deletion gets a sharing
    # violation only when attempted. A safe early rejection is also acceptable.
    $lock=[OutsideAdsObservation]::LockStream($second+':Zone.Identifier')
    $observer=New-Object OutsideAdsObservation ($first+':Zone.Identifier')
    try { $results=@(Invoke-CleanerWithOptions -Inputs @($first,$second) -Atomic) }
    finally { $observer.Dispose(); $lock.Dispose() }
    $restored=$true
    for ($i=0;$i -lt 2;$i++) {
        $file=@($first,$second)[$i]; $after=Get-FileSnapshot $file; $afterTime=Get-FileTimes $file
        $restored=$restored -and (([string](Get-NamedStreamText $file 'Zone.Identifier')).Trim() -eq 'ZoneId=3')
        $restored=$restored -and (([string](Get-NamedStreamText $file 'Keep')).Trim() -eq 'must-survive')
        $restored=$restored -and $after.Hash -eq $before[$i].Hash -and $after.Identity -eq $before[$i].Identity -and $after.Attributes -eq $before[$i].Attributes
        $restored=$restored -and $afterTime.CreationTimeUtc -eq $times[$i].CreationTimeUtc -and $afterTime.LastWriteTimeUtc -eq $times[$i].LastWriteTimeUtc
    }
    $valid=@($results).Count -eq 2 -and @($results | Where-Object { $_.Status -ne 'Failed' -or [string]::IsNullOrWhiteSpace([string]$_.Error) }).Count -eq 0 -and $restored
    [pscustomobject]@{passed=[bool]$valid;mutation_observed=[bool]$observer.Removed;state_restored=[bool]$restored;
        outcome=$(if ($observer.Removed) {'mid_commit_failure_with_observed_mutation'} else {'safe_early_rejection_or_unobserved_transient'});results=$results}
}
