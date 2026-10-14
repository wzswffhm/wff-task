# escape=`
FROM mcr.microsoft.com/dotnet/sdk:8.0.424-windowsservercore-ltsc2022@sha256:fa7a4d07b90c18a3679139a139121a7e233c328efb7c8c89a89e96edd8c051be

SHELL ["powershell", "-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command"]

ENV HARBOR_TASK_ID=windows-d4-litemonitor-001 `
    HARBOR_TASK_VERSION=2.1.2 `
    HARBOR_IMAGE_ROLE=agent `
    HARBOR_ENVIRONMENT_TIER=E1 `
    HARBOR_BASE_IMAGE_DIGEST=sha256:fa7a4d07b90c18a3679139a139121a7e233c328efb7c8c89a89e96edd8c051be `
    HARBOR_BASELINE_COMMIT=48d4c10b876ed5118fa321c1824e0503858269af `
    HARBOR_BASELINE_ZIP_SHA256=c6945e9a6102d907004c3362b61dad64b17a40554b6de25251576cc25cd342e5 `
    HARBOR_UPSTREAM_COMMIT=169e90a2ccaa68ca29d0b549d10c6c59634c1b49 `
    HARBOR_IMAGE_STAMP=C:\harbor\image_stamp.json `
    HARBOR_WORKSPACE_ROOT=C:\harbor\workspace `
    DOTNET_CLI_TELEMETRY_OPTOUT=1 `
    DOTNET_NOLOGO=1 `
    DOTNET_SKIP_FIRST_TIME_EXPERIENCE=1 `
    NUGET_XMLDOC_MODE=skip

WORKDIR C:\harbor

COPY environment/assets/nuget/ C:/harbor/assets/nuget/
COPY environment/nuget.config C:/harbor/nuget.config
ENV NUGET_PACKAGES=C:\harbor\nuget-packages

COPY environment/assets/baseline-repo.zip C:/harbor/assets/baseline-repo.zip
COPY environment/assets/vendor/ C:/harbor/assets/vendor/
COPY instruction.md C:/harbor/task/instruction.md
COPY task.toml C:/harbor/task/task.toml
COPY environment/ C:/harbor/task/environment/

# AP invokes environment validation at C:\environment and expects a repository
# that can be discovered and patched at an ASCII-only C:\workspace path.
COPY environment/ C:/environment/

RUN powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -File C:\harbor\task\environment\build_image.ps1 -Role agent
RUN . C:\harbor\task\environment\env_common.ps1; `
    $repo = Get-DefaultRepoRoot -WorkspaceRoot C:\harbor\workspace; `
    if (-not (Test-Path -LiteralPath (Join-Path $repo 'LiteMonitor.csproj'))) { throw 'frozen LiteMonitor repository is missing' }; `
    if (Test-Path -LiteralPath C:\workspace) { throw 'AP workspace destination already exists' }; `
    Copy-Item -LiteralPath $repo -Destination C:\workspace -Recurse -Force

ENV HARBOR_REPO_ROOT=C:\workspace
WORKDIR C:\workspace

CMD ["powershell", "-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", "Write-Host 'Harbor E1 Agent executor for windows-d4-litemonitor-001'"]
