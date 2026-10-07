# Windows Bench 派生镜像 —— wfflab__wtask-216
#
# 硬性要求（规范 5.3 + 7.x）：
#   1. 真实 Windows Runtime，不用 Linux Mock 或普通容器替代
#   2. 依赖版本锁定，断网可复现
#   3. 从 HEAD 建立可回放的基线 commit（固定提交时间，不使用 wall-clock）
#   4. environment/ 严禁泄漏 Solution 与隐藏测试
#
# 说明：本题的被测包是自包含的纯 Python 库；被测语义（Task Scheduler 日程语义、
# ISO-8601 时长规范形式、规范化 XML 序列化）都是确定性的纯逻辑行为，
# 不依赖任何外部服务、后台进程或真实系统计划任务。

FROM mcr.microsoft.com/windows/servercore:ltsc2022

SHELL ["powershell", "-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", "$ErrorActionPreference = 'Stop'; $ProgressPreference = 'SilentlyContinue';"]

# --- 1. Git：模型补丁捕获与回放必需 ---
RUN if (-not (Get-Command git.exe -ErrorAction SilentlyContinue)) { \
      Set-ExecutionPolicy Bypass -Scope Process -Force; \
      [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; \
      iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1')); \
      choco install git -y --no-progress; \
    }

# --- 2. Python 3.12.9（embed 包，版本锁定） ---
RUN $pythonDir = 'C:\Python312'; \
    Invoke-WebRequest -UseBasicParsing -Uri 'https://www.python.org/ftp/python/3.12.9/python-3.12.9-embed-amd64.zip' -OutFile C:\python.zip; \
    Expand-Archive C:\python.zip -DestinationPath $pythonDir; \
    Remove-Item C:\python.zip -Force; \
    (Get-Content "$pythonDir\python312._pth") -replace '#import site', 'import site' | Set-Content "$pythonDir\python312._pth"; \
    Invoke-WebRequest -UseBasicParsing -Uri 'https://bootstrap.pypa.io/get-pip.py' -OutFile C:\get-pip.py; \
    & "$pythonDir\python.exe" C:\get-pip.py; \
    Remove-Item C:\get-pip.py -Force

ENV PATH="C:\\Python312;C:\\Python312\\Scripts;C:\\Program Files\\Git\\cmd;${PATH}"

# --- 3. 测试依赖（版本锁定，与题包本机验证环境一致） ---
RUN & 'C:\Python312\python.exe' -m pip install --no-cache-dir \
      'pytest==8.3.5' 'pytest-json-report==1.5.0'

# --- 4. 评分产物目录 ---
RUN New-Item -ItemType Directory -Force C:\logs\verifier | Out-Null

# --- 5. 注入工作区（task-build 以 environment/ 为构建上下文） ---
COPY ["workspace/", "C:/testbed/"]

# --- 6. 环境预检：证明被测包与测试框架真的可用 ---
RUN Set-Location C:\testbed; \
    $env:PYTHONPATH = 'C:\testbed'; \
    python -c "import pytest, wtask"

# --- 7. 基线 commit（固定提交时间 → 确定性 sha，不用 wall-clock） ---
RUN $env:GIT_AUTHOR_DATE = '2026-10-04T00:00:00+00:00'; \
    $env:GIT_COMMITTER_DATE = '2026-10-04T00:00:00+00:00'; \
    if (-not (Test-Path C:\testbed)) { throw 'C:\testbed is missing from the base image' }; \
    Set-Location C:\testbed; \
    if (-not (Test-Path .git)) { git init -q }; \
    git config core.autocrlf false; \
    git add -A; \
    git -c user.email=bench@example.com -c user.name='Terminal Bench' commit --allow-empty -qm baseline

WORKDIR C:\testbed
