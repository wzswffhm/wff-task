# Windows Bench derived image - wfflab__wtoken-221
#
# Hard requirements (spec 5.3 + 7.x):
#   1. real Windows runtime, no Linux mock or cross-platform substitute
#   2. dependency versions pinned and the build performs NO network access
#   3. replayable baseline commit from HEAD (fixed timestamp, no wall clock)
#   4. environment/ never leaks the solution or the hidden tests
#
# Build inputs are vendored under environment/vendor/ (see vendor/INVENTORY.json):
# the Python embed distribution, a pinned MinGit archive and the wheelhouse the
# test runner needs. The base image is addressed by immutable digest.

# The base image is the full Windows Server runtime, addressed by immutable
# digest. It must NOT be a Server Core or Nano Server image: the current project
# policy requires a complete, untrimmed Windows system (>= Server 2019, 2025
# preferred) and explicitly forbids both trimmed families.
#
# ltsc2022 carries os.version 10.0.20348, which is exactly the buyer host build.
# It is also the only complete image that satisfies both constraints at once: a
# build-equal image runs under process isolation on the buyer's 20348 hosts, and
# because 20348 <= every Windows 11 build it also runs under Hyper-V isolation on
# Windows 11 hosts. ltsc2025 (build 26100) would exceed the buyer host build and
# could not start there at all, so the "prefer 2025" guidance yields to the hard
# requirement that the buyer can actually run the image.
FROM mcr.microsoft.com/windows/server:ltsc2022@sha256:7b9f4ac228cf21b6a4f8795e23329442183bd708e3ee55f7b67798481c94f591

SHELL ["powershell", "-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", "$ErrorActionPreference = 'Stop'; $ProgressPreference = 'SilentlyContinue';"]

# --- 1. Git (MinGit 2.56.0.2, vendored; no package manager, no network) ------
COPY ["vendor/MinGit-2.56.0.2-64-bit.zip", "C:/vendor/mingit.zip"]
RUN Expand-Archive -LiteralPath C:\vendor\mingit.zip -DestinationPath C:\Git -Force; \
    Remove-Item C:\vendor\mingit.zip -Force; \
    & C:\Git\cmd\git.exe --version

# --- 2. Python 3.12.9 (embed distribution, vendored) -------------------------
COPY ["vendor/python-3.12.9-embed-amd64.zip", "C:/vendor/python.zip"]
RUN Expand-Archive -LiteralPath C:\vendor\python.zip -DestinationPath C:\Python312 -Force; \
    Remove-Item C:\vendor\python.zip -Force; \
    (Get-Content 'C:\Python312\python312._pth') -replace '#import site', 'import site' | Set-Content 'C:\Python312\python312._pth'; \
    Add-Content 'C:\Python312\python312._pth' 'C:\testbed'; \
    Add-Content 'C:\Python312\python312._pth' 'C:\task\environment\workspace'

ENV PATH="C:/Python312;C:/Python312/Scripts;C:/Git/cmd;C:/Windows/System32;C:/Windows;C:/Windows/System32/WindowsPowerShell/v1.0"

# --- 3. Test dependencies, installed strictly from the vendored wheelhouse ---
# pip itself comes from the wheelhouse too: the embed distribution ships no
# installer, and get-pip.py would need the network. Unpacking the pip wheel into
# site-packages is enough for `python -m pip` to run offline.
COPY ["vendor/wheels/", "C:/vendor/wheels/"]
RUN Add-Type -AssemblyName System.IO.Compression.FileSystem; \
    $sitePackages = 'C:\Python312\Lib\site-packages'; \
    New-Item -ItemType Directory -Force $sitePackages | Out-Null; \
    $pipWheel = (Get-ChildItem C:\vendor\wheels\pip-*.whl | Select-Object -First 1).FullName; \
    [System.IO.Compression.ZipFile]::ExtractToDirectory($pipWheel, $sitePackages); \
    & 'C:\Python312\python.exe' -m pip --version; \
    & 'C:\Python312\python.exe' -m pip install --no-index --find-links C:\vendor\wheels --no-cache-dir --no-warn-script-location 'pytest==8.3.5' 'pytest-json-report==1.5.0'; \
    Remove-Item C:\vendor -Recurse -Force

# --- 4. Verifier output directory -------------------------------------------
RUN New-Item -ItemType Directory -Force C:\logs\verifier | Out-Null

# --- 5. Workspace injection (build context is environment/) ------------------
COPY ["workspace/", "C:/testbed/"]

# --- 6. Build-time smoke check ----------------------------------------------
RUN Set-Location C:\testbed; \
    $env:PYTHONPATH = 'C:\testbed'; \
    & 'C:\Python312\python.exe' -c 'import pytest, wtoken'

# --- 7. Baseline commit (fixed timestamps -> deterministic sha) --------------
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
