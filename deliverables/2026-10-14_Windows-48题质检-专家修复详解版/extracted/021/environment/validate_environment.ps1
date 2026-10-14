$ErrorActionPreference='Stop'
if(-not $IsWindows -or $PSVersionTable.PSVersion.Major-lt 7){exit 1}
[IO.Pipes.PipeTransmissionMode]::Message | Out-Null
exit 0
