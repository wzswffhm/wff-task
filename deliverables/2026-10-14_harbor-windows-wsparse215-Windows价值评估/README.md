# `wfflab__wsparse-215` Windows 价值评估（2026-10-14）

评估对象：`harbor-windows/wfflab__wsparse-215-v1.0.0-delivery`（包内版本 1.0.0）
评估问题：**该题包是否具备 Windows 价值**（甲方采购质检十项人工硬门禁第 5 项）

## 结论

**具备，且是本批 wff 题包里 Windows 价值最扎实的一个 —— 该项判 `PASS`。**

题目的实现层、观测层、环境门禁三层都压在真实 Win32 文件系统控制码与 NTFS 语义上，参考解在非 Windows 上不是降级而是直接拒绝执行。**但需要精确区分依赖强度**（详见第六节）：五条机制判据中，“稀疏属性位”与“稀疏标志不可回溯语义”两条是 Windows 独有、POSIX 侧不存在对应行为；另外三条（稀疏预分配、物理占用、已分配区间）在 Linux 上有等价实现（`ftruncate` / `st_blocks` / `SEEK_DATA`），换平台会换实现、但不会丢行为。按甲方门禁口径（核心行为是否消失或发生实质变化）判定仍为 `PASS`，价值锚点主要落在前两条。这与 215/216/218（`wfmt` / `wchunk` / `wlogseg`）那三个“题面与源码里一处 Windows 语义都没有”的包形成鲜明对照。

> 注意：本评估只回答“Windows 价值”这一项。该包目前**还不具备交付条件**，结构层另有 7 条硬错误（见第四节），与 Windows 价值无关。

---

## 一、逐条机制映射（题面要求 → Windows 机制 → 测试位置）

| # | 题面要求 | 唯一可行的 Windows 机制 | 隐藏套件判据 |
|---|---|---|---|
| 1 | `preallocate` 必须把文件标记为稀疏 | `DeviceIoControl(FSCTL_SET_SPARSE)` + `FILE_ATTRIBUTE_SPARSE_FILE` | `tests/test_wsparse_semantics.py:276-282`（`sparse_state` + `os.stat().st_file_attributes` + `fsutil sparse queryflag` 三重外部校验） |
| 2 | 预分配 1 GiB 后物理占用 < 8 MiB | `SetFilePointerEx` + `SetEndOfFile`（**不能**逐块写零） | 同文件 `:284-293`（`GetCompressedFileSizeW` + `FILE_STANDARD_INFO.AllocationSize`） |
| 3 | `disk_usage` 返回物理占用而非逻辑长度 | `GetCompressedFileSizeW` / `GetFileInformationByHandleEx(FileStandardInfo)` | `:317-324`（与文件系统读数比对，容差 64 KiB） |
| 4 | `allocated_ranges` 返回真实已分配区间 | `DeviceIoControl(FSCTL_QUERY_ALLOCATED_RANGES)` | `:329-340`、`:442-460` |
| 5 | 补设稀疏标志不得回收已分配簇 | NTFS 独有语义（MS-FSCC：*Currently allocated clusters SHOULD NOT be deallocated*） | `:360-374`（对 16 MiB 密集文件补标志后 `disk_usage` 仍须 ≥ 16 MiB） |
| 6 | 不支持时抛 `WSParseError(kind="unsupported")` | Win32 错误码 `ERROR_INVALID_FUNCTION` / `ERROR_NOT_SUPPORTED` / `ERROR_INVALID_PARAMETER` | `:379-388` |

题包自带的机读声明 `metadata/windows_mechanism.json` 把上述 5 条机制逐条登记，并给出反事实结论：

> 主要实现只能由 Win32 稀疏文件控制码构成……`fallocate`、`F_PREALLOCATE`、`SEEK_HOLE` 语义不同，也不会产生 `FILE_ATTRIBUTE_SPARSE_FILE` 这个文件属性。……评测点还压在 NTFS 的一条独有语义上——补设的稀疏标志不会回收已经分配的簇，POSIX 侧没有对应行为。

---

## 二、为什么无法用平台无关方式通过（三条防线）

这道题不是“贴了 Windows 标签的通用题”，它的判分结构堵住了所有跨平台替代路径：

1. **观测不采信候选自己的返回值。** 隐藏套件自己开 `CreateFileW` 句柄、自己发 `DeviceIoControl`、自己读 `GetCompressedFileSizeW`，并调用 `fsutil sparse queryflag` / `fsutil file queryAllocRanges` 取得“候选无法伪造”的外部结论（套件头部注释即声明 “No value returned by the candidate package is ever used as the reference for its own correctness”）。
2. **测试样本由测试自己构造。** `sparse_64m`（64 MiB 逻辑、约 128 KiB 实占）、`hole_8m`（8 MiB 全空洞）、`one_extent.bin`（单区间）三个 fixture 都由套件用 Win32 现场创建，候选事先不知情 → “自己记账、事后按记录回报”的假实现必然失败。
3. **起点刻意不给捷径。** `environment/workspace/wsparse/_winapi.py` 只绑定了 `GetCompressedFileSizeW` 一个函数，`DeviceIoControl` / `FSCTL_*` / `SetEndOfFile` 全部要候选自己实现；而起点 `alloc.py:50-54` 正是“逐块写零字节”的缺陷写法（真占盘），修好它**只能**换成稀疏控制码 —— Windows 上 `os.truncate` 扩展文件会实打实分配每个簇（CPython issue 39910），Python 在 Windows 也没有 `posix_fallocate`、没有可用的 `st_blocks`、没有 `SEEK_HOLE`。

平台守卫与环境门禁同样闭合：

- 套件在非 Windows 上 `pytest.skip(..., allow_module_level=True)`（`:25-29`）；
- `environment/validate_environment.ps1` 在真实卷上要求 `fsutil fsinfo volumeinfo` 报出 `File System Name : NTFS` 且含 `Supports Sparse files`，否则环境判 `INVALID`（`:33-43`）。

---

## 三、控制组实测（只可能在真实 Windows 上产生）

沿用包内 `verifier/evidence/` 的实跑记录：

| 控制组 | 逐用例结果 | reward |
|---|---|---|
| Golden（`solution/reference` 覆盖候选包） | **20/20 PASS** | 1 |
| no-change（未改动的缺陷起点） | **10 条 F2P 全 FAIL + 10 条 P2P 全 PASS** | 0 |

no-change 挂掉的 10 条恰好就是第一节表里的机制判据（`f2p-preallocate-marks-file-sparse`、`-does-not-materialise-the-file`、`-disk-usage-is-physical-not-logical`、`-allocated-ranges-are-the-real-extents`、`-late-sparse-flag-does-not-free-clusters` 等）。**只要判据不是真的绑在 NTFS 上，“逐块写零”的缺陷实现不可能在物理占用和已分配区间上被抓住** —— 这条控制组曲线本身就是 Windows 价值的实测证据。同时它符合甲方要求的 “NOP 侧 P2P 全 PASS、核心 F2P 全 FAIL”。

隔离方面也达标：包根 `tests/test_wsparse_semantics.py` 与判分侧正本 `verifier/tests/test_wsparse_semantics.py` 的 sha256 相同（`302caee314c3ec21…`），平台投放副本与隐藏正本分层正确。

---

## 四、但该包当前不可交付（与 Windows 价值无关）

用甲方主入口 `run_qc.py::static_check()` 实测，`static_pass = False`，7 条错误：

```
missing tests/judge.toml
missing tests/rubric.json
required_testcases.json must be a list
rubric.json has no task_id
required testcase manifest must contain at least 5 testcases; got 0
required testcase manifest must contain both F2P and P2P
referenced files are missing: solution\reference\wsparse, tests/rubric.json
```

逐条定性：

| # | 问题 | 定性 |
|---|---|---|
| 1 | `tests/required_testcases.json` 顶层是**对象**（`{"schema_version":…,"testcases":[…]}`），甲方要求顶层**数组**（218/219 均为数组） | **真缺陷**。直接导致解析出 0 条，并连带触发第 5、6 条 |
| 2 | `tests/` 缺 `judge.toml`、`rubric.json` | **真缺陷**（219 的 `tests/` 六件套齐全） |
| 3 | `tests/run_tests.ps1:172-173` 把未采集到的 required 用例直接写成 `FAIL`（注释自述 “not an infrastructure fault”） | **真缺陷**，与甲方在 215/216 返修原因里点名的“缺测/执行故障应为 INVALID，不能输出正式 0 分”是同一毛病 |
| 4 | 根目录无 `jobs/`（14 或 12 个原生 Harbor job 未组装），`validate_jobs` 直接抛 `FileNotFoundError` | **未完成**：目前只有本机控制组证据，缺真实容器 Oracle/NOP ×3 与模型轮次 |
| 5 | `solution\reference\wsparse` 被报缺失 | 大概率是**检查器语义误读**（`solve.ps1` 里的容错候选路径被正则当成必须存在的交付文件），与 215/216 同类，可通过运行时拼接路径规避 |
| 6 | 题面未定义 `kind="badarg"`，但 `p2p-preallocate-rejects-a-negative-size` 要求它 | 可辩护：起点 `alloc.py:14-16` 已经这么实现，属于候选可见的公开行为；但题面补一句更稳妥 |

### 身份提示

包内 `task_id = wfflab__wsparse-215`，与飞书表 215 号记录（当前指向 `wfflab__wfmt-215-v2.1.0-delivery`）**共用 215 编号但不是同一个包名**。这道题实际上就是 `wfmt-215` 的 `REFIT-2026-10-13.md` §4 所列候选改造方向 1（“NTFS 稀疏/压缩文件容器”）的落地物。若要作为 215 的替换版本发布，需先与甲方/采购确认身份与版本口径，避免同一编号出现两个包。

---

## 五、总结

| 维度 | 判定 |
|---|---|
| **Windows 价值（十项人工门禁第 5 项）** | **PASS** —— 高价值，反事实清晰，无可绕过的跨平台替代 |
| 判分语义（缺测/故障是否 INVALID） | FAIL（`run_tests.ps1` 把未采集用例记 FAIL） |
| 交付结构完整性 | FAIL（缺 `tests/judge.toml`、`tests/rubric.json`；清单顶层格式错误） |
| 运行证据完整性 | 未完成（无 `jobs/`，控制组仅本机） |
| 当前能否交付 | **不能**，但阻塞项全部是格式与证据组装问题，不涉及题目内核 |

---

## 附：本次评估的证据位置

- 题面与范围声明：`wfflab__wsparse-215-v1.0.0-delivery/instruction.md:9-13`、`:29-68`
- 机读机制声明：`.../metadata/windows_mechanism.json`
- 隐藏套件：`.../tests/test_wsparse_semantics.py`（同 `verifier/tests/` 副本）
- 参考解：`.../verifier/oracle/reference/wsparse/_winapi.py`（32 处 Win32 调用）
- 缺陷起点：`.../environment/workspace/wsparse/alloc.py`、`_winapi.py`
- 环境门禁：`.../environment/validate_environment.ps1:25-43`
- 控制组证据：`.../verifier/evidence/golden/`、`.../verifier/evidence/no_change/`
- 本次静态门禁实测：`harbor-windows/_qc_runs/wff-4pkg-static-qc/static-wsparse.json`

---

# 六、机制级复核（2026-10-14 二次核查）

本节回答“测试的是不是 Windows 专属能力、有没有真正依赖操作系统机制”，结论基于参考解源码逐行核对，而不是题包自己的声明。

## 6.1 参考解实际调用的 Win32 入口（`verifier/oracle/reference/wsparse/_winapi.py`）

| Win32 入口 | 常量/参数 | 用途 | 代码位置 |
|---|---|---|---|
| `CreateFileW` | `GENERIC_READ\|GENERIC_WRITE`、`OPEN_ALWAYS`/`OPEN_EXISTING`、`FILE_SHARE_ALL` | 取得真实文件句柄 | `:133-140` |
| `DeviceIoControl` | **`FSCTL_SET_SPARSE`（0x000900C4）** | 置稀疏标志 | `:150-158` |
| `DeviceIoControl` | **`FSCTL_QUERY_ALLOCATED_RANGES`（0x000940CF）** | 枚举真实已分配簇区间 | `:161-180` |
| `SetFilePointerEx` + `SetEndOfFile` | `FILE_BEGIN` | 只移动 EOF、不写数据字节 | `:185-192` |
| `FlushFileBuffers` | — | 让分配元数据落定 | `:195-198` |
| `GetFileInformationByHandleEx` | `FileStandardInfo(1)` | 读 `AllocationSize` / `EndOfFile` | `:201-217` |
| `GetCompressedFileSizeW` | — | 读物理占用（无需自持句柄） | `:220-228` |
| `CloseHandle` | — | 句柄释放 | `:143-145` |

另有 `FSCTL_SET_ZERO_DATA`（0x000980C8）已声明备用（`:38`）。

**非 Windows 行为不是降级而是拒绝**：`alloc.py:35-42`、`ranges.py:34-39`、`usage.py:30-35`、`flags.py:40-46` 一律抛 `WSParseError(kind="unsupported")` 并给出 “exists only on Windows” 说明。参考解里不存在任何 POSIX 分支。

## 6.2 为什么在 Windows 上绕不开标准库

| 候选可能想用的跨平台写法 | 在 Windows 上的实际结果 |
|---|---|
| `os.truncate` / `os.ftruncate` 扩展文件 | **实打实分配每个簇**，不产生稀疏（CPython [issue 39910](https://mail.python.org/pipermail/new-bugs-announce/2020-March/038706.html) 记录的正是这个语义差） |
| `posix_fallocate` | Windows 上不存在（POSIX only） |
| `os.stat().st_blocks` 求物理占用 | 该字段[不可移植](https://runebook.dev/en/docs/python/library/os/os.stat_result.st_blocks#1)，Windows 上不提供有效值 |
| `os.lseek(fd, 0, os.SEEK_DATA/SEEK_HOLE)` 枚举区间 | Windows 不支持，直接报错 |
| `shutil` / `pathlib` 任何接口 | 都不暴露物理分配信息 |

即：题面要求的三个公开 API，在 Windows 上**没有任何一个**能用标准库跨平台地实现。判据第 2、3、4 条的观测（`GetCompressedFileSizeW`、`FILE_STANDARD_INFO.AllocationSize`、`FSCTL_QUERY_ALLOCATED_RANGES`）同理。

## 6.3 依赖强度分层（这是对“Windows 价值”的精确边界）

| # | 机制判据 | 是否 Windows 独有 | 非 Windows 是否有等价行为 |
|---|---|---|---|
| 1 | 稀疏是文件的**显式属性位**（`FILE_ATTRIBUTE_SPARSE_FILE`，`fsutil sparse queryflag` 可读） | **是** | **无**。POSIX 没有“稀疏属性”，Linux 的稀疏只是块映射的隐含结果 |
| 5 | 补设稀疏标志**不回收**已分配簇（MS-FSCC 语义） | **是** | **无**。Linux 要释放必须先 `PUNCH_HOLE`，没有“标志”概念 |
| 2 | 预分配后逻辑长度 = size、物理占用 ≈ 0 | 接口是 | 有：`ftruncate` 在 Linux 上天然稀疏 |
| 3 | 报告物理占用（簇对齐） | 接口是 | 有：`st_blocks * 512`（口径不同：NTFS 是簇对齐 AllocationSize） |
| 4 | 报告已分配区间 | 接口是 | 有：`SEEK_DATA` / `SEEK_HOLE`（非所有文件系统支持） |

**结论**：Windows 价值成立，但真正的“反事实壁垒”集中在第 1、5 两条；第 2、3、4 条是“Windows 上的唯一可行接口”，不是“只有 Windows 才有的行为”。若甲方评审要求“整题的核心行为在 Linux 上完全无法复现”，这道题的强度属于**中等偏强**，而非无懈可击。

## 6.4 二次核查发现的三处实测问题

1. **题面宣称的外部观测有一条是死代码。** `instruction.md:13` 说评测器会用 `fsutil file queryAllocRanges` 观测；套件里 `_fsutil_alloc_ranges()`（`:219-220`）**定义了却从未被调用**（全文仅出现 1 次，即定义行）。`allocated_ranges` 的实际判据全部来自套件自己发的 `FSCTL_QUERY_ALLOCATED_RANGES`。这不影响 Windows 价值（两者都是 Windows 机制），但属于题面与实现不符，建议删除该函数或补上调用。

2. **判分依赖英文系统输出，存在本地化误杀风险。**
   - `tests/test_wsparse_semantics.py:212-216` 用 `"is set as sparse"` / `"is not set as sparse"` 匹配 `fsutil sparse queryflag` 的文本；
   - `environment/validate_environment.ps1:37-41` 用 `'File System Name : NTFS'`、`'Supports Sparse files'` 匹配 `fsutil fsinfo volumeinfo` 的文本。

   当前 `environment/Dockerfile:20` 用 `servercore:ltsc2022`（默认 en-US），因此现在能过；一旦换成 zh-CN 等非英文镜像，`fsutil` 会输出本地化文本，匹配失败返回 `"unknown"`，**正确实现会被误杀**。建议以 `os.stat().st_file_attributes` 位判断（套件已有）作为主判据，`fsutil` 仅作辅助，或在镜像里显式固定 en-US。

3. **测试只看结果、不约束实现手段。** 候选若用 `fsutil sparse setflag` / `fsutil file setZeroData` 子进程达成同样效果，也能通过，但这与 `instruction.md:13` “必须通过 Win32 文件系统控制码”的字面要求不符。`fsutil` 本身仍是 Windows 专属工具，所以不推翻 Windows 价值；若甲方要求“必须真调 API”，需要补机制层约束（静态检查或运行时钩子）。
