# Windows 价值与采购分类说明（wfflab__wlogseg-218，task version 1.1.0）

> **口径版本**：`windows-value-mapping-v1`（2026-10-13）。
> 对应质检条目：`ZQ004-03 / ZQ005-03｜风险｜Windows 专属价值较低`
> （同批次同类口径）。对应手册条款：**QD-SP-12**、**QD-SP-18**。
>
> **免责声明**：本说明是对已交付产物 `wfflab__wlogseg-218` 的分类澄清与后续
> 路线记录，**不代表修改或重评了原始产物**。原始作答记录、原始分数与原始证据
> 一律保持原样；本说明只新增口径，不改写历史。

本说明遵循专家修复步骤：**把题目要求逐条映射到真正依赖的操作系统机制**；映射
结果若显示价值不足，则按第 2 条**明确归入通用编码能力并调整采购分类**，而不是
只改题名或强加平台标签。

## 1. 结论

**本题不主张 Windows 反事实价值，按「通用编码能力（Windows 运行时执行）」归类。**

反事实问题「把目标 OS 换成 Linux/macOS，主要实现、错误根因和 Evaluator 是否基本
不变？」的答案是**是**：换掉解释器与文件系统后，本题的全部断言仍然成立，分数
不会变化。因此按甲方《最新质检要求》第 3 条，本题归入**通用编码能力题池**。

| 项 | 取值 |
| --- | --- |
| `primary_direction` | 通用编码能力（二进制容器格式 / 校验和 / 流式 IO） |
| `windows_target` | 如实标注为**执行平台**，不作为 Windows 专属能力 |
| 反事实价值 | **低**：字节布局、CRC-32、异常分类与 `read(n)` 契约都是平台无关语义 |
| 是否入 Windows 专属能力计分 | **否** |

## 2. 逐条映射：题面要求 → 依赖的 OS 机制（逐项核对）

| 题面要求 | 依赖的 OS 机制 | 判定 |
| --- | --- | --- |
| A. 样本 `verify` 为真、`pack(unpack(sample)) == sample` 逐字节一致 | 无（纯内存字节运算） | 平台无关 |
| B. `unpack` / `pack` 的段语义（`seg_id` 0..65535、`payload` 为 `bytes`） | 无 | 平台无关 |
| C. 段区与尾部索引布局必须与样本实际字节一致 | 无（容器内部布局，与文件系统无关） | 平台无关 |
| D. 尾部校验和是**通用 32 位 CRC 变体**，覆盖文件头与段区 | 无（`zlib.crc32` / CRC-32/ISO-HDLC，跨平台一致） | 平台无关 |
| E. 错误分类 `magic / version / truncated / structure / checksum`，`verify` 不得抛异常 | 无（纯 Python 异常对象） | 平台无关 |
| F. `iter_segments(fileobj)` 惰性、只用带长度的 `read(n)`、读完校验尾部 | 只依赖文件对象的 `read(size)` 契约；测试内由 `GuardedReader` / `io.BytesIO` 提供，**不依赖 Win32 句柄语义** | 平台无关（`read(n)` 在 POSIX 与 Windows 上语义一致） |
| G. 公开 API 名称与签名不得回归 | 无 | 平台无关 |

明确**不依赖**：注册表、NTFS 重解析点/ACL/大小写语义、Win32 API、命名对象、
进程与服务、计划任务、代码页与 `PATHEXT`、PowerShell 特有行为、DPAPI。
「在 Windows 容器里执行」只是交付载体，**不构成** Windows 采购价值。

## 3. 分类调整（本次执行项）

| 字段 | 调整后 |
| --- | --- |
| `primary_direction` | 通用编码能力（Windows 运行时执行） |
| `windows_target` | 执行平台，非被测能力 |
| 采购归类 | 入通用编码题池；**不参与** Windows 专属能力（QD-SP-12 / QD-SP-18）计分 |
| 题名 / 标签 | **未改**。没有通过改名或加字段、加标签的方式伪装成 Windows 题 |

## 4. 若需要 Windows 专属评测（未实施，供后续立项）

按专家修复步骤第 3 条：**新增有实际产品需求的 Windows 语义，发布新版后重新
作答**；**新需求不得追溯扣旧样本**（不能拿旧一轮作答判定新需求失败）。候选方向
（任一均需新版本号并重跑控制组与模型，与 `wfflab__wpeimg-219` 的 PE 语义族不重复）：

1. **NTFS 稀疏 / 压缩区间的流式纪律**：要求 `iter_segments` 在稀疏区间上保持
   O(已读) 内存（`FSCTL_QUERY_ALLOCATED_RANGES` 或等价能力）。
2. **Windows 文件共享与句柄语义**：要求容器在被另一进程以 `FILE_SHARE_READ`
   打开时仍可流式读取，并以约定分类报 `ERROR_SHARING_VIOLATION`。
3. **重解析点 / 备用数据流（ADS）落盘**：要求容器写入 ADS 或跨 junction 解析到
   真实文件，判据依赖重解析点语义。

改造后必须复核：控制组 Golden=1 / no-change=0、区分度重跑、分类与采购目标一一对应。

## 5. 证据

| 证据 | 路径 | 说明 |
| --- | --- | --- |
| 断言清单 | `tests/test_wlogseg_semantics.py`（平台投放副本）/ `verifier/tests/test_wlogseg_semantics.py`（判分侧正本，两者 sha256 相同） | 26 条断言，全部只触及第 2 节的平台无关项 |
| 判据与归因 | `verifier/rubric.conditions.json` | 每条 rubric 的判据 |
| 题面 | `instruction.md` | 验收标准 A–G |
| 隔离与分层 | `verifier/ISOLATION.md` + `verifier/negative_access_probe.ps1` | 公开测试 / 隐藏验收 / 参考解的分层与负访问证据 |
| 分类字段 | `task.toml` 的 `metadata.tags` 与 `_index/tasks_index.csv` | 归类落点 |
