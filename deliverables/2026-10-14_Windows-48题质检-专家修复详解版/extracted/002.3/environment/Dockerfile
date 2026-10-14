# escape=`
FROM mcr.microsoft.com/dotnet/sdk:8.0.424-windowsservercore-ltsc2022@sha256:fa7a4d07b90c18a3679139a139121a7e233c328efb7c8c89a89e96edd8c051be
SHELL ["powershell", "-NoLogo", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command"]
COPY . C:/environment/
COPY workspace/ C:/task-state/windows-d6-001/harbor/repo/
ENV HARBOR_REPO_ROOT=C:\task-state\windows-d6-001\harbor\repo OUTSIDE_WORKSPACE=C:\task-state\windows-d6-001\harbor\repo VERIFIER_LOGS_DIR=C:\logs\verifier\results DOTNET_CLI_TELEMETRY_OPTOUT=1 DOTNET_NOLOGO=1
WORKDIR C:\task-state\windows-d6-001\harbor\repo
RUN if ((dotnet --version) -ne '8.0.424') { throw 'SDK version mismatch' }
