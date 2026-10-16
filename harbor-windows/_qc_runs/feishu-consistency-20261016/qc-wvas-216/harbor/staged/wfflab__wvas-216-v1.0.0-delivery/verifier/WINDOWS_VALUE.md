# Windows 价值与采购分类说明（wfflab__wvas-216，task version 1.0.0）

> **口径版本**：`windows-value-mapping-v1`（2026-10-14）。
> 对应手册条款：**QD-SP-12**、**QD-SP-18**；甲方《最新质检要求》第 3 条
> 「Windows 价值必须真实映射到具体系统组件」。
> 门禁产物：`metadata/windows_mechanism.json`（`windows-mechanism-gate-v1`）。

本说明把题面要求逐条映射到真正依赖的 Windows 机制，并标注证据强度：

- **A 级（OS 机制，可复算）**：判分过程里确实调用了 Windows 系统组件，调用入口、
  参数形态与返回结构都写在隐藏套件里，换平台无对应物。
- **B 级（Windows 生态语义）**：语义由 Windows 侧定义，但判分只做离线比对。
- **C 级（通用平台语义）**：换平台不变，不构成 Windows 价值。

## 1. 结论

**本题具备真实的 Windows 反事实价值，主张 Windows 采购分类。**

反事实问题「把目标 OS 换成 Linux/macOS，主要实现、错误根因和 Evaluator 是否基本不变？」
的答案是**否**：被测对象是**本机一个真实进程的虚拟地址空间**，题目要求的每一项都是
Windows 虚拟内存接口的直接语义；换成 `/proc/<pid>/maps`（Linux）或
`mach_vm_region` + `proc_regionfilename`（macOS），字段宽度、错误分类、
「已保留但未提交」的表达和路径形式全部不同，实现与验收点会整体重写。

| 项 | 取值 |
| --- | --- |
| `primary_direction` | Windows / 进程与虚拟内存（`VirtualQueryEx` 语义 + 映射文件命名 + 设备路径翻译） |
| 反事实价值 | **高** |
| 证据强度构成 | **A 级 8 条**（全部为判分期真实系统调用）；无 B/C 级计分项 |
| 是否入 Windows 专属能力计分 | **是** |

## 2. 判分期真正发生的系统调用

隐藏套件 `tests/test_wvas_semantics.py`（与 `verifier/tests/` 同源）在**判分时**自己拉起
一个目标进程，并**独立**用同一组 Windows 接口测量该进程，再与被测包的输出逐个比对：

| 判分侧动作 | 入口 | 用途 |
| --- | --- | --- |
| 遍历目标进程地址空间 | `kernel32!VirtualQueryEx` + `MEMORY_BASIC_INFORMATION` | 独立取得 `BaseAddress` / `RegionSize` / `State` / `Type` / `Protect` 作为基准 |
| 命名文件背衬区间 | `psapi!GetMappedFileNameW` | 独立取得映射文件的名称 |
| 把设备路径翻成盘符/UNC | `kernel32!QueryDosDeviceW` + 最长前缀替换 | 独立把 `\Device\...` 翻成调用方可打开的形式 |
| 校验路径真的可打开 | `kernel32!CreateFileW` | 断言被测包给出的 `path` 能被打开 |
| 映像清单 | `psapi!EnumProcessModulesEx` + `GetModuleFileNameExW` | 独立取得已加载映像与各自文件路径，校验去重与升序 |

被测包自身只能通过同样的 Windows 接口回答；也就是说**判据与被测对象落在同一套 OS
语义上**，而不是对已知答案做字符串比对。

## 3. 逐条映射：题面要求 → 依赖的机制

| # | 题面要求（`instruction.md`） | 依赖的机制 | 级别 | 隐藏用例 |
| --- | --- | --- | --- | --- |
| 1 | `base` 必须是完整地址宽度下的真值 | 64 位 ABI 下 `MEMORY_BASIC_INFORMATION.BaseAddress` 为指针宽度；32 位读取会截断高地址 | **A** | `f2p-region-addresses-are-64-bit` |
| 2 | `size` 不得截断，超过 4 GiB 报真实长度 | `RegionSize` 为 `SIZE_T`；6 GiB 保留区的真实长度只能按 64 位读 | **A** | `f2p-region-sizes-are-64-bit` |
| 3 | `include_reserved=True` 时保留区必须出现 | `VirtualQueryEx` 的 `State` 区分 `MEM_COMMIT` / `MEM_RESERVE` | **A** | `f2p-reserved-regions-are-reported` |
| 4 | 文件映射区间的 `path` 等于真实磁盘路径 | `GetMappedFileNameW` 返回的是 NT 设备路径，需要翻译 | **A** | `f2p-file-mapping-path-is-a-dos-path` |
| 5 | `path` 必须是可直接打开的盘符/UNC 形式 | 设备名到驱动器号的映射由 `QueryDosDeviceW` 给出；`\Device\Mup\` 对应 UNC | **A** | `f2p-device-paths-are-translated` |
| 6 | 无文件背衬时 `path is None`，不得是空串 | `GetMappedFileNameW` 对无文件背衬区间返回 0（不是「空名字」）；契约把它定义为「没有文件」 | **A** | `f2p-anonymous-mapping-has-no-path` |
| 7 | 失败路径全部走 `WVasError(kind=...)` | `OpenProcess` 的 `ERROR_INVALID_PARAMETER`(87) 与 `ERROR_ACCESS_DENIED`(5) 语义 | **A** | `f2p-missing-process-is-classified` |
| 8 | `modules(pid)` 完整、去重、按 `base` 升序、`path` 可打开 | 已加载映像清单由 `EnumProcessModulesEx` + `GetModuleFileNameExW` 给出，与区间枚举是两条独立通路 | **A** | `f2p-modules-are-deduplicated` |

被测包中与平台无关的部分（字典结构、排序、去重、纯常量映射 `protection_name()` /
`type_name()`）**不单独计分**：它们只作为可见冒烟套件 `tests/test_wvas_basic.py` 的回归项
（P2P），不构成 Windows 价值主张。

## 4. 非 Windows 必然失败

| 锚点 | 落点 | 行为 |
| --- | --- | --- |
| 环境就绪探针 | `environment/validate_environment.ps1` | 主机不是 `Win32NT` 时直接 `Fail 'the host platform is not Windows (Win32NT), so the wvas contract cannot be graded here'`；同时在 Windows 上真实调用 `VirtualQueryEx` / `GetMappedFileNameW` / `QueryDosDeviceW` 确认可应答 |
| 隐藏套件 | `tests/test_wvas_semantics.py` | 模块级 `os.name != "nt"` 跳过；非 Windows 控制轮因此记为 `INVALID`，而不是「通过」 |
| 题目方向声明 | `instruction.md` | 排他声明：*"本任务的目标平台是真实的 Windows，验收不使用其他操作系统，也不需要实现其他操作系统的版本。"* |

## 5. 自检

```powershell
python harbor-windows\skills\harbor-windows\scripts\check_windows_mechanism.py --task-dir "<包目录>"
```

预期 `PASS`：F1 身份一致、F2 反事实答案「否」、F3 排他声明逐字锚定、F4 八条机制各带
`instruction_quote` + `test_ref` + F2P 用例、F5 非 Windows 硬失败证据落在
`environment/validate_environment.ps1`、F6 无自我否认表述。
