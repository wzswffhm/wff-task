# 本地离线构建变体 —— 仅用于本机重跑取证（wfflab__wchunk-216）
#
# 与交付包内的 environment/Dockerfile 逐条等价，唯一差异是三处联网下载改为
# 使用随构建上下文提供的**同一批锁定产物**（本机容器网络暂时无法出外网）：
#   - git          : MinGit 2.51.0（原为 choco install git）
#   - Python 3.12.9: python-3.12.9-embed-amd64.zip（python.org 原始文件，逐字节相同）
#   - get-pip.py   : bootstrap.pypa.io 同名文件（逐字节相同）
#   - pytest       : pytest==8.3.5 / pytest-json-report==1.5.0 及全部依赖 wheel（同一锁定版本）
# 其余步骤（PATH、评分目录、workspace 注入、预检、固定时间基线 commit）与原件完全一致。
FROM mcr.microsoft.com/windows/servercore:ltsc2022

SHELL ["powershell", "-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", "$ErrorActionPreference = 'Stop'; $ProgressPreference = 'SilentlyContinue';"]

# --- 1. Git：模型补丁捕获与回放必需 ---
# MinGit 自带的便携版 etc/gitconfig 会 include 自身，git 读配置时递归超过 10 层直接 fatal；
# 删掉它让系统配置回落到空默认值，任务只需要仓库内的 identity 设置。
COPY ["offline/MinGit.zip", "C:/MinGit.zip"]
RUN Expand-Archive -Path C:\MinGit.zip -DestinationPath 'C:\Program Files\Git' -Force; \
    Remove-Item C:\MinGit.zip -Force; \
    Remove-Item 'C:\Program Files\Git\etc\gitconfig' -Force -ErrorAction SilentlyContinue; \
    & 'C:\Program Files\Git\cmd\git.exe' --version

# --- 2. Python 3.12.9（embed 包，版本锁定） ---
COPY ["offline/python-3.12.9-embed-amd64.zip", "C:/python.zip"]
COPY ["offline/get-pip.py", "C:/get-pip.py"]
COPY ["offline/wheels/", "C:/wheels/"]
RUN $pythonDir = 'C:\Python312'; \
    Expand-Archive C:\python.zip -DestinationPath $pythonDir; \
    Remove-Item C:\python.zip -Force; \
    (Get-Content "$pythonDir\python312._pth") -replace '#import site', 'import site' | Set-Content "$pythonDir\python312._pth"; \
    Add-Content "$pythonDir\python312._pth" 'C:\testbed'; \
    Add-Content "$pythonDir\python312._pth" 'C:\task\environment\workspace'; \
    & "$pythonDir\python.exe" C:\get-pip.py --no-index --find-links C:/wheels; \
    Remove-Item C:\get-pip.py -Force

ENV PATH="C:/Python312;C:/Python312/Scripts;C:/Program Files/Git/cmd;C:/Windows/System32;C:/Windows;C:/Windows/System32/WindowsPowerShell/v1.0"

# --- 3. 测试依赖（版本锁定，与题包本机验证环境一致） ---
RUN & 'C:\Python312\python.exe' -m pip install --no-cache-dir --no-index \
      --find-links C:/wheels 'pytest==8.3.5' 'pytest-json-report==1.5.0'

# --- 4. 评分产物目录 ---
RUN New-Item -ItemType Directory -Force C:\logs\verifier | Out-Null

# --- 5. 注入工作区（task-build 以 environment/ 为构建上下文） ---
COPY ["workspace/", "C:/testbed/"]

# --- 6. 环境预检：证明被测包与测试框架真的可用 ---
RUN Set-Location C:\testbed; \
    $env:PYTHONPATH = 'C:\testbed'; \
    & 'C:\Python312\python.exe' -c 'import pytest, wchunk'

# --- 7. 基线 commit（固定提交时间 → 确定性 sha，不用 wall-clock） ---
RUN $env:GIT_AUTHOR_DATE = '2026-10-03T00:00:00+00:00'; \
    $env:GIT_COMMITTER_DATE = '2026-10-03T00:00:00+00:00'; \
    if (-not (Test-Path C:\testbed)) { throw 'C:\testbed is missing from the base image' }; \
    Set-Location C:\testbed; \
    git config --global --add safe.directory C:/testbed; \
    if (-not (Test-Path .git)) { git init -q }; \
    git config core.autocrlf false; \
    git add -A; \
    git -c user.email=bench@example.com -c user.name='Terminal Bench' commit --allow-empty -qm baseline

WORKDIR C:/testbed
