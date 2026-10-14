$ErrorActionPreference = 'Stop'
function Get-TaskWorkspace {
    if (-not $env:OUTSIDE_WORKSPACE) { throw 'Explicit candidate workspace is required.' }
    return $env:OUTSIDE_WORKSPACE
}
function Get-PathAclFixtureRoot {
    if (-not $env:PATHACL_FIXTURE_ROOT) { throw 'Explicit independent fixture root is required.' }
    return $env:PATHACL_FIXTURE_ROOT
}
function New-FailedF2P {
    $result = @{}
    foreach ($number in 1..8) { $result[('F2P-{0:000}' -f $number)] = $false }
    return ,$result
}
function Get-PathAclDll {
    param([string]$Workspace)
    if ($env:PATHACL_CANDIDATE_DLL -and (Test-Path -LiteralPath $env:PATHACL_CANDIDATE_DLL)) { return Get-Item -LiteralPath $env:PATHACL_CANDIDATE_DLL }
    return $null
}
function Invoke-PathAclBuild {
    param([string]$Workspace)
    if (Get-PathAclDll -Workspace $Workspace) { return $true }
    $project = Join-Path $Workspace 'src\PathAclTool\PathAclTool.csproj'
    $build = Join-Path (Split-Path -Parent $Workspace) 'verifier-build'
    if (Test-Path -LiteralPath $build) { throw 'Verifier build directory is not fresh.' }
    New-Item -ItemType Directory -Path $build -Force | Out-Null
    $options = @("-p:BaseIntermediateOutputPath=$build\obj\", "-p:BaseOutputPath=$build\bin\", '-p:NuGetAudit=false')
    $log = Join-Path $env:PATHACL_RESULTS 'artifacts\candidate_build.log'
    Push-Location $Workspace
    try {
        & dotnet restore $project --configfile (Join-Path $Workspace 'NuGet.Config') @options *> $log
        if ($LASTEXITCODE -ne 0) { throw 'Offline candidate restore failed; see candidate_build.log.' }
        & dotnet build $project -c Release --no-restore @options *>> $log
        if ($LASTEXITCODE -ne 0) { throw 'Candidate compilation failed; required tests did not execute.' }
    } finally { Pop-Location }
    $env:PATHACL_CANDIDATE_DLL = Join-Path $build 'bin\Release\net8.0-windows\PathAclTool.dll'
    if (-not (Test-Path -LiteralPath $env:PATHACL_CANDIDATE_DLL)) { throw 'Fresh candidate DLL missing.' }
    return $true
}
function Invoke-PathAclTool {
    param([string]$Workspace, [string]$Argument = $null, [string[]]$ExtraArguments = @())
    $dll = Get-PathAclDll -Workspace $Workspace
    if (-not $dll) { throw 'Fresh candidate assembly unavailable.' }
    $invocation = [guid]::NewGuid().ToString('N')
    $stdout = Join-Path $env:PATHACL_RESULTS "artifacts\$invocation.stdout.txt"
    $stderr = Join-Path $env:PATHACL_RESULTS "artifacts\$invocation.stderr.txt"
    $arguments = 'exec "' + $dll.FullName + '"'
    if ($Argument) { $arguments += ' "' + $Argument + '"' }
    foreach ($value in $ExtraArguments) { $arguments += ' "' + $value + '"' }
    $startInfo = New-Object Diagnostics.ProcessStartInfo
    $startInfo.FileName = (Get-Command dotnet).Source
    $startInfo.Arguments = $arguments
    $startInfo.WorkingDirectory = $Workspace
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $true
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true
    $startInfo.StandardOutputEncoding = [Text.Encoding]::UTF8
    $startInfo.StandardErrorEncoding = [Text.Encoding]::UTF8
    $process = New-Object Diagnostics.Process
    $process.StartInfo = $startInfo
    if (-not $process.Start()) { throw 'Candidate process did not start.' }
    $outputTask = $process.StandardOutput.ReadToEndAsync()
    $errorTask = $process.StandardError.ReadToEndAsync()
    if (-not $process.WaitForExit(30000)) {
        $process.Kill()
        $process.WaitForExit()
        throw 'Candidate process timeout; no complete execution receipt.'
    }
    if (-not [Threading.Tasks.Task]::WaitAll([Threading.Tasks.Task[]]@($outputTask, $errorTask), 5000)) { throw 'Candidate output streams did not close.' }
    [IO.File]::WriteAllText($stdout, $outputTask.Result, [Text.Encoding]::UTF8)
    [IO.File]::WriteAllText($stderr, $errorTask.Result, [Text.Encoding]::UTF8)
    $code = $process.ExitCode
    @{exited=$process.HasExited; exit_code=$code; arguments=$arguments; stdout=$stdout; stderr=$stderr} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $env:PATHACL_RESULTS "artifacts\$invocation.receipt.json") -Encoding UTF8
    $output = $outputTask.Result + $errorTask.Result
    $process.Dispose()
    return @{code=$code; output=$output}
}
