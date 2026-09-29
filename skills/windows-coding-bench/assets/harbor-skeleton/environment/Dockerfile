# Windows Bench 派生镜像（Dockerfile 骨架）
#
# 参考来源：Windows_SWE_d70d30df 27 题现包中已验证可用的 Dockerfile 模式
#
# 硬性要求（规范 5.3 + 7.x）：
#   1. 从已烘焙源码与工具链的 base image 派生（不要从纯净 windows 基础镜像从零装）
#   2. 依赖版本锁定，断网可复现（UV_OFFLINE / GOPROXY=off / --no-cache-dir 等）
#   3. 从 HEAD 建立可回放的基线 commit（不要用 wall-clock 标记）
#   4. environment/ 严禁泄漏 Solution 与隐藏测试
#   5. 真实 Windows Runtime 触发验证，不得用 Linux Mock 或普通容器替代

FROM <REGISTRY>/swe-bench-live:<instance-id-variant>

SHELL ["powershell", "-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", "$ErrorActionPreference = 'Stop'; $ProgressPreference = 'SilentlyContinue';"]

# --- 1. Git：模型补丁捕获与回放必需 ---
RUN if (-not (Get-Command git.exe -ErrorAction SilentlyContinue)) { \
      Set-ExecutionPolicy Bypass -Scope Process -Force; \
      [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; \
      iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1')); \
      choco install git -y --no-progress; \
    }

# --- 2. 语言运行时 + 包管理器（版本锁定） ---
# 例：Python 3.12.4 embed + uv 0.8.17；按题目语言调整（Go / Rust / .NET / Node 等）
RUN $pythonDir = 'C:\Python312'; \
    Invoke-WebRequest -UseBasicParsing -Uri 'https://www.python.org/ftp/python/3.12.4/python-3.12.4-embed-amd64.zip' -OutFile C:\python.zip; \
    Expand-Archive C:\python.zip -DestinationPath $pythonDir; \
    Remove-Item C:\python.zip -Force; \
    (Get-Content "$pythonDir\python312._pth") -replace '#import site', 'import site' | Set-Content "$pythonDir\python312._pth"; \
    Invoke-WebRequest -UseBasicParsing -Uri 'https://bootstrap.pypa.io/get-pip.py' -OutFile C:\get-pip.py; \
    & "$pythonDir\python.exe" C:\get-pip.py; \
    Remove-Item C:\get-pip.py -Force; \
    & "$pythonDir\python.exe" -m pip install --no-cache-dir 'uv==0.8.17'

ENV PATH="C:\\Python312;C:\\Python312\\Scripts;C:\\Program Files\\Git\\cmd;${PATH}"
ENV UV_PYTHON="C:\\Python312\\python.exe"

# --- 3. 评测 Harness 预取后转离线 ---
RUN uvx.exe --from 'harbor-rewardkit==0.1.7' rewardkit --help | Out-Null
ENV UV_OFFLINE="1"

# --- 4. 评分产物目录 ---
RUN New-Item -ItemType Directory -Force C:\logs\verifier | Out-Null

# --- 5. 注入工作区（task-build 以 environment/ 为构建上下文） ---
COPY ["workspace/", "C:/testbed/"]

# --- 6. 环境预检：证明依赖真的可用 ---
RUN Set-Location C:\testbed\<package-path>; \
    python -c "import pytest, <your-package>"

# --- 7. 基线 commit（可回放，不用 wall-clock） ---
RUN if (-not (Test-Path C:\testbed)) { throw 'C:\testbed is missing from the base image' }; \
    Set-Location C:\testbed; \
    if (-not (Test-Path .git)) { git init -q }; \
    git add -A; \
    git -c user.email=bench@example.com -c user.name='Terminal Bench' commit --allow-empty -qm baseline

WORKDIR C:\testbed
