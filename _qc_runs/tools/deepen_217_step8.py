"""217 加深（第八步）：复刻 215 的 L4 结构。

215（L4）的三重结构：
  assets/sample.wfmt          唯一权威样本（真实数据，必须逆向）
  docs/FORMAT.md              早期草稿，与真实布局脱节，顶部有醒目警告
  tests/test_wfmt_basic.py    可见冒烟测试，只测「自己写的能不能自己读回来」
  instruction.md              声明「样本才是唯一权威依据」

217 原先只有「唯一权威行为规格」的契约，照抄即可。本步改为：
  assets/observed-provider-facts.json  真机实测的 provider 行为事实（权威）
  docs/REPARSE-CONTRACT.md             语义权威，但补一节声明它不覆盖 provider 细节
  tests/test_wreparse_basic.ps1        可见冒烟测试（候选实现当前可全过）
  instruction.md                       同步声明两个来源的分工

说明：assets/ 无法放含硬链接/符号链接的目录树 —— 任务树经 bind mount 进入容器时，
bind filter 会拒绝硬链接与符号链接（217 的 tests/prepare.ps1 已记录该限制），
且 junction 的绝对目标在容器内会失效。因此权威样本以「实测事实」形式给出。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

TASK = Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-windows\wfflab__wreparse-217")
WS = TASK / "environment/workspace"
failed = False


def patch(path: Path, old: str, new: str, label: str) -> None:
    global failed
    text = path.read_text(encoding="utf-8")
    n = text.count(old)
    if n != 1:
        print(f"!! {path.name}: {label} 命中 {n} 次（期望 1）")
        failed = True
        return
    path.write_text(text.replace(old, new), encoding="utf-8")
    print(f"ok {path.name}: {label}")


# ============================================================ A. 权威实测事实
facts = {
    "collected_on": "Windows 11 (10.0.26100) / NTFS / Windows PowerShell 5.1",
    "purpose": (
        "在真机上对一棵含 junction、符号链接与硬链接的目录树实测采集 provider 行为。"
        "docs/REPARSE-CONTRACT.md 描述语义；本文件记录 provider 层返回值的真实形状。"
        "两者在实现细节上冲突时，以本文件为准。"
    ),
    "observations": [
        {
            "id": "reparse-attribute-is-the-only-reliable-marker",
            "statement": (
                "硬链接的 LinkType 是 'HardLink'，但其 Attributes 不含 ReparsePoint。"
                "只有 Attributes 位包含 FILE_ATTRIBUTE_REPARSE_POINT 的条目才是重解析点；"
                "仅凭 LinkType 非空来判定会把硬链接误判为重解析点。"
            ),
            "measured": {
                "hardlink.txt": {"LinkType": "HardLink", "Attributes": ["Archive"]},
                "junction": {"LinkType": "Junction", "Attributes": ["Directory", "ReparsePoint"]},
                "symlink-directory": {"LinkType": "SymbolicLink", "Attributes": ["Directory", "ReparsePoint"]},
                "symlink-file": {"LinkType": "SymbolicLink", "Attributes": ["Archive", "ReparsePoint"]}
            }
        },
        {
            "id": "link-type-vocabulary",
            "statement": (
                "provider 给出的 LinkType 取值是 'Junction'、'SymbolicLink'、'MountPoint'、'HardLink'。"
                "junction 与符号链接的 LinkType 不同，可直接区分；"
                "卷挂载点与 junction 同属目录重解析点，但 LinkType 不同。"
            )
        },
        {
            "id": "provider-target-is-a-collection",
            "statement": (
                "Get-ChildItem 返回的 .Target 是 System.String[]（可能有多个替换项），"
                "而不是单个字符串。相对目标按原样给出（例如 'docs'），"
                "绝对目标给出完整路径（例如 'C:\\\\tree\\\\docs'）。"
            )
        },
        {
            "id": "powershell-unrolls-single-element-arrays",
            "statement": (
                "PowerShell 函数 return 一个单元素数组时，调用方拿到的是元素本身而不是数组。"
                "因此把 provider 的 .Target 直接转发出去，得到的类型是不稳定的"
                "（单目标时是 String，多目标时是 Object[]）。"
                "契约把 Target 定义为一个目标串，所以必须显式取首元素并转成字符串。"
            )
        },
        {
            "id": "enumeration-order-is-not-contract-order",
            "statement": (
                "Get-ChildItem -Force 按目录索引返回条目，其顺序接近 Unicode 序，"
                "但契约要求的是序数、忽略大小写的键，且明确禁止使用受宿主区域设置影响的排序。"
                "在含非 ASCII 名字的目录上，区域设置敏感的默认排序（PowerShell 的 Sort-Object）"
                "会按基字母重排：例如把 'Ä' 与 'ö' 排在 ASCII 的 'Z' 之前，"
                "而序数比较把 'Z'(U+005A) 排在 'Ä'(U+00C4) 与 'ö'(U+00F6) 之前。"
                "两类顺序在真机上都可复现，必须按契约的序数规则实现。"
            )
        },
        {
            "id": "hard-links-and-symbolic-links-are-not-bind-mountable",
            "statement": (
                "把一棵目录树经 bind mount 投进 Windows 容器时，bind filter 会拒绝硬链接与"
                "符号链接（报 'Access is denied'），目录、普通文件与 junction 仍可创建。"
                "因此夹具建在容器的可写层上，而不是任务树里。"
            )
        }
    ]
}

assets = WS / "assets"
assets.mkdir(parents=True, exist_ok=True)
(assets / "observed-provider-facts.json").write_text(
    json.dumps(facts, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(f"ok 新增 assets/observed-provider-facts.json（{len(facts['observations'])} 条实测事实）")

# ==================================================== B. 可见冒烟测试（陷阱）
smoke = r'''# WReparse - 可见冒烟测试
#
# 只覆盖最基础的一条：自己产出的报告能被自己读懂。
# 它**不**校验行为契约的任何一条细则；通过它不代表实现符合
# docs/REPARSE-CONTRACT.md。评测方另行运行一组契约一致性检查。
#
# 退出码：0 通过；1 失败。

[CmdletBinding()]
param(
    [string]$WorkspaceRoot = ''
)

$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($WorkspaceRoot)) {
    $WorkspaceRoot = Split-Path -Parent $PSScriptRoot
}

$modulePath = Join-Path (Join-Path $WorkspaceRoot 'WReparse') ('WReparse' + '.psd1')
if (-not (Test-Path -LiteralPath $modulePath)) {
    Write-Host "smoke: 找不到模块 $modulePath"
    exit 1
}

Import-Module $modulePath -Force

$failed = 0

# 1) 模块可导入，且能报告 schema 版本
try {
    $version = Get-WReparseSchemaVersion
    if ([string]::IsNullOrWhiteSpace([string]$version)) { throw 'schema 版本为空' }
    Write-Host "[PASS] 模块可导入；SchemaVersion = $version"
}
catch {
    Write-Host "[FAIL] 模块导入或 Get-WReparseSchemaVersion 失败：$($_.Exception.Message)"
    $failed++
}

# 2) 对一个临时目录扫描，报告里应当有 Records / Errors / Stats
$probe = Join-Path $env:TEMP ('wreparse-smoke-' + [guid]::NewGuid().ToString('N').Substring(0, 8))
New-Item -ItemType Directory -Path (Join-Path $probe 'sub') -Force | Out-Null
Set-Content -LiteralPath (Join-Path $probe 'a.txt') -Value 'a' -NoNewline -Encoding ASCII
try {
    $report = Get-WReparseReport -Root $probe
    foreach ($field in @('Records', 'Errors', 'Stats')) {
        if ($null -eq $report.PSObject.Properties[$field]) { throw "报告缺少 $field" }
    }
    Write-Host '[PASS] 报告包含 Records / Errors / Stats'
}
catch {
    Write-Host "[FAIL] Get-WReparseReport 失败：$($_.Exception.Message)"
    $failed++
}

# 3) 报告能序列化成 JSON
try {
    $json = ConvertTo-WReparseJson -Report $report
    if ([string]::IsNullOrWhiteSpace([string]$json)) { throw '序列化结果为空' }
    Write-Host '[PASS] 报告可序列化为 JSON'
}
catch {
    Write-Host "[FAIL] ConvertTo-WReparseJson 失败：$($_.Exception.Message)"
    $failed++
}

# 4) 路径工具可用
try {
    $canonical = Get-WReparseCanonicalPath -Path $probe
    if ([string]::IsNullOrWhiteSpace([string]$canonical)) { throw '规范化结果为空' }
    Write-Host '[PASS] Get-WReparseCanonicalPath 可用'
}
catch {
    Write-Host "[FAIL] Get-WReparseCanonicalPath 失败：$($_.Exception.Message)"
    $failed++
}

Remove-Item -LiteralPath $probe -Recurse -Force -ErrorAction SilentlyContinue

if ($failed -gt 0) {
    Write-Host "smoke: $failed 项失败"
    exit 1
}
Write-Host 'smoke: 全部通过（注意：这并不代表符合 docs/REPARSE-CONTRACT.md）'
exit 0
'''
smoke_dir = WS / "tests"
smoke_dir.mkdir(parents=True, exist_ok=True)
(smoke_dir / "test_wreparse_basic.ps1").write_text(smoke, encoding="utf-8")
print("ok 新增 tests/test_wreparse_basic.ps1（可见冒烟测试）")

# ============================================ C. 契约补一节：provider 细节分流
CONTRACT = WS / "docs/REPARSE-CONTRACT.md"
tail_anchor = "\n## 9."
text = CONTRACT.read_text(encoding="utf-8")
if "## 10." in text:
    print("!! 契约已含 §10")
    failed = True
else:
    section = """
## 10. provider 细节与实测事实

本文件规定**语义**：字段含义、遍历规则、路径判定、错误码与序列化要求。

它**不**规定 provider 层返回值的真实形状——那是宿主实现决定的，并且会随
Windows 版本与访问方式变化。真机实测的权威事实记录在
`assets/observed-provider-facts.json`，包括：

- 重解析点与硬链接在文件属性上的区别；
- provider 给出的 `LinkType` 取值集合；
- `.Target` 的实际类型与相对/绝对形态；
- PowerShell 转发单元素数组时的类型行为；
- 枚举顺序与契约排序规则的关系。

**当本文件的文字与 `assets/observed-provider-facts.json` 的实测事实在实现细节上
冲突时，以实测事实为准。** 语义层面的规则仍以本文件为准。
"""
    idx = text.find(tail_anchor)
    if idx < 0:
        print("!! 契约里找不到 §9 锚点")
        failed = True
    else:
        CONTRACT.write_text(text[:idx] + section + text[idx:], encoding="utf-8")
        print("ok REPARSE-CONTRACT.md: 新增 §10 provider 细节与实测事实")

# ================================================================ D. instruction
INSTR = TASK / "instruction.md"

patch(INSTR,
      """`environment/workspace/WReparse` 是当前实现，`environment/workspace/docs/REPARSE-CONTRACT.md`
是它的**唯一权威行为规格**。当前实现与契约之间存在多处偏差，需要全部修掉。""",
      """`environment/workspace/WReparse` 是当前实现。行为依据有两个来源，分工明确：

- `environment/workspace/docs/REPARSE-CONTRACT.md` 规定**语义**（字段含义、遍历规则、
  路径判定、错误码、序列化要求），语义层面以它为准；
- `environment/workspace/assets/observed-provider-facts.json` 是在真机
  （Windows 11 + NTFS + Windows PowerShell 5.1）上实测采集的 **provider 层权威事实**
  （属性与 `LinkType` 的真实取值、`.Target` 的实际类型、枚举顺序与排序规则的关系等）。
  **两者在实现细节上冲突时，以实测事实为准。**

当前实现与以上两个来源之间存在多处偏差，需要全部修掉。""",
      "背景：声明两个权威来源及其分工")

patch(INSTR,
      """8. **错误码**：只使用契约 §7 的七个码，触发条件与契约一致（含 `invalid_argument`）；
   未给 `-Follow` 时不得产生 `cycle` 与 `broken_target`。""",
      """8. **错误码**：只使用契约 §7 的七个码，触发条件与契约一致（含 `invalid_argument`）；
   未给 `-Follow` 时不得产生 `cycle` 与 `broken_target`。
9. **导出面**：模块**只**导出契约 §2 的六个函数。内部辅助函数（遍历、排序、
   记录构造等）不得出现在模块的可见命令面上。
10. **报告字段集合**：报告对象的字段**恰好**是契约 §3 的 `SchemaVersion` / `Root` /
    `Records` / `Errors` / `Stats` 五项，不得多出任何字段（包括生成时间戳之类的元数据）。
11. **排序与宿主区域设置无关**：`Records` 与 `Errors` 的比较键必须是**序数**比较。
    不得把排序委托给受宿主 culture 影响的默认排序——在含非 ASCII 名字的目录上，
    这种排序会按基字母重排，使同一棵树在不同宿主机上产出不同报告。
12. **记录字段的类型稳定**：`Target` 是一个目标串。provider 可能把目标返回成集合，
    且 PowerShell 转发单元素数组时会退化成元素本身；实现必须显式把它规范成字符串，
    不得让 `Target` 的类型随目标个数变化。""",
      "必须满足的行为：新增第 9~12 条")

patch(INSTR,
      """11. 扫描一棵**空目录**树时，序列化结果中 `Records` 与 `Errors` 均为 `[]`。""",
      """11. 扫描一棵**空目录**树时，序列化结果中 `Records` 与 `Errors` 均为 `[]`。
12. 导入模块后，可见函数恰好是 `Get-WReparseReport`、`ConvertTo-WReparseJson`、
    `Get-WReparseSchemaVersion`、`Test-WReparseWithinRoot`、`Get-WReparseCanonicalPath`、
    `Resolve-WReparseLinkTarget` 六个；内部辅助函数（如遍历与排序函数）不可见。
13. 报告对象不含 `SchemaVersion` / `Root` / `Records` / `Errors` / `Stats` 之外的字段。
14. 在名字含非 ASCII 字符（如 `Ä`、`ö`）的目录上，`Records` 仍严格按**序数**规则排序：
    例如 ASCII 的 `Z` 必须排在 `Ä` 与 `ö` 之前——按基字母排序的实现会给出相反结果。
15. 未给 `-Follow` 时，报告的 `Errors` 中不出现 `cycle` 与 `broken_target`，
    即使扫描树里存在环和悬空目标。
16. 普通文件与目录（如 `plain.txt`、`docs`、硬链接）的 `InScope` 恒为 `false`；
    `InScope` 只对重解析点条目有意义。
17. 任何重解析点条目的 `Target` 都是字符串类型，不因目标个数而变化。""",
      "用户可见验收：新增第 12~17 条")

patch(INSTR,
      """- 不引入外部依赖：保持纯 PowerShell + .NET BCL。
- 模块必须在 Windows PowerShell 5.1 下可正常导入并运行（不得要求 PowerShell 7）。""",
      """- 不引入外部依赖：保持纯 PowerShell + .NET BCL。
- 模块必须在 Windows PowerShell 5.1 下可正常导入并运行（不得要求 PowerShell 7）。
- `environment/workspace/assets/observed-provider-facts.json` 是只读的权威事实，
  不得修改；`environment/workspace/tests/test_wreparse_basic.ps1` 是可见冒烟测试，
  也不得修改。""",
      "边界：声明 assets 与可见冒烟测试为只读")

patch(INSTR,
      """所述夹具与检查脚本属于**评测资产，不提供给候选**。""",
      """`environment/workspace/tests/test_wreparse_basic.ps1` 是**可见冒烟测试**：它只确认
模块能导入、报告结构存在、能序列化。它**不**校验上面任何一条细则，
通过它**不代表**实现了契约——当前这份有偏差的实现同样能通过它。

所述评测夹具与检查脚本属于**评测资产，不提供给候选**。""",
      "运行入口：说明可见冒烟测试不覆盖契约")

# ============================================================= E. task.toml 策略
patch(TASK / "task.toml",
      'read_only_paths = ["instruction.md", "environment/prepare.ps1", "environment/run.ps1", "environment/restore.ps1", "environment/cleanup.ps1", "environment/validate_environment.ps1", "environment/workspace/docs", "tests"]',
      'read_only_paths = ["instruction.md", "environment/prepare.ps1", "environment/run.ps1", "environment/restore.ps1", "environment/cleanup.ps1", "environment/validate_environment.ps1", "environment/workspace/docs", "environment/workspace/assets", "environment/workspace/tests", "tests"]',
      "task.toml: assets 与可见冒烟测试加入只读路径")

print("\nRESULT:", "部分失败" if failed else "第八步完成")
sys.exit(1 if failed else 0)
