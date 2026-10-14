# 阶段 2 设计定稿 — wfflab__wsparse-215

> 记录时间：2026-10-14。上游依据：CPython issue 39910《os.ftruncate on Windows
> should be sparse》（reporter Mingye Wang，2020-03-09 提交，状态 open）。
> 本文件是阶段 2 的冻结记录，后续阶段不得在未回改本文件的情况下改动题面条款。

## 1. 为什么这个题目满足 Windows 专属

上游 issue 的复现命令就是判据：

```
cmd> echo > 1.txt
cmd> python -c "__import__('os').truncate('1.txt', 1024 ** 3)"
cmd> fsutil sparse queryFlag 1.txt
```

在容器里实测（Windows Server 2022 build 20348，`mcr.microsoft.com/windows/servercore:ltsc2022`，
Hyper-V 隔离，NTFS）：

```
os.truncate(64MB): st_size=67108864 compressed=67108864 sparse_bit=False
fsutil queryflag: This file is NOT set as sparse
```

即 CPython 3.12.9 上该缺陷**依然存在**，而且缺陷本身只在 Windows 上成立：同一段
代码在 Linux 上扩展文件天然是稀疏的。issue 给出的正确做法（aria2
`src/AbstractDiskWriter.cc`）是先发 `FSCTL_SET_SPARSE`，再 seek + `SetEndOfFile`。

跨平台替换性判定：`FSCTL_SET_SPARSE` / `FSCTL_QUERY_ALLOCATED_RANGES` /
`GetCompressedFileSizeW` / `FILE_STANDARD_INFO.AllocationSize` 在 Linux/macOS 上没有对等物
（`fallocate`、`F_PREALLOCATE`、`SEEK_HOLE` 语义不同，也不产生
`FILE_ATTRIBUTE_SPARSE_FILE` 属性）。反事实判定因此为「否」。

## 2. 环境层能力探测（F5 的落点）

`environment/validate_environment.ps1` 必须先在环境层挡住非 Windows / 非 NTFS：

```
Fail 'the NTFS volume does not advertise sparse-file support'
```

同一文件里还有 `OSVersion.Platform -ne [System.PlatformID]::Win32NT` 与
`File System Name : NTFS` 两条断言。任何一条不成立 → 就绪探测 exit 1 →
本次运行是 INVALID（基础设施不合格），不是候选 0 分。

容器内实测的卷能力（`fsutil fsinfo volumeinfo C:`）：

```
File System Name : NTFS
Is ReadWrite | Is Thinly-Provisioned | Supports Sparse files
Supports file-based Compression | Supports Reparse Points | Supports Named Streams
Supports Hard Links | Supports Extended Attributes | Supports Open By FileID
Max Component Length : 255 | Volume Serial Number : 0x7aa00ef6
```

## 3. 题面条款与机制锚点（F3 / F4）

排他声明（逐字写入 `instruction.md`，并登记在 `metadata/windows_mechanism.json`）：

> 本任务的目标平台是真实的 Windows + NTFS，验收不使用其他操作系统，也不需要实现其他操作系统的版本。

五条机制锚点，每条绑定一段逐字题面条款、一段 `test_ref` 与一条 F2P 用例：

| # | 机制 | 题面条款 | test_ref | F2P 用例 |
|---|---|---|---|---|
| 1 | `DeviceIoControl(FSCTL_SET_SPARSE)` 置位稀疏标志 | A 第 1 条 | `verifier/tests/test_wsparse_semantics.py#L276-L282` | `f2p-preallocate-marks-file-sparse` |
| 2 | `SetFilePointerEx` + `SetEndOfFile` 不改写数据地扩展 | A 第 2 条 | 同文件 `#L284-L293` | `f2p-preallocate-does-not-materialise-the-file` |
| 3 | `FSCTL_QUERY_ALLOCATED_RANGES` 枚举真实已分配区间 | D 第 1 条 | 同文件 `#L329-L340` | `f2p-allocated-ranges-are-the-real-extents` |
| 4 | `GetCompressedFileSizeW` 读物理占用 | C 第 1 条 | 同文件 `#L317-L327` | `f2p-disk-usage-is-physical-not-logical` |
| 5 | 稀疏标志不可回溯（MS-FSCC: Currently allocated clusters SHOULD NOT be deallocated） | E 第 1 条 | 同文件 `#L360-L377` | `f2p-late-sparse-flag-does-not-free-clusters` |

## 4. 判据来源（全部在容器内实测，不是推断）

| 场景 | 实测结果 |
|---|---|
| 先置稀疏标志，再 `SetEndOfFile(64MB)` | `AllocationSize=0`，`GetCompressedFileSizeW=0` |
| 之后写 4096B@0 与 8192B@32MB，再 `FlushFileBuffers` | `AllocationSize=131072`，`GetCompressedFileSizeW=131072` |
| 同一次调用里的 `FSCTL_QUERY_ALLOCATED_RANGES` | `[(0, 65536), (33554432, 65536)]` |
| 关闭并重开句柄后复测 | 完全一致，持久 |
| `fsutil sparse queryflag` | `This file is set as sparse` |
| `fsutil file queryAllocRanges offset=0 length=67108864` | `Allocated range[0]: Offset: 0x0 Length: 0x10000` / `Allocated range[1]: Offset: 0x2000000 Length: 0x10000` |
| **不置标志**直接 `SetEndOfFile(64MB)` | `AllocationSize=67108864`，区间 `[(0, 67108864)]` |
| 密集之后**补设**稀疏标志 | `setsparse=True`，但 `AllocationSize` 仍 `67108864` → 不可回溯 |
| 关闭再打开后 `st_file_attributes` | `0x220`（`0x200` = `FILE_ATTRIBUTE_SPARSE_FILE`）→ 标志持久 |
| 目录句柄上发 `FSCTL_SET_SPARSE` | `ok=False err=87`（`ERROR_INVALID_PARAMETER`） |
| 目录上的 `FSCTL_QUERY_ALLOCATED_RANGES` | `ok=False err=87` |
| 空文件置位后关闭重开 | `AllocationSize=0`，`compressed=0`，稀疏位保持 |

**测量纪律**：写入之后内核不会立刻更新分配元数据，必须 `FlushFileBuffers` 或关闭重开
句柄再测。评测器（隐藏套件）因此一律「另开句柄 → flush → 测量」。

## 5. 缺陷版模块（`environment/workspace/wsparse`）冻结形态

| 文件 | 缺陷 |
|---|---|
| `alloc.py` | 用 `b"\x00" * n` 写满尾部来预留空间（即 issue39910 描述的写零扩展） |
| `usage.py` | 返回 `os.stat(path).st_size`（逻辑长度） |
| `ranges.py` | 任何非空文件都返回 `[(0, size)]` |
| `flags.py` | 只报告当前状态、从不写属性 |
| `_winapi.py` | 只绑定了 `GetCompressedFileSizeW`，而且没有任何调用点 |

`errors.py` 与 `__init__.py` 在缺陷版与参考版之间保持一致（API 不变）。

## 6. 样例文件的处置（阶段 3 的实测修正）

稀疏性属于**磁盘布局**而非字节内容，无法穿过 zip、构建上下文或容器层。最初的设计是在
镜像构建时于 NTFS 卷上生成 `sparse_64m.bin` / `hole_8m.bin` / `dense_1m.bin`，实测该层
在提交时失败：

```
hcsshim::ImportLayer failed in Win32: The system cannot find the path specified. (0x3)
```

**定稿改为**：不随包提供任何稀疏样本。`environment/workspace/assets/` 只放一个 64 KiB 的
普通密集对照文件 `dense_64k.bin`；隐藏套件用它自己的句柄创建它要测的每一个稀疏 fixture。
这同时强化了三层锁——评测结论完全建立在评测器自己持有的内核对象上。

## 7. 判分面

- F2P 10 条、P2P 10 条，共 20 条（见 `tests/required_testcases.json`）。
- 二值判分：20 条全部 PASS 才得 1 分；无权重、无部分分。
- 基础设施故障（候选包缺失、隐藏套件未注入、判分产物缺失或 `run_validity != VALID`）
  一律 INVALID 并 exit 2，绝不伪装成候选 0 分。
