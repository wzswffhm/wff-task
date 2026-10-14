# escape=`
FROM mcr.microsoft.com/dotnet/framework/runtime:4.8-windowsservercore-ltsc2019@sha256:3b38924c828aa43995b33124218388f91c0fe2a4f9d7f64723af9e72122e3f7e
SHELL ["powershell.exe", "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", "$ErrorActionPreference = 'Stop'; $ProgressPreference = 'SilentlyContinue';"]
ENV WINBENCH_DISPOSABLE_CONTAINER="1"
WORKDIR C:\testbed
COPY workspace/src/ C:/testbed/src/
COPY build.ps1 C:/testbed/build.ps1
RUN net user BenchAgent /add; `
    if ($LASTEXITCODE -ne 0) { throw 'Agent account creation failed' }; `
    New-Item -ItemType Directory -Force C:\agenttmp | Out-Null; `
    icacls C:\testbed /grant 'BenchAgent:(OI)(CI)RX'; `
    if ($LASTEXITCODE -ne 0) { throw 'Workspace ACL setup failed' }; `
    icacls C:\testbed\src /grant 'BenchAgent:(OI)(CI)M'; `
    if ($LASTEXITCODE -ne 0) { throw 'Source ACL setup failed' }; `
    icacls C:\agenttmp /grant 'BenchAgent:(OI)(CI)M'; `
    if ($LASTEXITCODE -ne 0) { throw 'Scratch ACL setup failed' }; `
    & C:\testbed\build.ps1; `
    Get-ChildItem C:\testbed\bin -Force | Remove-Item -Recurse -Force; `
    icacls C:\testbed\bin /grant 'BenchAgent:(OI)(CI)M'; `
    if ($LASTEXITCODE -ne 0) { throw 'Build output ACL setup failed' }
CMD ["powershell.exe", "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", "while ($true) { Start-Sleep -Seconds 3600 }"]
