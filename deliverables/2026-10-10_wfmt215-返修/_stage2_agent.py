"""Stage 2: rewrite the agent-visible package.

Files written here:
  solution/README.md
  environment/workspace/README.md
  environment/agent_visible_paths.json
  environment/Dockerfile
  environment/adapter.toml
  environment/validate_environment.ps1
  tests/run_tests.ps1
  tests/aggregate_results.ps1
  tests/rubric.json
  tests/judge.toml
  task.toml

Every .ps1/.bat stays pure ASCII: Windows PowerShell 5.1 decodes BOM-less
script files as ANSI, and multi-byte comments swallow the following newline.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(r"C:\Users\Administrator\Desktop\wff-task\deliverables\2026-10-10_wfmt215-返修")
TASK = ROOT / "build" / "outside_harbor-assets" / "wfflab__wfmt-215"
TASK_ID = "wfflab__wfmt-215"
TASK_VERSION = "2.1.0"
BASE_IMAGE = (
    "mcr.microsoft.com/windows/servercore:ltsc2022"
    "@sha256:76cf422c98ca437b308374d0498280541fa42ac7061bb44015a6c8b70cf4db6a"
)

PROGRAMMATIC = [
    ("sample-compatibility", 0.10, [
        "f2p-sample-verifies",
        "f2p-sample-roundtrip-is-byte-identical",
        "f2p-sample-records-match-expected",
    ]),
    ("checksum-semantics", 0.10, [
        "f2p-crc-matches-standard-check-value",
        "f2p-tampered-content-is-rejected",
        "f2p-checksum-covers-header-and-records",
    ]),
    ("error-classification", 0.10, [
        "f2p-truncated-container-is-reported-as-truncated",
        "p2p-bad-magic-is-reported-as-magic",
        "p2p-verify-never-raises",
    ]),
    ("streaming", 0.075, [
        "f2p-iter-records-is-streaming",
        "p2p-truncated-stream-is-reported-as-truncated",
        "p2p-read-all-matches-unpack",
    ]),
    ("roundtrip-robustness", 0.125, [
        "p2p-self-roundtrip-small-records",
        "p2p-empty-payload-roundtrip",
        "p2p-pack-verify-agrees-for-generated-data",
    ]),
]

LLM_JUDGE = [
    ("contract-preservation", 0.15),
    ("implementation-quality", 0.15),
    ("anti-shortcut-discipline", 0.10),
    ("verification-report", 0.10),
]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_text(rel: str, text: str, crlf: bool = False) -> None:
    path = TASK / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    if crlf:
        text = text.replace("\r\n", "\n").replace("\n", "\r\n")
    with path.open("w", encoding="utf-8", newline="") as handle:
        handle.write(text)
    print(f"write {rel} ({len(text)} chars)")


def write_ascii_script(rel: str, text: str) -> None:
    try:
        text.encode("ascii")
    except UnicodeEncodeError as exc:  # pragma: no cover - guarded on purpose
        raise SystemExit(f"{rel} is not pure ASCII: {exc}")
    write_text(rel, text, crlf=True)


# --------------------------------------------------------------------------- #
# solution/README.md
# --------------------------------------------------------------------------- #
SOLUTION_README = """# Golden 入口（参考解不随本题包交付）

本目录只保留 Golden / Oracle 控制跑所需的入口脚本，**不含参考答案**：
参考实现本体（`reference/`）、补丁（`oracle.patch`）与判据明细均已移出
Agent 可见题包，改由评测侧在判分阶段注入到独立目录。

## 目录内容

| 文件 | 作用 |
| --- | --- |
| `solve.ps1` | 定位并安装判分侧注入的参考实现到候选工作区 |
| `solve.bat` | 标准 Harbor 的 `.bat` 入口，委托 `solve.ps1` |

## 参考实现的查找顺序

`solve.ps1` 按以下顺序查找参考实现目录（命中即用）：

1. `-ReferenceRoot <dir>` 参数；
2. 环境变量 `WFMT_REFERENCE_ROOT`；
3. `C:\\solution\\reference\\wfmt`（评测平台注入点）；
4. `<包根>\\outside_harbor-verifier\\wfflab__wfmt-215\\oracle\\reference\\wfmt`
   —— 与 Agent 可见题包**平级**的判分侧目录，仅在本地复现时使用。

找不到参考实现时脚本以退出码 1 结束，不会退化成"跳过 Oracle"。
"""

# --------------------------------------------------------------------------- #
# environment/workspace/README.md
# --------------------------------------------------------------------------- #
WORKSPACE_README = """# wfmt 工作区

采集器的落盘容器格式实现。模块布局：

```
wfmt/
  errors.py     # WFormatError（kind 标记）
  varint.py     # 无符号变长整数编解码
  crc.py        # 尾部校验和
  header.py     # 文件头
  codec.py      # 记录编解码 + 整份容器 pack/unpack/verify
  stream.py     # 流式读取 iter_records / read_all
tests/
  test_wfmt_basic.py    # 可见的冒烟测试（只覆盖最基础往返）
docs/
  FORMAT.md             # 早期格式草稿（见下方警告）
assets/
  sample.wfmt           # 权威样本（外部采集器落盘的真实文件）
  sample_empty.wfmt     # 零记录样本
```

## ⚠️ 关于 docs/FORMAT.md

`docs/FORMAT.md` 是格式设计**早期**的草稿，之后实现与样本都改动过若干次，
**它现在与真实字节布局不一致**，不要按它实现。

判断格式的唯一依据是 `assets/` 下的样本：正确的实现必须能做到

1. `verify(open("assets/sample.wfmt","rb").read()) is True`；
2. `pack(unpack(sample)) == sample`（逐字节一致）。

换句话说：**样本就是规范**。

## 运行可见测试

```
python -m pytest tests\\test_wfmt_basic.py
```

可见冒烟测试只验证「自己写的数据自己能读回来」，**它全绿不代表格式正确**。

修复时不要改动公开 API 的名称与签名。
"""

# --------------------------------------------------------------------------- #
# environment/agent_visible_paths.json
# --------------------------------------------------------------------------- #
AGENT_VISIBLE = {
    "schema_version": "agent-visible-paths-v1",
    "task_id": TASK_ID,
    "task_version": TASK_VERSION,
    "agent_runtime": {
        "host_os": "windows",
        "image": BASE_IMAGE,
        "workspace_root": "C:\\testbed",
        "path": "C:/Python312;C:/Python312/Scripts;C:/Git/cmd;C:/Windows/System32;C:/Windows",
    },
    "visible_in_agent_container": [
        {"path": "C:\\testbed", "mode": "read-write", "note": "candidate workspace; the only writable surface"},
        {"path": "C:\\testbed\\wfmt", "mode": "read-write", "note": "mutable package sources"},
        {"path": "C:\\testbed\\assets", "mode": "read-only", "note": "authoritative samples"},
        {"path": "C:\\testbed\\docs", "mode": "read-only"},
        {"path": "C:\\testbed\\tests", "mode": "read-only", "note": "visible smoke test only"},
    ],
    "not_present_in_agent_container": [
        {"path": "C:\\solution", "note": "oracle reference payload, injected only for the Golden control"},
        {"path": "C:\\verifier", "note": "hidden behavioural suite and rubric conditions"},
        {"path": "oracle.patch", "note": "ships outside the agent-visible package"},
        {"path": "outside_harbor-verifier/", "note": "package-root sibling, never mounted into the task root"},
    ],
    "evidence": [
        "environment/Dockerfile copies workspace/ only; no answer or hidden-suite path is part of the image",
        "environment/validate_environment.ps1 fails the readiness probe when withheld material is visible",
        "solution/ ships entry points only; the reference payload is resolved from an injected path at Oracle time",
    ],
}

# --------------------------------------------------------------------------- #
# environment/Dockerfile
# --------------------------------------------------------------------------- #
DOCKERFILE = """# Windows Bench derived image - wfflab__wfmt-215
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

FROM {base_image}

SHELL ["powershell", "-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", "$ErrorActionPreference = 'Stop'; $ProgressPreference = 'SilentlyContinue';"]

# --- 1. Git (MinGit 2.56.0.2, vendored; no package manager, no network) ------
COPY ["vendor/MinGit-2.56.0.2-64-bit.zip", "C:/vendor/mingit.zip"]
RUN Expand-Archive -LiteralPath C:\\vendor\\mingit.zip -DestinationPath C:\\Git -Force; \\
    Remove-Item C:\\vendor\\mingit.zip -Force; \\
    & C:\\Git\\cmd\\git.exe --version

# --- 2. Python 3.12.9 (embed distribution, vendored) -------------------------
COPY ["vendor/python-3.12.9-embed-amd64.zip", "C:/vendor/python.zip"]
RUN Expand-Archive -LiteralPath C:\\vendor\\python.zip -DestinationPath C:\\Python312 -Force; \\
    Remove-Item C:\\vendor\\python.zip -Force; \\
    (Get-Content 'C:\\Python312\\python312._pth') -replace '#import site', 'import site' | Set-Content 'C:\\Python312\\python312._pth'; \\
    Add-Content 'C:\\Python312\\python312._pth' 'C:\\testbed'; \\
    Add-Content 'C:\\Python312\\python312._pth' 'C:\\task\\environment\\workspace'

ENV PATH="C:/Python312;C:/Python312/Scripts;C:/Git/cmd;C:/Windows/System32;C:/Windows;C:/Windows/System32/WindowsPowerShell/v1.0"

# --- 3. Test dependencies, installed strictly from the vendored wheelhouse ---
# pip itself comes from the wheelhouse too: the embed distribution ships no
# installer, and get-pip.py would need the network. Unpacking the pip wheel into
# site-packages is enough for `python -m pip` to run offline.
COPY ["vendor/wheels/", "C:/vendor/wheels/"]
RUN Add-Type -AssemblyName System.IO.Compression.FileSystem; \\
    $sitePackages = 'C:\\Python312\\Lib\\site-packages'; \\
    New-Item -ItemType Directory -Force $sitePackages | Out-Null; \\
    $pipWheel = (Get-ChildItem C:\\vendor\\wheels\\pip-*.whl | Select-Object -First 1).FullName; \\
    [System.IO.Compression.ZipFile]::ExtractToDirectory($pipWheel, $sitePackages); \\
    & 'C:\\Python312\\python.exe' -m pip --version; \\
    & 'C:\\Python312\\python.exe' -m pip install --no-index --find-links C:\\vendor\\wheels --no-cache-dir --no-warn-script-location 'pytest==8.3.5' 'pytest-json-report==1.5.0'; \\
    Remove-Item C:\\vendor -Recurse -Force

# --- 4. Verifier output directory -------------------------------------------
RUN New-Item -ItemType Directory -Force C:\\logs\\verifier | Out-Null

# --- 5. Workspace injection (build context is environment/) ------------------
COPY ["workspace/", "C:/testbed/"]

# --- 6. Build-time smoke check ----------------------------------------------
RUN Set-Location C:\\testbed; \\
    $env:PYTHONPATH = 'C:\\testbed'; \\
    & 'C:\\Python312\\python.exe' -c 'import pytest, wfmt'

# --- 7. Baseline commit (fixed timestamps -> deterministic sha) --------------
RUN $env:GIT_AUTHOR_DATE = '2026-10-03T00:00:00+00:00'; \\
    $env:GIT_COMMITTER_DATE = '2026-10-03T00:00:00+00:00'; \\
    if (-not (Test-Path C:\\testbed)) {{ throw 'C:\\testbed is missing from the base image' }}; \\
    Set-Location C:\\testbed; \\
    git config --global --add safe.directory C:/testbed; \\
    if (-not (Test-Path .git)) {{ git init -q }}; \\
    git config core.autocrlf false; \\
    git add -A; \\
    git -c user.email=bench@example.com -c user.name='Terminal Bench' commit --allow-empty -qm baseline

WORKDIR C:/testbed
""".format(base_image=BASE_IMAGE)

# --------------------------------------------------------------------------- #
# environment/adapter.toml
# --------------------------------------------------------------------------- #
ADAPTER = """# Runtime binding for the local Outside Harbor runner. The runner reads this file
# to build, prepare, drive and clean the task inside a Windows container, so the
# same task tree can be executed without any host-specific path baked into it.
schema_version = "outside-harbor-adapter-v1"
task_id = "wfflab__wfmt-215"
task_version = "2.1.0"

[container]
engine = "windows"
# Immutable digest, not a floating tag.
image = "{base_image}"
task_root = 'C:\\task'
workspace_root = 'C:\\task\\environment\\workspace'
shell = "powershell"
shell_flags = ["-NoProfile", "-ExecutionPolicy", "Bypass", "-NonInteractive"]

[isolation]
# The agent may only change the package sources. Everything below is enforced by
# the image build (only workspace/ is copied) and checked again by the readiness
# probe, which fails when withheld material is reachable from the agent.
# The machine-readable list lives in environment/agent_visible_paths.json.
agent_visible_paths = ['C:\\task\\environment\\workspace']
agent_read_only_paths = ['C:\\task\\instruction.md', 'C:\\task\\environment\\workspace\\docs', 'C:\\task\\environment\\workspace\\assets', 'C:\\task\\environment\\workspace\\tests']
withheld_paths = ['C:\\task\\tests', 'C:\\task\\solution', 'C:\\solution', 'C:\\verifier']

[prepare]
# Runs exactly once per run, before the test entry point.
command = 'powershell -NoProfile -ExecutionPolicy Bypass -NonInteractive -File C:\\task\\environment\\prepare.ps1'
timeout_sec = 900

[validate]
# Readiness probe; a non-zero exit means the environment cannot host the task.
command = 'powershell -NoProfile -ExecutionPolicy Bypass -NonInteractive -File C:\\task\\environment\\validate_environment.ps1'
timeout_sec = 900

[exec_agent]
# The candidate may only touch the package sources. Everything else in the task
# tree stays authoritative and must not be rewritten.
writable_paths = ['C:\\task\\environment\\workspace\\wfmt']
protected_paths = ['C:\\task\\instruction.md', 'C:\\task\\environment\\prepare.ps1', 'C:\\task\\environment\\run.ps1', 'C:\\task\\environment\\workspace\\docs', 'C:\\task\\environment\\workspace\\assets']

[test]
command = 'powershell -NoProfile -ExecutionPolicy Bypass -NonInteractive -File C:\\task\\environment\\run.ps1'
result_path = 'results/result.json'
checks_path = 'results/checks.json'
timeout_sec = 7200

[restore]
command = 'powershell -NoProfile -ExecutionPolicy Bypass -NonInteractive -File C:\\task\\environment\\restore.ps1'
timeout_sec = 900

[cleanup]
command = 'powershell -NoProfile -ExecutionPolicy Bypass -NonInteractive -File C:\\task\\environment\\cleanup.ps1'
timeout_sec = 900
""".format(base_image=BASE_IMAGE)

# --------------------------------------------------------------------------- #
# environment/validate_environment.ps1
# --------------------------------------------------------------------------- #
VALIDATE = """# Generated for wfflab__wfmt-215 by the task authoring pipeline.
#
# Readiness probe: answers whether this machine can host the task. It reports on
# the platform, the PowerShell runtime, the interpreter, the candidate package
# and the authoritative samples, and it never scores the candidate.
#
# It also proves the isolation claim: withheld material (the oracle reference
# payload and the hidden behavioural suite) must not be reachable from the
# agent-visible tree. A hit fails the probe instead of being reported as a
# warning.
#
# Exit codes:
#   0  the environment is ready
#   1  the environment is not ready (details on stdout)

[CmdletBinding()]
param(
    [string]$TaskRoot = ''
)

$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($TaskRoot)) {
    $TaskRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
}
$TaskRoot = (Resolve-Path -LiteralPath $TaskRoot).Path

$problems = New-Object System.Collections.ArrayList

if ([System.Environment]::OSVersion.Platform -ne [System.PlatformID]::Win32NT) {
    [void]$problems.Add('the host platform is not Windows')
}

if ($PSVersionTable.PSVersion.Major -lt 5) {
    [void]$problems.Add("Windows PowerShell 5.1 or later is required (found $($PSVersionTable.PSVersion))")
}

$python = (Get-Command python -ErrorAction SilentlyContinue)
if (-not $python) { $python = (Get-Command python3 -ErrorAction SilentlyContinue) }
if (-not $python) {
    [void]$problems.Add('no python interpreter is available on PATH')
}
else {
    & $python.Source -c "import pytest" 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) { [void]$problems.Add('the pytest package is not importable') }
}

$workspace = Join-Path $TaskRoot 'environment\\workspace'
$packageInit = Join-Path (Join-Path $workspace 'wfmt') '__init__.py'
if (-not (Test-Path -LiteralPath $packageInit)) {
    [void]$problems.Add("the candidate package is missing: $packageInit")
}
else {
    $env:PYTHONPATH = "$workspace;$env:PYTHONPATH"
    & $python.Source -c "import wfmt" 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) { [void]$problems.Add('the candidate package cannot be imported') }
}

foreach ($sample in @((Join-Path 'assets' 'sample.wfmt'), (Join-Path 'assets' 'sample_empty.wfmt'))) {
    if (-not (Test-Path -LiteralPath (Join-Path $workspace $sample))) {
        [void]$problems.Add("the authoritative sample is missing: $sample")
    }
}

# ---- isolation audit --------------------------------------------------------
# 1. Inside the agent-visible workspace nothing may look like an answer or a
#    hidden suite.
$leaked = New-Object System.Collections.ArrayList
foreach ($item in @(Get-ChildItem -LiteralPath $workspace -Recurse -File -Force -ErrorAction SilentlyContinue)) {
    $name = $item.Name.ToLowerInvariant()
    if ($name -match 'oracle|golden|reference|hidden|rubric|solution|reward') {
        [void]$leaked.Add($item.FullName)
    }
}
foreach ($item in $leaked) { [void]$problems.Add("agent workspace contains withheld material: $item") }

# 2. The verifier-side and oracle-side roots must be outside the agent-visible
#    tree. They are injected for grading only; if they resolve inside the
#    workspace the packaging is wrong.
foreach ($forbidden in @('C:\\verifier', 'C:\\solution')) {
    if (-not (Test-Path -LiteralPath $forbidden)) { continue }
    $resolved = (Resolve-Path -LiteralPath $forbidden).Path
    if ($resolved.ToLowerInvariant().StartsWith($workspace.ToLowerInvariant())) {
        [void]$problems.Add("withheld root is inside the agent workspace: $resolved")
    }
}

if ($problems.Count -gt 0) {
    foreach ($problem in $problems) { Write-Host "NOT READY: $problem" }
    exit 1
}

Write-Host "ready: $env:COMPUTERNAME / PowerShell $($PSVersionTable.PSVersion) / task root $TaskRoot"
Write-Host 'isolation: agent workspace is free of oracle, reference and hidden-suite material'
exit 0
"""

# --------------------------------------------------------------------------- #
# tests/run_tests.ps1
# --------------------------------------------------------------------------- #
RUN_TESTS = """# Generated for wfflab__wfmt-215 by the task authoring pipeline.
#
# Objective checks for the wfmt container-format behaviour contract. The hidden
# semantic suite is injected by the evaluation side and executed against the
# candidate package with pytest; its per-test outcome is mapped onto stable
# check ids. Scoring is delegated to aggregate_results.ps1.
#
# The suite is deliberately NOT part of this package: it is resolved from a
# verifier-side root. See agent_visible_paths.json.
#
# Exit codes:
#   0  every check passed
#   1  at least one check failed (functional failure)
#   2  the harness itself could not run (infrastructure failure)

[CmdletBinding()]
param(
    [string]$WorkspaceRoot = '',
    [string]$ChecksPath = '',
    [string]$TaskRoot = '',
    [string]$VerifierRoot = ''
)

$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($TaskRoot)) {
    $TaskRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
}
$TaskRoot = (Resolve-Path -LiteralPath $TaskRoot).Path
if ([string]::IsNullOrWhiteSpace($WorkspaceRoot)) { $WorkspaceRoot = Join-Path $TaskRoot 'environment\\workspace' }
if ([string]::IsNullOrWhiteSpace($ChecksPath)) { $ChecksPath = Join-Path (Join-Path $TaskRoot 'results') ('checks' + '.json') }

function Resolve-HiddenSuite([string]$Root) {
    if ([string]::IsNullOrWhiteSpace($Root)) { return '' }
    foreach ($relative in @('tests\\test_wfmt_semantics.py', 'test_wfmt_semantics.py')) {
        $candidate = Join-Path $Root $relative
        if (Test-Path -LiteralPath $candidate) { return (Resolve-Path -LiteralPath $candidate).Path }
    }
    return ''
}

$verifierCandidates = New-Object System.Collections.ArrayList
if (-not [string]::IsNullOrWhiteSpace($VerifierRoot)) { [void]$verifierCandidates.Add($VerifierRoot) }
if (-not [string]::IsNullOrWhiteSpace($env:WFMT_VERIFIER_ROOT)) { [void]$verifierCandidates.Add($env:WFMT_VERIFIER_ROOT) }
[void]$verifierCandidates.Add('C:\\verifier\\wfflab__wfmt-215')
[void]$verifierCandidates.Add('C:\\verifier')
$packageRoot = Split-Path -Parent $TaskRoot
if (-not [string]::IsNullOrWhiteSpace($packageRoot)) {
    [void]$verifierCandidates.Add((Join-Path $packageRoot 'outside_harbor-verifier\\wfflab__wfmt-215'))
}

$hiddenSuite = ''
foreach ($candidate in $verifierCandidates) {
    $hiddenSuite = Resolve-HiddenSuite $candidate
    if (-not [string]::IsNullOrWhiteSpace($hiddenSuite)) { break }
}

# ---- infrastructure preconditions -----------------------------------------
if (-not (Test-Path -LiteralPath (Join-Path (Join-Path $WorkspaceRoot 'wfmt') '__init__.py'))) {
    Write-Host "INVALID: candidate package not found under $WorkspaceRoot"
    exit 2
}
if ([string]::IsNullOrWhiteSpace($hiddenSuite)) {
    Write-Host 'INVALID: the verifier-side hidden semantic suite was not injected'
    exit 2
}
Write-Host "verifier: hidden suite resolved to $hiddenSuite"

# The graded suite runs against a scratch copy so that pytest artefacts never
# touch the (possibly read-only) workspace and so a stale cache cannot leak in.
$runRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('wfmt-graded-' + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $runRoot -Force | Out-Null

try {
    & robocopy $WorkspaceRoot $runRoot /E /XD .git __pycache__ .pytest_cache reports /XF *.pyc /NFL /NDL /NJH /NJS /NP | Out-Null
    if ($LASTEXITCODE -ge 8) {
        Write-Host "INVALID: staging the candidate workspace failed (robocopy $LASTEXITCODE)"
        exit 2
    }
    $global:LASTEXITCODE = 0

    $testsDir = Join-Path $runRoot 'tests'
    if (-not (Test-Path -LiteralPath $testsDir)) { New-Item -ItemType Directory -Path $testsDir -Force | Out-Null }
    Copy-Item -LiteralPath $hiddenSuite -Destination (Join-Path $testsDir 'test_wfmt_semantics.py') -Force

    # The embed interpreter isolates sys.path through python312._pth, so PYTHONPATH
    # alone is not enough. Drop a conftest that prepends the scratch root so that
    # `import wfmt` resolves against the staged candidate package.
    $conftest = @'
import pathlib
import sys

_root = str(pathlib.Path(__file__).resolve().parent)
if _root not in sys.path:
    sys.path.insert(0, _root)
'@
    Set-Content -LiteralPath (Join-Path $runRoot 'conftest.py') -Value $conftest -Encoding UTF8

    $reportPath = Join-Path $runRoot ('pytest-results' + '.json')
    $python = (Get-Command python -ErrorAction SilentlyContinue)
    if (-not $python) { $python = (Get-Command python3 -ErrorAction SilentlyContinue) }
    if (-not $python) {
        Write-Host 'INVALID: no python interpreter is available on PATH'
        exit 2
    }

    $env:PYTHONPATH = "$runRoot;$env:PYTHONPATH"
    Push-Location -LiteralPath $runRoot
    try {
        & $python.Source -m pytest -rA --tb=short -p no:cacheprovider --json-report --json-report-file=$reportPath (Join-Path 'tests' 'test_wfmt_semantics.py') 2>&1 | Out-Host
    }
    finally {
        Pop-Location
    }

    if (-not (Test-Path -LiteralPath $reportPath)) {
        Write-Host 'INVALID: pytest produced no json report'
        exit 2
    }

    $doc = Get-Content -LiteralPath $reportPath -Raw -Encoding UTF8 | ConvertFrom-Json

    # Map the pytest node ids onto the stable contract check ids.
    $slugByFunction = [ordered]@{
        'test_sample_verifies'                          = 'sample-verifies'
        'test_sample_roundtrip_is_byte_identical'       = 'sample-roundtrip-is-byte-identical'
        'test_sample_records_match_expected'            = 'sample-records-match-expected'
        'test_crc_matches_standard_check_value'         = 'crc-matches-standard-check-value'
        'test_tampered_content_is_rejected'             = 'tampered-content-is-rejected'
        'test_checksum_covers_header_and_records'       = 'checksum-covers-header-and-records'
        'test_truncated_container_is_reported_as_truncated' = 'truncated-container-is-reported-as-truncated'
        'test_truncated_stream_is_reported_as_truncated'    = 'truncated-stream-is-reported-as-truncated'
        'test_bad_magic_is_reported_as_magic'           = 'bad-magic-is-reported-as-magic'
        'test_verify_never_raises'                      = 'verify-never-raises'
        'test_iter_records_is_streaming'                = 'iter-records-is-streaming'
        'test_self_roundtrip_small_records'             = 'self-roundtrip-small-records'
        'test_empty_payload_roundtrip'                  = 'empty-payload-roundtrip'
        'test_pack_verify_agrees_for_generated_data'    = 'pack-verify-agrees-for-generated-data'
        'test_read_all_matches_unpack'                  = 'read-all-matches-unpack'
    }

    $observed = @{}
    foreach ($test in @($doc.tests)) {
        $nodeId = [string]$test.nodeid
        if ([string]::IsNullOrWhiteSpace($nodeId)) { continue }
        $function = ($nodeId -split '::')[-1]
        if (-not $slugByFunction.Contains($function)) { continue }
        $slug = [string]$slugByFunction[$function]
        $outcome = ([string]$test.outcome).ToLowerInvariant()
        $status = if ($outcome -eq 'passed' -or $outcome -eq 'xpassed') { 'PASS' } else { 'FAIL' }
        $observed[$slug] = @{ Status = $status; Detail = "pytest outcome=$outcome" }
    }

    $results = New-Object System.Collections.ArrayList
    foreach ($entry in $slugByFunction.GetEnumerator()) {
        $slug = [string]$entry.Value
        if ($observed.ContainsKey($slug)) {
            $state = $observed[$slug]
            [void]$results.Add([pscustomobject][ordered]@{ test_id = $slug; status = $state.Status; detail = $state.Detail })
        }
        else {
            # A required check that the suite never reported is a failure of the
            # candidate contract (missing collection), not an infrastructure fault.
            [void]$results.Add([pscustomobject][ordered]@{ test_id = $slug; status = 'FAIL'; detail = 'required check was not collected' })
        }
    }

    $checksDirectory = Split-Path -Parent $ChecksPath
    if (-not (Test-Path -LiteralPath $checksDirectory)) { New-Item -ItemType Directory -Path $checksDirectory -Force | Out-Null }

    $payload = [pscustomobject][ordered]@{
        task_id      = 'wfflab__wfmt-215'
        task_version = '2.1.0'
        checks       = @($results.ToArray())
    }
    $payload | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $ChecksPath -Encoding UTF8

    $failed = @($results | Where-Object { $_.status -ne 'PASS' }).Count
    Write-Host ("checks: {0} passed, {1} failed, {2} total" -f ($results.Count - $failed), $failed, $results.Count)

    if ($failed -gt 0) { exit 1 }
    exit 0
}
finally {
    if (Test-Path -LiteralPath $runRoot) { Remove-Item -LiteralPath $runRoot -Recurse -Force -ErrorAction SilentlyContinue }
}
"""

# --------------------------------------------------------------------------- #
# tests/aggregate_results.ps1
# --------------------------------------------------------------------------- #
AGGREGATE = """# Generated for wfflab__wfmt-215 by the task authoring pipeline.
#
# Maps the raw check results onto the authoritative rubric and writes the
# machine readable task result consumed by the evaluation runner.
#
# The rubric is split: programmatic items (0.5) gate the run, llm_judge items
# (0.5) are scored by the reviewer against the conditions shipped on the
# verifier side. Only programmatic items take part in the binary gate, so the
# candidate score stays 0/1 and never turns into a partial credit.
#
# NOTE: keep this file pure ASCII: Windows PowerShell 5.1 reads BOM-less files as
# ANSI, and multi-byte comments can swallow the following newline.

[CmdletBinding()]
param(
    [string]$ChecksPath = '',
    [string]$RubricPath = '',
    [string]$OutputPath = '',
    [string]$TaskRoot = ''
)

$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($TaskRoot)) {
    $TaskRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
}
$TaskRoot = (Resolve-Path -LiteralPath $TaskRoot).Path
if ([string]::IsNullOrWhiteSpace($ChecksPath)) { $ChecksPath = Join-Path (Join-Path $TaskRoot 'results') ('checks' + '.json') }
if ([string]::IsNullOrWhiteSpace($RubricPath)) { $RubricPath = Join-Path (Join-Path $TaskRoot 'tests') ('rubric' + '.json') }
if ([string]::IsNullOrWhiteSpace($OutputPath)) { $OutputPath = Join-Path (Join-Path $TaskRoot 'results') ('result' + '.json') }

if (-not (Test-Path -LiteralPath $ChecksPath)) { throw "Checks file not found: $ChecksPath" }
if (-not (Test-Path -LiteralPath $RubricPath)) { throw "Rubric file not found: $RubricPath" }

$checks = Get-Content -LiteralPath $ChecksPath -Raw -Encoding UTF8 | ConvertFrom-Json
$rubric = Get-Content -LiteralPath $RubricPath -Raw -Encoding UTF8 | ConvertFrom-Json

$statusById = @{}
foreach ($check in @($checks.checks)) { $statusById[[string]$check.test_id] = [string]$check.status }

$programmaticItems = @(@($rubric.items) | Where-Object { [string]$_.type -eq 'programmatic' })
$llmItems = @(@($rubric.items) | Where-Object { [string]$_.type -ne 'programmatic' })
$programmaticBudget = 0.0
foreach ($item in $programmaticItems) { $programmaticBudget += [double]$item.weight }
$llmBudget = 0.0
foreach ($item in $llmItems) { $llmBudget += [double]$item.weight }
$programmaticBudget = [Math]::Round($programmaticBudget, 6)
$llmBudget = [Math]::Round($llmBudget, 6)

$itemResults = New-Object System.Collections.ArrayList
$weightedScore = 0.0
$allPassed = $true

foreach ($item in $programmaticItems) {
    $missing = New-Object System.Collections.ArrayList
    $failed = New-Object System.Collections.ArrayList
    foreach ($id in @($item.test_ids)) {
        # rubric test_ids carry the f2p or p2p protocol prefix required by the
        # reviewer contract, while the raw check ids are bare; strip it first.
        $bareId = ([string]$id) -replace '^(f2p|p2p)-', ''
        if (-not $statusById.ContainsKey($bareId)) { [void]$missing.Add($bareId) }
        elseif ($statusById[$bareId] -ne 'PASS') { [void]$failed.Add($bareId) }
    }
    $passed = ($missing.Count -eq 0 -and $failed.Count -eq 0)
    if ($passed) { $weightedScore += [double]$item.weight } else { $allPassed = $false }
    [void]$itemResults.Add([pscustomobject][ordered]@{
            rubric_id = [string]$item.rubric_id
            type      = 'programmatic'
            weight    = [double]$item.weight
            passed    = $passed
            failed    = @($failed.ToArray())
            missing   = @($missing.ToArray())
        })
}

$weightedScore = [Math]::Round($weightedScore, 6)
$score = if ($allPassed) { 1 } else { 0 }
$total = @($checks.checks).Count
$failedTotal = @($checks.checks | Where-Object { [string]$_.status -ne 'PASS' }).Count

if ($score -eq 1) { $reason = 'All programmatic rubric items satisfied.' }
else {
    $names = @($itemResults | Where-Object { -not $_.passed } | ForEach-Object { $_.rubric_id })
    $reason = "Unsatisfied rubric items: $($names -join ', ')"
}

# ---- Reviewer aggregate-v1 contract (bundled QC checker) --------------------
# cases cover every testcase declared by the programmatic rubric; a terminal
# status other than PASS or FAIL counts as invalid, and any invalid>0 makes
# run_validity=INVALID (incomplete evidence / infrastructure failure is never a
# legitimate 0).
$cases = New-Object System.Collections.ArrayList
$invalidTotal = 0
foreach ($item in $programmaticItems) {
    foreach ($id in @($item.test_ids)) {
        $bareId = ([string]$id) -replace '^(f2p|p2p)-', ''
        $st = ''
        if ($statusById.ContainsKey($bareId)) { $st = [string]$statusById[$bareId] }
        if ($st -ne 'PASS' -and $st -ne 'FAIL') { $invalidTotal++ }
        [void]$cases.Add([pscustomobject][ordered]@{
                test_id = [string]$id
                passed  = ($st -eq 'PASS')
            })
    }
}
$casesArray = @($cases.ToArray())
$casesTotal = $casesArray.Count
$casesPassed = @($casesArray | Where-Object { $_.passed }).Count
$casesFailed = $casesTotal - $casesPassed
$runValidity = if ($casesTotal -gt 0 -and $invalidTotal -eq 0) { 'VALID' } else { 'INVALID' }
$formalScore = if ($casesTotal -gt 0 -and $casesPassed -eq $casesTotal) { 1 } else { 0 }

$result = [pscustomobject][ordered]@{
    schema_version = 'aggregate-v1'
    run_validity   = $runValidity
    task_id        = [string]$checks.task_id
    task_version   = [string]$checks.task_version
    total          = $casesTotal
    passed         = $casesPassed
    failed         = $casesFailed
    invalid        = $invalidTotal
    formal_score   = $formalScore
    cases          = $casesArray
    required       = @($casesArray | ForEach-Object { $_.test_id })
    mode           = $null
    verdict        = $score
    reason         = $reason
    rubric_split   = [pscustomobject][ordered]@{
        programmatic_weight = $programmaticBudget
        llm_judge_weight    = $llmBudget
        programmatic_items  = @($programmaticItems).Count
        llm_judge_items     = @($llmItems).Count
    }
    test           = [pscustomobject][ordered]@{
        report = [pscustomobject][ordered]@{
            status       = 'VALID'
            score        = $score
            task_id      = [string]$checks.task_id
            task_version = [string]$checks.task_version
        }
        weighted_score = $weightedScore
        summary        = [pscustomobject][ordered]@{
            checks_total  = $total
            checks_failed = $failedTotal
            items_total   = @($programmaticItems).Count
            items_failed  = @($itemResults | Where-Object { -not $_.passed }).Count
        }
        rubric_items = @($itemResults.ToArray())
        checks       = @($checks.checks)
    }
}

$outputDirectory = Split-Path -Parent $OutputPath
if (-not (Test-Path -LiteralPath $outputDirectory)) { New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null }
$result | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $OutputPath -Encoding UTF8

Write-Host ("aggregate: score={0} weighted={1} ({2})" -f $score, $weightedScore, $reason)
if ($score -eq 1) { exit 0 }
exit 1
"""

# --------------------------------------------------------------------------- #
# tests/rubric.json (conditions moved to the verifier side)
# --------------------------------------------------------------------------- #
def build_rubric() -> dict:
    items = []
    for rubric_id, weight, test_ids in PROGRAMMATIC:
        items.append({
            "rubric_id": rubric_id,
            "type": "programmatic",
            "weight": weight,
            "test_ids": test_ids,
            "evidence_source": "results/result.json",
        })
    for rubric_id, weight in LLM_JUDGE:
        items.append({
            "rubric_id": rubric_id,
            "type": "llm_judge",
            "weight": weight,
            "evidence_source": "outside_harbor-verifier/wfflab__wfmt-215/rubric.conditions.json",
        })
    return {
        "schema_version": "mixed-v2",
        "task_id": TASK_ID,
        "task_version": TASK_VERSION,
        "conditions_source": "outside_harbor-verifier/wfflab__wfmt-215/rubric.conditions.json",
        "items": items,
        "total_weight": 1.0,
    }


def build_judge(rubric_sha: str) -> str:
    lines = [
        "# Generated for wfflab__wfmt-215 by the task authoring pipeline.",
        "# Binds the judge configuration to the authoritative rubric and records its",
        "# digest so that silent rubric drift is detectable.",
        "#",
        "# The split honours WIP VV-14: no single scoring family may exceed 50%.",
        "# pass/fail conditions for every item live on the verifier side",
        "(outside_harbor-verifier/wfflab__wfmt-215/rubric.conditions.json).",
        'schema_version = "outside-mixed-rubric-v2"',
        'authoritative_source = "rubric.json"',
        f'source_sha256 = "{rubric_sha}"',
        "programmatic_weight = 0.5",
        "llm_judge_weight = 0.5",
        "",
    ]
    for rubric_id, weight, test_ids in PROGRAMMATIC:
        lines.append("[[rubrics]]")
        lines.append(f'rubric_id = "{rubric_id}"')
        lines.append('type = "programmatic"')
        lines.append(f"weight = {weight}")
        lines.append("test_ids = [" + ", ".join(f'"{t}"' for t in test_ids) + "]")
        lines.append("")
    for rubric_id, weight in LLM_JUDGE:
        lines.append("[[rubrics]]")
        lines.append(f'rubric_id = "{rubric_id}"')
        lines.append('type = "llm_judge"')
        lines.append(f"weight = {weight}")
        lines.append("")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# task.toml
# --------------------------------------------------------------------------- #
TASK_TOML = """# Platform schema version fixed by the upstream Outside Harbor contract.
version = "1.0"

# Base image pinned by immutable digest. The runtime underneath is Windows
# Server Core, which is the real Windows runtime this container-format behaviour
# contract and its file-handle semantics depend on.
docker_image = "{base_image}"

[metadata]
quality_restoration_version = "20261010.2"
author_name = "wfflab"
task_id = "wfflab__wfmt-215"
tags = ["coding", "windows", "python", "binary-format", "streaming", "crc", "varint"]
difficulty = "L4"

[agent]
timeout_sec = 7200.0

[verifier]
timeout_sec = 7200.0

[environment]
build_timeout_sec = 3600.0
cpus = 2
memory = "4G"
# Standard Harbor reads the OS switch and the working directory from this table.
# Harbor builds environment/Dockerfile itself, which bakes the workspace into
# C:\\testbed.
os = "windows"
workdir = "C:\\\\testbed"

# Local runner compatibility extension. These paths are relative to the task
# root and are re-validated by the task authoring pipeline.
[task]
id = "wfflab__wfmt-215"
# Standard Harbor requires "org/name" here; the local runner uses `id` above.
name = "wfflab/wfmt-215"
version = "2.1.0"
instruction = "instruction.md"
workspace = "environment/workspace"
setup = "environment/prepare.ps1"
test = "tests/test.ps1"
golden = "solution/solve.ps1"

[policy]
# The candidate may only change the package sources. The contract document and
# the authoritative samples stay read-only, and neither tests/ nor solution/
# is part of the agent-visible surface (see environment/agent_visible_paths.json):
# the hidden behavioural suite and the reference payload are injected on the
# verifier side at grading time.
mutable_paths = ["environment/workspace/wfmt"]
read_only_paths = ["instruction.md", "environment/prepare.ps1", "environment/run.ps1", "environment/restore.ps1", "environment/cleanup.ps1", "environment/validate_environment.ps1", "environment/workspace/docs", "environment/workspace/assets", "environment/workspace/tests"]
withheld_from_agent = ["tests", "solution"]
""".format(base_image=BASE_IMAGE)


def main() -> None:
    write_text("solution/README.md", SOLUTION_README)
    write_text("environment/workspace/README.md", WORKSPACE_README)
    write_text("environment/agent_visible_paths.json",
               json.dumps(AGENT_VISIBLE, ensure_ascii=False, indent=2) + "\n")
    write_ascii_script("environment/Dockerfile", DOCKERFILE)
    write_ascii_script("environment/adapter.toml", ADAPTER)
    write_ascii_script("environment/validate_environment.ps1", VALIDATE)
    write_ascii_script("tests/run_tests.ps1", RUN_TESTS)
    write_ascii_script("tests/aggregate_results.ps1", AGGREGATE)
    write_ascii_script("task.toml", TASK_TOML)

    rubric_path = TASK / "tests" / "rubric.json"
    with rubric_path.open("w", encoding="utf-8", newline="") as handle:
        handle.write(json.dumps(build_rubric(), ensure_ascii=False, indent=2) + "\n")
    rubric_sha = hashlib.sha256(rubric_path.read_bytes()).hexdigest()
    print(f"write tests/rubric.json sha256={rubric_sha}")
    write_ascii_script("tests/judge.toml", build_judge(rubric_sha))


if __name__ == "__main__":
    main()
