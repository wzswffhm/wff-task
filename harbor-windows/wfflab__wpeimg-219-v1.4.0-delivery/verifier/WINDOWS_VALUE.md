# Windows 价值与采购分类说明（wfflab__wpeimg-219，task version 1.4.0）

> **口径版本**：`windows-value-mapping-v3`（2026-10-13；v1 的过度声明已按 §2.2 更正，
> v3 追加 v1.4.0 的「判分期真实系统调用」一组）。
> 对应质检条目：`ZQ004-03 / ZQ005-03｜风险｜Windows 专属价值较低`
> （同批次同类口径，适用于所有 Windows 专项题包）。
> 对应手册条款：**QD-SP-12**、**QD-SP-18**；甲方《最新质检要求》第 3 条
> 「Windows 价值必须真实映射，否则归入通用编码题池」。

本说明遵循专家修复步骤第 1 条：**把题目要求逐条映射到真正依赖的机制**，并给每条
标注**证据强度**（A 级 = 真有 Windows 系统组件调用可复算；B 级 = Windows 生态 /
格式规范、换平台无对应物但判分不触发系统调用；C 级 = 通用平台语义）。

## 1. 结论

**本题具备真实的 Windows 反事实价值，主张 Windows 采购分类。**
反事实问题「把目标 OS 换成 Linux/macOS，主要实现、错误根因和 Evaluator 是否
基本不变？」的答案是**否**：本题的被测对象是 **Windows PE 映像**，最硬的一条
判据（映像校验和）只有 **Windows 自己的映像帮助库**能给出权威值，这两点在非
Windows 平台上都不存在等价物。

| 项 | 取值 |
| --- | --- |
| `primary_direction` | Windows / 可执行映像格式与生态（PE/COFF） |
| 反事实价值 | **高**：PE 是 Windows 原生映像格式；权威校验和只有 Windows 提供 |
| 证据强度构成 | **A 级 6 条**：构建期锚定 2 条（校验和，含系统库调用留档）+ **判分期真实系统调用 4 条**（`windows-live-services`）；**B 级 8 条**（PE 格式与生态语义）；C 级 1 条 |
| 是否入 Windows 专属能力计分 | **是**（依据见 §2.2，边界见 §2.2 末段） |

## 2. 逐条映射：题面要求 → 依赖的机制（带证据强度）

> **自检更正（2026-10-13）**：本节初版把若干条写成「依赖 Windows 加载器语义 /
> 文件句柄语义」，但那些断言的**判分过程并没有调用任何 Windows API**。逐条压过
> 一遍后改为按**证据强度**分三级标注，避免用措辞把格式规范说成操作系统机制：
>
> - **A 级（OS 机制，可证明）**：权威值/判据确实出自 Windows 系统组件，且有留档
>   可复算（含调用参数与返回码）。
> - **B 级（Windows 生态与格式规范）**：语义由 Microsoft 的 PE/COFF 规范与
>   Windows 生态惯例定义，Linux/macOS 没有对应物；但判分只做**离线字节比对**，
>   不触发系统调用。
> - **C 级（通用平台语义）**：换平台不变，不构成 Windows 价值。

### 2.1 逐条映射

| # | 题面 / 断言要求 | 依赖的机制 | 级别 | 本包中的证据 |
| --- | --- | --- | --- | --- |
| 1 | 两个样本必须被**真实描述**（机器类型、两种可选头布局、节区表） | PE/COFF 是 Windows 映像格式，字段语义由微软规范定义 | **B** | 样本是真实 Windows 二进制：`amd64-module.bin` 取自 python-3.12.9-embed 的 `winsound.pyd`（PE32+、6 节区、带 13304 字节尾部）；`i386-module.bin` 为按规范合成的最小 PE32。生成脚本 `evidence/select_pe_assets.py` |
| 2 | `compute_checksum(data)` 必须给出**与 Windows 映像校验和完全相同**的值 | **`imagehlp!MapFileAndCheckSumW`（Windows 系统库例程）** | **A** | `evidence/authoritative.py` 在 Windows 上调 `imagehlp.MapFileAndCheckSumW`，10 条 `status=0` 的结果落盘 `evidence/authoritative-checksums.json`，与隐藏套件常量逐条对应（例如 `amd64-module.bin` = 74415） |
| 3 | 该算法必须是**确定函数**（对任意输入成立，不只对样本） | 同上：算法由 Windows 例程定义 | **A** | `evidence/checksum-experiment.json`：12 个真实 Windows 二进制取原生值，4 种候选写法里只有「全量累加 + 两次 16 位折叠」吻合 12/12，变体 B 仅 1/12、变体 C 0/12 |
| 4 | `is_pe32_plus` 如实反映 `0x10B` / `0x20B` | 两种可选头布局由规范定义（前者 `ImageBase` 4 字节、后者 8 字节） | **B** | 样本覆盖两种布局：PE32+ `SizeOfOptionalHeader=0xF0`；PE32 `=0xE0` |
| 5 | `rva_to_offset` 的 RVA→文件偏移语义 | RVA 与文件偏移是两套地址空间，由规范与加载器映射规则定义 | **B** | 隐藏套件 `test_rva_*` 四例逐条对应题面 C 节 |
| 6 | 结构自检（越界、重叠、未对齐、`SizeOfHeaders`/`SizeOfImage` 不足） | 这些检查项与 Windows 加载器的验收条件一致 | **B** | 隐藏套件 8 条 `*_reports_structure`；`_structural_variants()` 逐条构造违规映像 |
| 7 | **A2**：`data_directories` 十六槽位置数组（PE32 偏移 96 / PE32+ 112）、`NumberOfRvaAndSizes` 决定有效槽位 | 目录数组的位置语义由 PE/COFF 规范定义；加载器按同一数组找导入表、重定位表、证书表 | **B** | 隐藏套件 4 例；`slot 12/15` 写标记读回；声明 0/3/16/64 与越界四种边界 |
| 8 | **A2**：`has_authenticode_signature` 必须要求证书表**真的**有文件字节支撑 | 证书表项第一个字段是**文件偏移**（全数组里唯一如此）而非 RVA；Authenticode 是 Windows 部署生态的既有形态 | **B** | `amd64-module.bin` 尾部 13304 字节是真实 PEM/PKCS#7 形态的签名字节（`evidence/probe_overlay.py` 打印前 48 字节：`30 82 33 ea 06 09 2a 86 48 86 f7 0d 01 07 02`）；合成样本无证书表 → `False` |
| 9 | 错误分类六类互斥，结构自检先于校验和 | 分类学对应加载器失败分类（如 `ERROR_BAD_EXE_FORMAT`）与 `CheckSumMappedFile` 的调用次序 | **B** | 隐藏套件 12 条分类断言 |
| 10 | `iter_sections(fileobj)` 惰性、不得整体读入、用带长度的 `read(n)` | 只依赖文件对象的 `read(size)` 契约 | **C** | `test_iter_sections_does_not_slurp_the_stream`：尾部放大 8 倍后首条节区前的读取量必须逐字节不变 |
| 11 | 实现**不得**调用 `ctypes` / `subprocess` | 反向声明：契约值由 Windows 例程定义，但实现必须自包含 | **A**（作为约束） | `test_package_has_no_external_dependencies` 扫描包内 `*.py` |
| 12 | **F2**：`signature_info()` 必须自行解析 PKCS#7 `SignedData` 的 DER（contentType OID、digestAlgorithms、证书数、签名者数），并对 `dwLength` 与文件不符的记录抛 `kind="structure"` | PKCS#7 与 `WIN_CERTIFICATE` 的字段语义由规范定义；Authenticode 是 Windows 部署生态的既有形态 | **B** | 判据锚定真实签名字节（`offset=13824`、`size=13304`、`revision=0x0200`、`certificate_count=4`、`signer_count=1`、`digest_algorithms=["sha256"]`）；`verifier/tests/win_services.py` 之外不调用任何系统服务 |
| 13 | **F3**：判分**过程本身**必须拿 Windows 系统服务来对照——`compute_checksum()` 要与 `imagehlp!MapFileAndCheckSumW` 对**判分时构造的变体**给出的值相等；`iter_sections()` 要在 `CreateFileW` 的真实句柄上有界读取 | **`imagehlp!MapFileAndCheckSumW` 是 Windows 系统库例程**（映像校验和的唯一权威实现）；**`kernel32!CreateFileW` / `GetFileSizeEx` 是 Windows 文件系统与句柄机制的入口** | **A** | `verifier/tests/win_services.py` 在判分期真实调用 imagehlp 与 kernel32；4 条断言每次判分都跑，系统组件缺失则 `pytest.fail` 显式暴露；变体权威值由系统库现取且要求 ≥3 个互不相同，硬编码无法通过 |

### 2.2 自检结论（哪几条真的落到操作系统机制上）

| 级别 | 条目 | 说明 |
| --- | --- | --- |
| **A（判分期真实调用）** | #13（`windows-live-services` 的 4 条） | 判分**过程本身**在 Windows 上调用系统组件：`imagehlp!MapFileAndCheckSumW` 对**判分时现场构造**的映像变体给出权威值；`kernel32!CreateFileW` 提供真实文件句柄，`GetFileSizeEx` 核对句柄长度。这 4 条断言离开 Windows 无法执行，判据不再依赖任何离线常量 |
| **A（构建期锚定）** | #2、#3（+ 作为约束的 #11） | 权威校验和的来源脚本与 10 条结果留档可复算；这一组的常量比对现在被 #13 的活体调用覆盖与复核，两者互为交叉验证 |
| **B** | #1、#4–#9、#12 | 语义由 PE/COFF 规范与 Windows 生态定义，换平台没有对应物（被测对象消失）；判分只做离线字节比对，不触发系统调用。这类是「Windows 专属格式/生态知识」，不是「操作系统机制」——本说明不再把它表述成「依赖加载器语义」 |
| **C** | #10 | 换平台不变（`io.BytesIO` 上的有界读），不计入 Windows 价值；真实句柄上的同类判据已提升为 A 级 #13 |

**诚实边界（v1.4.0 起）**：这道题现在**确实在判分期调用了 Windows 系统组件**——
`imagehlp.dll` 与 `kernel32.dll`，用途分别是「权威校验和的唯一来源」与「真实文件
句柄」。它仍然**没有**触及注册表、服务控制管理器、安全描述符、命名对象、进程/线程
调度或内核对象生命周期那些更深层的机制；B 级条目依旧只是 Windows 专属的格式与
生态语义。

### 2.3 判分期系统调用的落点与复核路径

`windows-live-services` 组由 `verifier/tests/win_services.py` 提供封装，全部在
**判分侧**（`C:\tests` 下），候选工作区里没有它：

| 系统组件 | 调用点 | 断言用途 |
| --- | --- | --- |
| `imagehlp!MapFileAndCheckSumW` | `win_services.live_checksum()` | 对样本与**判分时构造的变体**取权威校验和，要求 `compute_checksum()` 逐例相等；并额外要求 ≥3 个变体的权威值互不相同，使硬编码答案无法通过 |
| `kernel32!CreateFileW` / `GetFileSizeEx` | `win_services.open_real_handle()` | 用真实句柄驱动 `iter_sections()`，并核对句柄长度与文件长度一致 |
| CRT 句柄桥（`msvcrt.open_osfhandle`） | `win_services.handle_to_file()` | 把 Win32 HANDLE 交给 Python 文件对象，使被测函数面对的就是系统句柄语义 |
| 无界读检测 | `win_services.BoundedReader` | 拒绝 `read(-1)`/`readline`/`readlines`，把「有没有整体读入」变成真实句柄上的可测属性 |

复核方式：这几条断言**每次判分都在跑**，无需额外探针。若系统组件缺失，套件会以
`pytest.fail` 显式报出（判分环境故障，而不是静默跳过）——因为「判据没生效」本身
就是必须暴露的问题。构建期那一组的复核路径仍是：

```powershell
python verifier\evidence\authoritative.py
# 期望：10 条 status=0，且 checksum 与 verifier/tests 的 AUTHORITATIVE 常量逐条相同
```

## 3. 反事实（写清楚换成非 Windows 会发生什么）

| 换到 Linux / macOS | 结果 |
| --- | --- |
| 样本本身 | Linux/macOS 的系统二进制是 ELF / Mach-O；PE 映像只能作为外来文件出现，`/usr/bin` 下不存在 PE32+ 模块，也没有 Authenticode overlay 形态 |
| 权威校验和 | `imagehlp.dll` 不存在，`MapFileAndCheckSumW` / `CheckSumMappedFile` 没有对应导出；没有公认的跨平台权威实现（`pefile` 只做近似，且公认在部分映像上与 Windows 不一致） |
| 加载器语义 | RVA→文件偏移、`SectionAlignment`/`FileAlignment`、未初始化尾部、overlay 合法性等都由 Windows 加载器定义，ELF/Mach-O 没有同名语义 |
| 结论 | 换个平台这道题的**被测对象消失**，而不是「换个解释器照样过」 |

对照 `wfflab__wlogseg-218`（同批次的容器格式题）：那道题的字节布局、CRC-32 与
`read(n)` 契约在所有平台一致，已按同一口径**明确归入通用编码能力**，不主张
Windows 反事实价值。两题的处理方式不同，正是「逐条映射」而不是「统一贴标签」。

## 4. 证据

| 证据 | 路径 | 内容 |
| --- | --- | --- |
| 权威值取得脚本 | `evidence/authoritative.py` | 在 Windows 上调用 `imagehlp!MapFileAndCheckSumW` 取 10 个值 |
| 权威值结果 | `evidence/authoritative-checksums.json` | 10 条 `status=0` 的权威校验和 |
| 算法唯一性实验 | `evidence/checksum_experiment.py` | 4 种候选写法 vs Windows 原生值 |
| 算法唯一性结果 | `evidence/checksum-experiment.json` | 12 个真实 Windows 二进制，变体 A/D 吻合 12/12，变体 B 1/12，变体 C 0/12 |
| 样本来源与生成 | `evidence/select_pe_assets.py` | 样本选取/合成过程与逐字段打印 |
| 结构探针 | `evidence/probe_overlay.py` | 节区覆盖与尾部字节 |
| 样本身份 | 隐藏套件 `AUTHORITATIVE` 常量 + 下表 | sha256 与关键字段 |

样本身份（2026-10-13 实测）：

| 样本 | 大小 | sha256 | 关键字段 |
| --- | --- | --- | --- |
| `amd64-module.bin` | 27128 | `31c83cb8c5e3eb397252fe871c74fb163d90b88c9e7ac7fd689eeba88c0dd92e` | `machine=0x8664`、`magic=0x20B`、`nsec=6`、`SizeOfOptionalHeader=0xF0`、记录 `CheckSum=74415` |
| `i386-module.bin` | 2048 | `6115b2507ee908fc7e402761b490d2aea4e2e951dc6e2f2ee5ce56b6bce5aff7` | `machine=0x14C`、`magic=0x10B`、`nsec=2`、`SizeOfOptionalHeader=0xE0`、记录 `CheckSum=9700` |

复现命令（需在 Windows 上执行；`evidence/` 内的脚本只作审计留档，不参与判分）：

```powershell
python evidence\authoritative.py           # 重取 10 个权威校验和
python evidence\checksum_experiment.py     # 重跑 4 种算法的唯一性实验
python evidence\select_pe_assets.py --out <assets 目录> --check
```

## 5. 边界与未实施项

- 本题**不**声称 PE 解析只能在 Windows 上运行：解析器本身是纯 Python，跨平台可跑。
  被主张的是**被测契约与被测样本来自 Windows**（第 2 节逐条），这符合甲方
  「不得只改题名或强加平台标签」的反面要求——本题没有改题名，也没有加标签。
- **判分期确实调用系统组件**（v1.4.0 起）：`imagehlp!MapFileAndCheckSumW` 与
  `kernel32!CreateFileW` 都在判分过程中被真实调用，落点见 §2.3。构建期锚定的那一组
  仍然保留，两者互为交叉验证。
- **不声称** B 级条目是「操作系统机制」：它们是 Windows 专属的格式与生态语义，
  判分只做离线字节比对。v1.4.0 已经把原先属于这一类的两件事（权威校验和、
  `iter_sections` 的读取上界）提升为判分期的真实系统调用，因此 A 级不再是「只有
  构建期锚定」；仍未覆盖的是注册表、安全模型、进程/线程、内核对象生命周期等更深
  的机制。
- 未新增需求，因此**不追溯扣旧样本**：v1.0.0 / v1.1.0 / v1.2.0 / v1.3.0 的历史轨迹与分数保持原样，
  本说明与四轮整改记录并列归档。
- v1.2.0 新增的 A2（目录表 + Authenticode 尾部）与 v1.3.0 新增的 F2（自行解析
  PKCS#7 SignedData DER：contentType OID、digestAlgorithms、证书数、签名者数）
  都属于 **B 级**：提升的是 Windows 专属语义密度与判分颗粒度（27 → 34 → 39 条），
  不是新增系统调用。签名记录体本身仍是 Windows 部署生态的产物（微软签发的
  Authenticode 签名字节），但没有调用 `WinVerifyTrust` 之类的系统服务。
- v1.4.0 新增的 F3（`windows-live-services`，4 条）是 **A 级**：它不要求实现增加
  功能，而是**换掉判据的来源**——权威校验和改为判分时向 `imagehlp` 现取，流式
  契约改为在 `CreateFileW` 的真实句柄上验证。颗粒度 39 → 43 条。
- 未覆盖（如后续立项可考虑）：导入表/导出表/重定位表的**内容**解析、`.NET` CLI 头、
  Authenticode 签名结构本身（PKCS#7 解析）。这些同样具备 Windows 专属价值。
