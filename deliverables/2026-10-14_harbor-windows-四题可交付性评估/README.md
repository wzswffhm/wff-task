# harbor-windows 四题可交付性评估（2026-10-14）

评估对象：飞书 `华创-windwos作业` 表（Base `EsJebL8JJaf7g4sIbItcnMFgnvg` / table `tblRDxcGkblflMBA`，节点 `O1qjw1qFRijaf8kal5scROn9nmc`）中标注人 **wff** 名下 4 条记录对应的题包，其中 **3 条带返修原因**（215 / 216 / 218），219 无返修原因。

判据：
1. 甲方自检包 `harbor-windows/_reference/windows-harbor-qc/`（用户指定）；
2. 甲方报告 `C:\Users\Administrator\Desktop\Windows-48题质检-专家修复详解版-20261012\`；
3. 采购质检手册十项人工硬门禁（`references/quality-gates.md`）。

---

## 一、结论速览

| 题包 | 包内版本 | 飞书返修原因 | Windows 专属能力 | 甲方静态门禁（2026-10-14 口径） | 是否还能交付 |
|---|---|---|---|---|---|
| `wfflab__wfmt-215` | 2.1.1 | 有（4 条） | **无** | layout PASS / **jobs FAIL 251 条** / gate FAIL | **不能** |
| `wfflab__wchunk-216` | 1.2.1 | 有（4 条） | **无** | layout PASS / **jobs FAIL 277 条** / gate FAIL | **不能** |
| `wfflab__wlogseg-218` | 1.1.0 | 有（1 条：仅 Windows 价值） | **无** | **全部 PASS** | 作为 Windows 题**不能**；甲方书面同意移出 Windows 池后可作为通用编码题交付 |
| `wfflab__wpeimg-219` | 1.4.0 | 无 | **有**（imagehlp / kernel32） | layout PASS / jobs PASS / **gate FAIL（区分度）** | 暂不能；补区分度判据并重跑后可交付 |

**一句话结论**：三个返修题包（215 / 216 / 218）的“没有依赖 Windows 专属能力”不是误判——题面和源码里**一处 Windows 机制都没有**，按甲方十项人工硬门禁第 5 项必然 `FAIL`，而该项一挂整题即 `FAIL`，所以这三题**在当前形态下都不能作为 Windows 专项题交付**。其中 218 除这一条外已全部达标，215 / 216 还叠加了 job 归档层与身份门的整层阻塞。

---

## 二、核心问题：Windows 专属能力（三题全部不成立）

判据原文（`references/quality-gates.md` §5）：

> 复核时写出 Windows 反事实：如果换到 Linux 或普通跨平台 Runtime，哪个核心行为会消失或发生实质变化。……只有启动脚本使用 PowerShell、路径里出现盘符、镜像是 Windows，不能单独证明 Windows 价值。**若核心功能可原样移到 Linux，测试也不依赖真实 Windows 语义，本项 `FAIL`。**

### 2.1 实测证据（本次复核）

| 题包 | `instruction.md` 中 Windows 语义关键词命中 | Python 源码中 Windows API 命中 |
|---|---|---|
| wfmt-215 | **0 行** | **0 处** |
| wchunk-216 | **0 行** | **0 处** |
| wlogseg-218 | **0 行** | **0 处** |
| wpeimg-219（对照） | **10 行** | 98 处（`imagehlp!MapFileAndCheckSumW`、`kernel32!CreateFileW`、`msvcrt.open_osfhandle`） |

检索词：`Windows|NTFS|注册表|registry|DPAPI|ACL|重解析|句柄|imagehlp|Win32|PowerShell`（题面），`winreg|ctypes|windll|WinDLL|FILE_SHARE|FSCTL|CryptProtect|CreateFileW|kernel32|_winapi`（源码）。

### 2.2 包内自述构成反向证据

三题的 `verifier/WINDOWS_VALUE.md` 都**自己写明**：

> 本题**不主张 Windows 反事实价值**。它的能力域是**通用编码能力**……同一个包在 Linux 上换掉解释器即可原样通过，分数不会变化。

并各自声明 “入通用编码题池；不参与 Windows 专属能力计分”。甲方返修原因正是直接引用了这段自述。

### 2.3 三条可选路径的现状

| 路径 | 215 | 216 | 218 |
|---|---|---|---|
| ① 逐条映射 OS 机制，找出真实 Windows 依赖 | 已做 → 结论“无” | 已做 → 结论“无” | 已做 → 结论“无” |
| ② 按真实采购分类移出 Windows 池 | 已改分类字段，**未经甲方确认** | 同左 | 已改分类字段，**未经甲方确认** |
| ③ 发布含 Windows 机制的新版并重跑 | **未实施** | **未实施** | **未实施**（REFIT §4 仅列为候选方向） |

> 218 的 `REFIT-2026-10-13.md` R2 明确把 Windows 机制改造写成“**未实施，供后续立项**”的候选清单（NTFS 稀疏/压缩区间流式纪律、`FILE_SHARE_READ` 与 `ERROR_SHARING_VIOLATION`、重解析点/ADS 落盘）。

---

## 三、Windows 价值之外的阻塞项

### 3.1 wfmt-215 / wchunk-216：job 归档层整层不合规

（下表为 2026-10-14 口径实测）

| 错误类型 | 215 | 216 |
|---|---|---|
| testcase 状态非终态（`NONE`） | 192 | 228 |
| 缺 `verifier/verifier.log` | 12 | 14 |
| `task_checksum` 与交付包不一致 | 12 | 12 |
| testcase 集合与 `required_testcases.json` 不符 | 12 | — |
| 模型 alias 不可识别 | 6 | 6 |
| 缺 `agent/trajectory.jsonl` | 6 | 6 |
| `model-result.json` provenance 不完整 | 6 | 6 |
| `trajectory.jsonl` 为空 | 3 | 3 |
| Oracle / NOP 轮次识别为 0 | 2 | 2 |
| **合计** | **251** | **277** |

根因：两包的 `jobs/` 仍是**旧协议归档**——`verifier/result.json` 用 `outside-harbor-result-v1` + `items[].passed`，而甲方解析器读 `cases[]` + `status: PASS/FAIL`，于是全部 case 被记为 `NONE`；控制组 job 也没有 `ctl-oracle-*` / `ctl-nop-*` 语义名，甲方识别不出 Oracle/NOP。218 / 219 已是新协议，所以不受影响。

**身份门**（全部 job 的 `task_checksum` 必须等于交付包 Harbor dirhash）：

| 包 | 包 dirhash | job `task_checksum` | 一致 |
|---|---|---|---|
| 215 | `e29b36d0333757ef…` | `e5766a67f6346b56…` | **否** |
| 216 | `7c9e690e0d9db620…` | `d6d317c507752c0f…` | **否** |
| 218 | `a4e33ca3981e9014…` | 同左 | 是 |
| 219 | `8af4efbac29d722f…` | 同左 | 是 |

即 215 / 216 是“跑完分之后包又被改过”，旧 job **全部作废**，必须冻结包后整批重跑。

**其他缺件与记录问题**：

- 215 / 216 的 `tests/` 下**没有**平台投放副本 `test_*_semantics.py`（只有 `verifier/tests/` 有）；218 / 219 是两份且 sha256 相同。这是真缺件（Harbor 只从包根 `tests/` 投放套件）。
- 215 飞书表填 `Opus 3/3`，包内 job 日志合计为 **2**，与返修原因指出的不一致**至今未修正**。
- 215 / 216 目录名版本（2.1.0 / 1.2.0）与包内身份（2.1.1 / 1.2.1）不一致。

### 3.2 wpeimg-219：区分度门禁不过（题目过易）

```
model distinction gate failed: Qwen and Opus are both full-score across all required runs
(model_score_sum tied at 3), and Opus testcase_pass_sum (129) is not strictly greater than
Qwen (129); the required testcases do not separate the two models
```

飞书表同样填 Qwen `3/3`、Opus `3/3`，逐 testcase 43×3 = 129 对 129，**两个主模型完全平手**。219 的 Windows 价值没有问题（真实调用 `imagehlp` / `kernel32`），卡点纯粹是区分度。

### 3.3 wlogseg-218：静态门禁全部通过

- 14 个原生 job 齐全（Oracle 3 + NOP 3 + Qwen 3 + Opus 3 + GLM 1 + Kimi 1），`task_checksum` 与包一致；
- 区分度走“全模型有效零分平局”例外（Qwen 0/3、Opus 0/3，逐 case 55 vs 55）判定通过；
- 唯一返修原因是 Windows 价值。

---

## 四、必须注意的口径差异

工作区内存在**两份规则不同的自检包副本**，同一题包会得到不同判定：

| | `_reference/windows-harbor-qc`（用户指定） | `_qc_runs/qc-pkg-new/windows-harbor-qc`（2026-10-14 09:29 更新） |
|---|---|---|
| job 数量 | `must contain exactly 14` | `12` 必需（Qwen3+Opus3+Oracle3+NOP3），GLM/Kimi **忽略** |
| `docker_image` | 必需字段（缺失即 error） | **不再必需**（镜像由 Dockerfile 固定 digest） |
| 219 判定 | jobs **FAIL**（12≠14、缺 GLM/Kimi） | jobs **PASS**，仅 gate FAIL |
| 215 / 216 layout | FAIL（无 `docker_image`） | PASS |

两副本的 `SKILL.md` 完全相同，且文档仍写“14 个 Harbor job”，与其自身实现冲突。**建议以哪一版为准需与甲方书面确认。**

另外，本机 **Docker Desktop 的 Windows 容器引擎未运行、且无 harbor CLI**，因此 Oracle/NOP 实跑与十项人工门禁无法在本机完成；按 `windows-harbor-qc` 规则，缺此环节最终结论只能是 `BLOCKED`。本报告的自动部分为**静态门禁 + Windows 价值语义判定**。

---

## 五、建议处置

1. **218**：四题中唯一静态全过的包。向甲方书面确认“移出 Windows 池、按通用编码题归类与计价”。若甲方同意，这是唯一可直接交付的；若甲方坚持 Windows 池，则必须按 REFIT §4 补 Windows 机制并发新版重跑（届时 `task_hash` 变化，旧 job 全部作废）。
2. **219**：若要保留在 Windows 池，需新增能让 Qwen 稳定失败、Opus 通过的独立判据（R11），再整批重跑 12 个 job。
3. **215 / 216**：按顺序做——冻结包 → 从 `verifier/tests/` 复制平台投放副本到 `tests/` → 按 218/219 的归档协议重建 `jobs/`（`cases[]` + `status`、补 `verifier/verifier.log`、控制组用 `ctl-oracle-*` / `ctl-nop-*`）→ 整批重跑（Oracle3+NOP3+Qwen3+Opus3）→ 同步修正飞书字段与目录名版本。**仅按通用编码题池交付，也仍需先解决 job 层与身份门。**
4. **Windows 价值本身**：若要让这三题留在 Windows 池，必须补真实 Windows 机制。REFIT 给的候选（NTFS 稀疏/压缩区间流式纪律、`FILE_SHARE_READ` + `ERROR_SHARING_VIOLATION`、ADS / 重解析点落盘）需先查重，避免与已有题（`wfflab__wreparse-217`、`windows-share-lock`、`windows-ntfs-ads` 等）撞语义。
5. **索引与登记**：`_index/tasks_index.csv` 与实物不符（219 记 1.1.0 / required 27，实物 1.4.0 / 43；215 记 16，实物 20），建议按实物回填。

---

## 六、附：本次实测产物

- 静态门禁双口径结果：`harbor-windows/_qc_runs/wff-4pkg-static-qc/static-reference.json`、`static-pkgnew.json`
- 复跑脚本：`harbor-windows/_qc_runs/wff-4pkg-static-qc/run_static_qc.py`
- 历史四题复核（含逐 testcase 明细）：`harbor-windows/_qc_runs/qc-verify-4tasks/VERIFY-4TASKS.md`
- 飞书返修原因快照：`harbor-windows/_qc_runs/windows-mechanism-rework/返修原因-三条-20261014.md`
