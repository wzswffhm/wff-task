# escape=`
FROM mcr.microsoft.com/windows/servercore:2004@sha256:1241480fc719b88dbe0f482806d4f67ab90e10752ddd56c014f9a801d3aac991
USER ContainerAdministrator
SHELL ["powershell.exe", "-NoLogo", "-NoProfile", "-NonInteractive", "-Command"]
COPY toolchain/python-3.12.14-stdlib.zip C:/runtime/python.zip
RUN $ErrorActionPreference='Stop'; Expand-Archive C:/runtime/python.zip C:/Python; Remove-Item C:/runtime/python.zip
COPY toolchain/powershell/ C:/PowerShell/
ENV PATH="C:\PowerShell;C:\Python;C:\Windows\System32\WindowsPowerShell\v1.0;C:\Windows\System32;C:\Windows"
ENV PYTHONUTF8=1
COPY workspace/ C:/task/environment/workspace/
COPY *.ps1 C:/task/environment/
COPY environment.lock.json C:/task/environment/
WORKDIR C:/task
RUN $ErrorActionPreference='Stop'; Set-Culture zh-CN; `
    New-Item -ItemType Directory -Force C:/logs/agent,C:/logs/verifier,C:/logs/artifacts,C:/tests | Out-Null; `
    & icacls.exe C:/task /grant '*S-1-5-93-2-2:(OI)(CI)M' /T | Out-Null; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }; `
    & icacls.exe C:/tests /inheritance:r /grant:r '*S-1-5-18:(OI)(CI)F' '*S-1-5-32-544:(OI)(CI)F' /T | Out-Null; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }; `
    & icacls.exe C:/logs/verifier /inheritance:r /grant:r '*S-1-5-18:(OI)(CI)F' '*S-1-5-32-544:(OI)(CI)F' /T | Out-Null; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }; `
    & icacls.exe C:/logs/agent /grant '*S-1-5-93-2-2:(OI)(CI)M' /T | Out-Null; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }; `
    & C:/PowerShell/pwsh.exe -NoLogo -NoProfile -NonInteractive -File C:/task/environment/validate_environment.ps1; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
# Harbor's Windows tar transport uses the image user. Keep transport privileged;
# task.toml explicitly runs the Agent as ContainerUser and Verifier as admin.
USER ContainerAdministrator
