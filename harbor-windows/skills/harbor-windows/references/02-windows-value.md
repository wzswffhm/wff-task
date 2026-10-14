# 02 · Windows 价值反事实判定

来源：规范第三章「Windows 专项准入」

---

## 核心判定方法

**逐题回答以下问题**：

> 如果将目标操作系统替换为 Linux 或 macOS，主要实现、错误根因和 Evaluator 是否基本不变？
>
> 若答案为「是」，**原则上不属于 Windows 专项题**。

**判定三要素**（任一被替换后显著改变即可成立）：

1. **主要实现** —— 代码主体是否依赖 Windows API/运行时/工具链
2. **错误根因** —— 缺陷是否只在 Windows 平台语义下成立
3. **Evaluator** —— 验收机制是否必须在真实 Windows Runtime 触发

---

## 判定必须留痕：门禁产物 + 禁止自认句

> **2026-10-14 起为硬门禁**。本节判定的结论不能只停留在"人认为通过"，
> 必须落成可复算的产物并接受脚本校验 —— 见 `references/12-windows-mechanism-gate.md`。

**产物**：`delivery-extras/tasks/<task-id>/metadata/windows_mechanism.json`
（模板：`assets/metadata-templates/windows_mechanism.json`），逐条给出：

- `counterfactual.answer = "否"` + `reason`；
- `exclusive_declaration.quote` —— **排他声明**，与 `instruction.md` 逐字一致；
- `mechanisms[]` —— ≥3 条，每条 `instruction_quote`（题面逐字）+ `test_ref`（`文件#L起-L止`）
  + `f2p_case`（必须是 `required_testcases.json` 中 group=F2P 的用例）；
- `non_windows_must_fail` —— 环境层"非 Windows / 非 NTFS 必然失败"的文件与逐字证据。

**校验**：`python scripts/check_windows_mechanism.py --task-dir <题包目录>`，退出码 `0` 才算过。

### 排他声明 ≠ 免责声明（本批次最大坑）

| | 例句 | 性质 | 判定 |
|---|---|---|---|
| ✅ 排他声明 | `目标是真实的 Windows NTFS 语义，不需要实现其他操作系统版本。` | 把其他 OS 排除出验收范围 | 加强项，F3 要求登记 |
| ❌ 免责声明 | `本题不主张 Windows 反事实价值，按通用编码能力归类。` | 自我否认被测能力 | **F6 命中即 FAIL，永不豁免** |

`wfflab__wchunk-216 / wfmt-215 / wlogseg-218` 被判「Windows 专属价值低」时，
甲方**直接引用了包内 `verifier/WINDOWS_VALUE.md` 的自认句作为证据**。
因此：包内出现自认句时，正确处置是**给题注入真实 Windows 机制发新版**（或按甲方口径移出 Windows 池），
**不是删掉那段话** —— 删掉只让门禁变绿，判定依据仍在题面与测试里。

### 判定前先看的三件事（避免走回头路）

1. **题面是否把机制名写进了"可验收行为"**，而不是只写在背景或"可以使用 Windows API"这类许可式表述里。
   只写许可 = 跨平台写法也能过 = 本批次翻车的形态。
2. **验证层是否由评测器自己持有内核对象**（真句柄 / 真命名对象 / 真注册表通知 / 真 Job Object），
   而不是比对候选输出的字符串。可直接照搬的手法清单见 `references/12-windows-mechanism-gate.md` §5。
3. **环境层是否有"非 Windows 必然失败"的探针且记为 INVALID**，而不是靠 `$IsWindows` 一句版本号检查。

---

## 不能单独证明 Windows 价值的 6 种情况

| # | 误判做法 | 为什么不算 |
|---|---|---|
| 1 | 题面出现 PowerShell、批处理、盘符、反斜杠、C# 或 Windows 路径 | 表层符号 ≠ 平台语义 |
| 2 | 将通用算法、普通业务逻辑或跨平台任务放到 Windows 机器运行 | 环境换了，能力没换 |
| 3 | 只增加 Windows 启动脚本，核心实现仍与平台无关 | 壳子是 Windows，内核不是 |
| 4 | 只验证编译成功、文件存在、进程存在、日志关键词或代码字符串 | 不验证真实行为 |
| 5 | 使用 WSL 内纯 Linux 结果、Linux Mock、模型自写测试或模型自报代替正式 Windows 判分 | 未在目标平台判分 |
| 6 | 仅为兼容目录形式而用 Linux 容器替代 Windows VM/Server/桌面/企业环境 | 验证环境失真 |

> **S1–S2 级的表面 Windows 题不得进入正式集。**

---

## 可接受的价值来源：12 个主流方向

题目可以来自**真实开源 Issue/PR、授权工程问题或高价值定向构造场景**。优先覆盖以下方向：

| # | 方向 | 代表性能力 |
|---|---|---|
| 1 | **.NET 与桌面应用** | .NET/.NET Framework、WinForms、WPF、WinUI、Windows App SDK、桌面生命周期与部署 |
| 2 | **原生开发与互操作** | Win32、C/C++、P/Invoke、COM、ABI、MSVC、Windows SDK |
| 3 | **Shell 与自动化** | Windows PowerShell 5.1、PowerShell 7、CMD/Batch、非交互执行、错误流与退出码 |
| 4 | **文件系统与路径** | NTFS、ADS、ACL、文件锁、长路径、盘符、UNC、符号链接/Reparse Point、大小写与路径规范化 |
| 5 | **系统管理** | 注册表、Windows Service、计划任务、环境变量、证书、安装与卸载状态 |
| 6 | **进程与执行上下文** | 进程树、Job Object、Session、桌面与焦点、权限边界、生命周期和资源释放 |
| 7 | **安全与身份** | UAC、Token、ACL、凭据、最小权限、审计、加密与安全存储 |
| 8 | **网络与 IPC** | Named Pipe、Windows Socket、SMB、端口与防火墙、进程间通信 |
| 9 | **构建、安装与打包** | MSBuild、NuGet、MSI/MSIX、Inno/NSIS、签名、升级/回滚/卸载闭环 |
| 10 | **编码与区域** | UTF-8/BOM、代码页、Locale、中文用户名/路径、时区与区域格式 |
| 11 | **诊断与可观测性** | Event Log、Dump、WinDbg、ETW、性能与故障诊断 |
| 12 | **设备与系统底层** | 设备 API、驱动、内核交互及需要真实专用环境的工程问题 |

---

## 覆盖度申报规则

- 知识树用于**引导覆盖**，**不要求**供应商机械复刻旧版分类或配额
- 每题申报**一个主方向**和必要的**次级标签**
- 采购方按批次检查：
  - 是否覆盖主流方向
  - 是否**过度集中在单一语言/题型/冷门 API**
  - Evaluator 是否真实覆盖所申报能力

**产出位置**：`delivery-extras/tasks/<task-id>/metadata/labels.json`

```json
{
  "task_id": "Azure__azure-sdk-for-python-41822",
  "primary_direction": "安全与身份",
  "secondary_tags": ["凭据", "SSO", "WAM", "COM互操作"],
  "language": "Python",
  "task_type": "bug-fix",
  "target_windows": {
    "version": "Windows 11",
    "edition": "Pro",
    "arch": "x64",
    "locale": "en-US",
    "shell": "PowerShell 5.1"
  },
  "difficulty": "L4",
  "counterfactual": {
    "question": "换 Linux/macOS 后主要实现、错误根因、Evaluator 是否基本不变？",
    "answer": "否",
    "reason": "核心依赖 Windows WAM broker 与 VS Code 凭据存储的 COM 交互，Linux 无对应机制"
  }
}
```

---

## 预筛检查清单

- [ ] 反事实问题答案明确为「否」，且写明**理由**
- [ ] 主方向落在 12 个方向内，次级标签准确
- [ ] 不属于 6 种误判情况
- [ ] 非 S1–S2 表面题
- [ ] Evaluator 真的能覆盖所申报能力
- [ ] 难度来源为工程语义，非歧义/冷僻知识
- [ ] 题面含**排他声明**（并已登记 `exclusive_declaration.quote`）
- [ ] 至少 3 条机制写进**可验收行为**，每条绑定一条 **F2P** 用例
- [ ] 环境层有"非 Windows 必然失败"的探针，且该情形记为 **INVALID**
- [ ] 包内**无**自我否认 Windows 价值的表述（`platform-agnostic` / 「通用编码能力」等）
- [ ] `check_windows_mechanism.py` 退出码 `0`
