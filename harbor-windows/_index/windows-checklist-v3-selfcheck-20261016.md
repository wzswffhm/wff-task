# 飞书已有题包一致性核对 +《Windows 评测待修复清单 v3》自查（2026-10-16）

> **检查性质：只读。** 未修改任何题包文件、未改动飞书记录、未重跑容器、未安装依赖。
> **自查对象（用户指定）**：`harbor-windows/` 下 6 个题包 —— `wfflab__wsparse-215`、`wfflab__wvas-216`、
> `wfflab__wspawn-218`、`wfflab__wcancel-219`、`wfflab__wciocp-220`、`wfflab__wtoken-221`。
> **检查深度（用户指定）**：静态核对 —— 读题面 / 测试源码 / verifier / 包内记录与 jobs，逐项判定清单问题是否成立。

---

## 一、口径与来源

| 项 | 取值 |
|---|---|
| 飞书来源 | base `EsJebL8JJaf7g4sIbItcnMFgnvg` / table `tblRDxcGkblflMBA`（Windows 作业表） |
| 拉取时刻 | 2026-10-16 15:07（快照 151 条记录；标注员 = `wff` 的 5 条） |
| 判定字段 | 只认交付附件字段 **`作业压缩包`**（README 铁律四第 6 条：`分数截图`/`oracle-nop截图`/`返修原因` 属过程证据，不参与一致性判定） |
| 比对方法 | `base +record-download-attachment` 下载 → 核对 ZIP 唯一根目录名 = 附件名去 `.zip` → 解压内容与本地目录**逐文件 SHA256** |
| 清单归并 | 清单 v3 的 28 项（zq-id 3/30/31/32/48/49/95/96/97）归并为 **C1–C18** 通用检查项，见 `_qc_runs/feishu-consistency-20261016-r2/checklist-v3.md` |
| 原始数据 | `_qc_runs/feishu-consistency-20261016-r2/`（快照、ZIP、比对脚本与 JSON、jobs 汇总、身份校验、各包 md） |

---

## 二、飞书已有题包 vs 本地：**5/5 完全一致**

| 飞书交付附件 | ZIP 文件数 | 本地文件数 | ZIP 独有 | 本地独有 | 同名异内容 | 结论 |
|---|---|---|---|---|---|---|
| `wfflab__wsparse-215-v1.0.0-delivery.zip` | 273 | 273 | 0 | 0 | 0 | **一致** |
| `wfflab__wvas-216-v1.0.0-delivery.zip` | 259 | 259 | 0 | 0 | 0 | **一致** |
| `wfflab__wspawn-218-v1.0.0-delivery.zip` | 261 | 261 | 0 | 0 | 0 | **一致** |
| `wfflab__wcancel-219-v1.0.0-delivery.zip` | 260 | 260 | 0 | 0 | 0 | **一致** |
| `wfflab__wciocp-220-v1.0.0-delivery.zip` | 258 | 258 | 0 | 0 | 0 | **一致** |
| `wfflab__wtoken-221` | — | — | — | — | — | **飞书无记录（未提交）** |

本次下载副本 SHA256（与 10-16 上午 10:22 那次重拉的副本对比）：

| 附件 | ZIP SHA256（本次） | 与 10:22 副本 |
|---|---|---|
| wsparse-215 | `a83f3622468897fada1b54507729c9d9a96b5f285a431b187f1b203beba787ef` | 相同 |
| wvas-216 | `edea432cacf6b3f6701f6182a1de18261795b0c98214ce30565d6da5c3efe446` | 相同 |
| wspawn-218 | `f02055cbddfc8b12be2dd393cea5a0cb40a07b57008b4080c93000a152e149f4` | **已更新**（旧版 `68c34d4c…`） |
| wcancel-219 | `0ebe199eeaef5761e8d3267611847930d6b08a1676b2a0ffded6a97c863a29e4` | 相同 |
| wciocp-220 | `d637d595533368b3679243cf65cf4b5a73da6d9fd4b93b39f66331156a4bd4d9` | 相同 |

结论要点：

1. **5 个飞书交付附件与本地镜像逐字节一致**（0 多 / 0 少 / 0 同名异内容），符合 README 铁律四。
2. **218 的飞书附件已于 2026-10-16 13:10 换成完成镜像改造的新版**（`f02055cb…`，54,511,970 B），本地与之逐字节一致；
   `jobs/` 也已按新身份重跑（见 4.1 对比）。
3. **216 此前"本地多 2 个文件"的问题已消失**：10-16 10:22 重拉时把 `REFIT-2026-10-14.md`、`verifier/WINDOWS_VALUE.md`
   移出题包目录（备份在 `_qc_runs/feishu-repull-20261016/preserved-from-local/`），因此现与飞书一致 ——
   但这次移除改变了包身份，直接导致 216 的 `jobs/` 与当前包对不上（见 4.1）。
4. **221 尚未在飞书建记录**，本地也缺整套 `jobs/`（模型轮仍在跑），无法比对、也无法交付。

飞书侧状态变化（重要）：5 条记录状态已从「待返修」变为「**返修待质检**」，`返修原因` 已被甲方替换为
**【2026-10-16 本轮质检】** 的意见（不再是 10-14 那条 Server Core 镜像意见）。原文见
`_qc_runs/feishu-consistency-20261016-r2/feishu-wff-reasons.md`。

---

## 三、清单 v3 通用检查项自查结果

### 3.1 汇总矩阵（6 包 × C1–C18）

| 检查项 | 215 | 216 | 218 | 219 | 220 | 221 |
|---|---|---|---|---|---|---|
| C1 测试与私有实现耦合 | PASS | PASS | PASS | PASS | PASS | PASS |
| C2 未公开/题面外判分条件 | PASS | **FAIL** | PASS | PASS | **FAIL** | **FAIL** |
| C3 断言缺口（可绕过/自证） | 待确认 | **FAIL** | **FAIL** | **FAIL** | PASS | PASS |
| C4 覆盖不足（题面 vs 用例） | **FAIL** | **FAIL** | **FAIL** | **FAIL** | **FAIL** | **FAIL** |
| C5 F2P 在空跑基线已通过 | PASS | PASS | **FAIL** | PASS | PASS | N/A（无 jobs） |
| C6 对照齐全 + 身份绑定 | PASS | **FAIL** | PASS | PASS | PASS（evidence 空） | N/A |
| C7 评分入口/规则一致性 | PASS | **FAIL** | PASS | PASS | PASS | PASS |
| C8 基建故障被当成 0 分 | **FAIL** | **FAIL** | **FAIL** | **FAIL** | **FAIL** | **FAIL** |
| C9 模型区分度（Opus > Qwen） | PASS 3>1 | PASS 3>1 | PASS 3>2 | PASS 3>1 | PASS 2>0 | N/A |
| C10 对照模型身份 | PASS | PASS | PASS | PASS | PASS | N/A |
| C11 有效样本完整性 | 无无效槽位 | 空名单 | 无 | 1 例已解决 | 无 | N/A |
| C12 题面混入无关内容 | PASS | PASS | PASS | PASS | PASS | PASS |
| C13 题面描述不准确 | **FAIL** | **FAIL** | 待确认 | **FAIL** | **FAIL** | PASS |
| C14 题面范围 > 测试覆盖 | PASS | **FAIL** | **FAIL** | PASS | **FAIL** | **FAIL** |
| C15 跨平台要求缺回归 | N/A | N/A | N/A | N/A | N/A | N/A |
| C16 失败证据完整性 | **FAIL** | PASS | **FAIL** | PASS | PASS | **FAIL** |
| C17 答案污染/联网 | 待确认¹ | PASS | 待确认¹ | PASS | 待确认¹ | 待确认¹ |
| C18 镜像 OS 版本 | **部分**² | **部分**² | **部分**² | **部分**² | **部分**² | **部分**² |

- ¹ C17「待确认」= 包内无运行期禁网声明（`task.toml`/`adapter.toml` 均无 network 字段），构建期均为离线 vendored
  wheelhouse，且模型轨迹里对 `curl/git clone/pip/WebFetch` 的检索**零命中**、无上游源码或补丁痕迹。
  即：**未发现污染证据**，但"运行期是否禁网"由平台侧决定，静态不可核。
- ² C18 见 4.7：`environment/Dockerfile` 的 `FROM` 已全部是完整 `mcr.microsoft.com/windows/server:ltsc2022`
  （build 20348，非 Server Core / Nano Server），但 `environment/adapter.toml` 与
  `environment/agent_visible_paths.json` 里仍写着旧的 `servercore:ltsc2022@sha256:76cf422c…`（6 包全中）。

### 3.2 清单 28 项 → 本批结论对照

| 清单原项 | 归并检查项 | 本批（我们的 6 个包）结论 |
|---|---|---|
| 3-1 测试耦合私有函数名 | C1 | 6 包全部 PASS：隐藏套件只 import 题面公开入口，无私有符号引用 |
| 3-2 题面要求兼容 Unix 但缺 Unix 回归 | C15 | 6 包全部 N/A：题面明确把其他平台排除在验收外，且有"非 Windows → skip → INVALID"保护 |
| 3-3 / 32-3 / 48-3 / 49-3 区分度全 0 | C9 | 5 个有 jobs 的包**全部满足 Opus > Qwen**（3>1、3>1、3>2、3>1、2>0），无"双方零分/同分"情形 |
| 30-1 / 95-1 / 96-2 未公开的判分条件 | C2 | 216、220、221 命中同类问题（详见 4.5、4.9） |
| 30-2 / 32-2 / 48-2 / 49-2 / 95-3 覆盖不足 | C4 | 6 包全部存在题面条款无用例（详见 4.6） |
| 31-1 失败只剩布尔值 | C16 | 215/218/221 命中；216/219/220 有 `test-stdout.txt` 可复核，属"部分满足" |
| 31-2 / 32-1 断言缺口可绕过 | C3 | 216、218、219 命中（详见 4.4、4.8） |
| 48-1 F2P 在空跑基线已通过 | C5 | **218 命中**：2 个 F2P 在三次 NOP 全部 PASS（详见 4.3） |
| 49-1 旧 OS 镜像 | C18 | Dockerfile 已合规；但 adapter/agent 两处仍是 Server Core（详见 4.7） |
| 49-4 题面混入无关模板文字 | C12 | 6 包全部 PASS |
| 96-1 模型联网取上游答案 | C17 | 未发现污染证据；运行期禁网无包内声明 |
| 96-3 两个评分入口规则不同 | C7 | 216 存在"加权 rubric 声明 vs 二值实现"口径不一致；其余入口唯一且规则一致 |
| 96-4 题面描述不准确 | C13 | 215、216、219、220 命中；218 待确认 |
| 97-1 缺 golden / 空跑对照 | C6 | 5 包 `jobs/` 对照齐全（oracle×3=1、nop×3=0、全 VALID）；**216 身份不匹配**（详见 4.1）；`verifier/evidence/` 只有 215 存了 golden/no_change 文件，219/220 为空目录、216/218/221 无该目录 |
| 97-2 题面范围大于测试覆盖 | C14 | 216、218、220、221 命中 |
| 97-3 对照模型不是 Opus5 | C10 | 5 包均为 `claude-opus-5`（`https://4router.net`），符合要求 |
| 97-4 异常运行未形成有效评分 | C11 | 219 记录 1 个 provider-quota 无效槽位并已重跑归一（`invalid-slots.json` 完整留痕）；无静默剔除 |

### 3.3 各包明细报告

- [wsparse-215](_qc_runs/feishu-consistency-20261016-r2/pkgs/wsparse-215.md)
- [wvas-216](_qc_runs/feishu-consistency-20261016-r2/pkgs/wvas-216.md)
- [wspawn-218](_qc_runs/feishu-consistency-20261016-r2/pkgs/wspawn-218.md)
- [wcancel-219](_qc_runs/feishu-consistency-20261016-r2/pkgs/wcancel-219.md)
- [wciocp-220](_qc_runs/feishu-consistency-20261016-r2/pkgs/wciocp-220.md)
- [wtoken-221](_qc_runs/feishu-consistency-20261016-r2/pkgs/wtoken-221.md)

---

## 四、重点问题（按严重度）

### 4.1【硬伤·甲方已点名】216 的 12 份运行记录与当前交付包身份不一致

- 当前包身份（Harbor dirhash）：`80ae0a3d…`；包内 12 个 job 记录的 `task_checksum`：`253161fb…`（12 个全同，均为旧身份）。
- 成因：10-16 10:22 从飞书重拉 216 时，把本地独有的 `REFIT-2026-10-14.md` 与 `verifier/WINDOWS_VALUE.md` 移出，
  包身份随之改变，但 `jobs/` 未按新身份重跑（215/218/219/220 均已核验为"12/12 job 与当前身份一致"）。
- 与甲方 2026-10-16 意见第 1 条完全对应：「现在包里的 Task 校验值和 12 份原始运行记录对不上」。
- 证据：`_qc_runs/feishu-consistency-20261016-r2/identity-check.json`。

### 4.2【硬伤·甲方已点名】C8 —— 基础设施故障被判成候选 0 分（6 包全中）

- 判分链路 `run_tests.ps1 → aggregate_results.ps1 → test.ps1` 的故障语义存在两类反向错误：
  - 215/218/219/220/221：`if ($collected -eq 0) { status = 'FAIL' }`（215 `run_tests.ps1:183-189`，219/220/218 `:177-182`，221 `:183-189`）
    → 套件被改坏、conftest 冲突、解释器 site 异常等**评测侧/环境侧**故障与"候选包无法导入"不可区分，最终产出
    `run_validity=VALID` + `formal_score=0` 并写 reward（`aggregate_results.ps1:111-112`、`test.ps1:64-82`）。
  - 216：`$status = if ($outcome -eq 'passed' -or $outcome -eq 'xpassed') { 'PASS' } else { 'FAIL' }`（`run_tests.ps1:155`）
    → pytest 的 `error` / `skipped`（含 fixture 阶段环境失败，`test_wvas_semantics.py:274-277` 显式 `pytest.fail`）
    一律记候选 FAIL，同样得到 `VALID/0`；它的 `collected==0` 分支反而正确置 INVALID。
- 与甲方意见第 2 条对应，且甲方明确"探针不是完整 Docker 实测" —— 本批 12 轮记录未触发该路径，属静态判定。

### 4.3【硬伤·甲方已点名】C5 —— 218 有 2 个 F2P 在三次空跑基线上已经通过

- `f2p-empty-inherit-leaks-nothing`、`f2p-only-one-of-two-handed-over-pipes-crosses` 在 `ctl-nop-1/2/3` 三次全部 PASS
  （`jobs/ctl-nop-*/verifier/report.json`，NOP 每轮 9/14）。
- 成因（清单 48-1 同类）：这两条用例把泄漏对象的句柄值从未交给子进程，因此观测不到泄漏
  （`tests/test_wspawn_semantics.py:266-286`、`:289-315`）；`handle-handover` 分组实际只靠
  `test_unlisted_handle_does_not_cross_the_boundary` 支撑。
- 与甲方意见第 3 条逐字对应（「原包三次 NOP 和本轮 NOP 均 PASS」）。
- 其余 4 包无此问题：215 nop 10/20、216 8/16、219 7/14、220 10/14，均为「P2P 全过 + F2P 全挂」。

### 4.4【硬伤】C3 —— 关键语义只靠候选自证（216、219 尤重）

- **219**：题面与 `verifier/README.md`、`metadata/windows_mechanism.json` 都声称"以 `GetOverlappedResult` 的
  内核终态（995/996/1168）为准、不采信候选返回值"，但交付套件里**没有任何** `GetOverlappedResult`
  调用（`tests/test_wcancel_semantics.py:58-71` 只声明 CreateNamedPipeW/CreateFileW/WriteFile/CloseHandle），
  终态断言全部取自候选 `wait()` 返回的 `Completion.status`（`:141`、`:171`、`:201`）
  → 一个只在进程内记账、从不调用 `CancelIoEx` 的实现也能满分（假阳性）。
- **216**：区间类断言只比 `max(base)` 与定点覆盖，不比对区间集合，`size` 只受下界约束
  （`tests/test_wvas_semantics.py:296-301`、`:310-317`），可被"少报区间 / 夸大 size"绕过。
- 215 的同类怀疑（两条 F2P 只比候选自报的 `allocated_ranges()`，`:295-312`）因需先知道 fixture 偏移才能盲式谎报，记为待确认。

### 4.5【硬伤】C2 —— 题面外判分条件造成假阴性（216 已实际触发）

- **216（已实际造成失分）**：`f2p-modules-are-deduplicated` 对每条 `path` 直接 `os.path.normcase`
  （`tests/test_wvas_semantics.py:385`），等价断言"不得返回 `path=None`"；题面 `instruction.md:76-77` 却明确
  「路径无法还原的映像仍必须出现，`path` 允许为 `None`」。`jobs/model-qwen-3/verifier/test-stdout.txt:25`
  报 `TypeError: expected str, bytes or os.PathLike object, not NoneType`，该 F2P 因此判 FAIL。
- **220**：4 条门控断言题面无据 —— `request.handle == server`（`test_wciocp_semantics.py:206`）、
  `event.bytes_read == 5`（`:245`）、`event.status == "completed"`（`:246`）、`take()` 返回顺序（`:198-199`）。
- **221**：`integrity_level()` 必须等于套件内置的 7 项小写词表（`test_wtoken_semantics.py:166-174`、`:379`），
  该词表在题面、`README.md`、`docs/NOTES.md`、包 docstring 中均未出现；参考解自己用首字母大写，靠 `.lower()` 才对齐。

### 4.6【硬伤】C4/C14 —— 题面条款无用例（6 包全部存在）

| 包 | 题面明确要求但**完全无用例**的行为 |
|---|---|
| 215 | D 条"非稀疏文件返回覆盖整个长度的一个区间"；F 条 `preallocate`/`sparse_flag` 对目录抛 `unsupported` |
| 216 | B.4 `file_backed_regions` 顺序；C 条清单完整性与 path 校验；D 条 `access-denied`/`unsupported`/`query-failed`；E.3 联网约束 |
| 218 | F 条 `unsupported` 分类；E 条 console/unknown 类型；C 条"不支持须报错"（`:403` 把 kind 放宽为三选一） |
| 219 | F 条底层失败 `kind="os"`；C 条 `bytes_read` 非零的部分完成 |
| 220 | D2"超时不得丢弃**已到达**通知"（`:252-265` 实测的是"先超时后提交"，与**用例名不符**）；F2 close 时 `cancelled` 交付（`cancelled` 在套件中命中 0）；F3b `kind="os"` |
| 221 | E 条"提升类型"（`TokenElevationType` 常量声明后从未使用）；F 条 `kind="os"` |

### 4.7【较硬】C18 —— Dockerfile 已合规，但 adapter / agent 两处镜像声明仍是 Server Core（6 包全中）

| 位置 | 现状 | 判定 |
|---|---|---|
| `environment/Dockerfile` | `FROM mcr.microsoft.com/windows/server:ltsc2022`（完整版，build 20348） | 合规（清单 49-1 关注 OS 版本，此项通过） |
| `task.toml` | `docker_image = ghcr.io/wzswffhm/wfflab-windows:<task>-1.0.0`（成品镜像） | 合规 |
| `environment/adapter.toml:30` | `image = "mcr.microsoft.com/windows/servercore:ltsc2022@sha256:76cf422c…"`（**旧 Server Core**） | **不一致** |
| `environment/agent_visible_paths.json:7` | `agent_runtime.image = "…/windows/servercore:ltsc2022@sha256:76cf422c…"` | **不一致** |

`adapter.toml` 自述是"本地 Outside Harbor runner 的运行时绑定（runner 读它来 build/prepare/drive/clean 容器）"，
`agent_visible_paths.json` 描述 agent 运行镜像。二者仍指向甲方明令禁止的 Server Core；一旦甲方按"**实际运行**基础镜像"
核对（其 10-16 意见原文即"这个包的实际运行基础镜像使用了 Server Core 或 Nano Server"），会再次命中该硬项。
建议：与 Dockerfile 同步改为 `windows/server:ltsc2022`（或明确这两处的消费方与豁免依据），并同步
`_qc_runs/*-build/quality-review.json` 里"docker_image 与 Dockerfile FROM 逐字相同"的旧表述。

### 4.8【较硬】221 的两处自身硬伤（尚未交付，正好赶在提交前修）

1. **`environment/prepare.ps1` 必然失败**：其 `$required` 列出 `wtoken\proc.py`、`wtoken\inherit.py`、`wtoken\kinds.py`
   （`prepare.ps1:19-27`），而 `environment/workspace/wtoken/` 下实际只有
   `errors.py / privileges.py / token.py / _winapi.py / __init__.py`（清单系从 218 的 wspawn 包沿用时未改）。
   prepare 退出 1 → `environment/run.ps1:22-23` 转 `exit 2`（INVALID），走 setup 的链路直接不可评。
2. **`tests/required_testcases.json` 分组与 id 前缀矛盾**：`p2p-inventory-matches-the-token-exactly` 与
   `p2p-visible-smoke-suite-still-passes` 的 `group` 被标成 `F2P`（文件 `:36`、`:80`），
   导致该文件统计为 F2P 10 / P2P 10，而 `rubric.json`、`judge.toml`、`rubric.conditions.json` 均为 F2P 8 / P2P 12。
   该文件虽不参与计分，但会被外部 reviewer 读作 F2P 声明。

### 4.9【中等】C13 —— 题面与实现/基线不符（215、216、219、220；218 待确认）

- **215**：现象 4 把"补设稀疏标志后占用没降"当缺陷（`instruction.md:22`），验收 E 条却要求占用**必须**不降（`:57`）；
  现象 1 称"同一行代码在 Linux 上几乎不占空间"与包内实现（无平台分支、循环写零）矛盾（`:19`）。
- **216**：现象 2"长度是很小的数"与现象 3"保留区间根本不出现"互斥（`instruction.md:20-24`，实测失败信息是 missing）；
  C 节允许 `path=None` 与 E.2 必过冒烟用例 `assert item["path"]`（`test_wvas_basic.py:59`）互斥，参考解只能丢弃映像。
- **219**：`instruction.md:9` 声称"以内核报告的终态为准、不采信候选返回值"，与 4.4 的实现事实不符。
- **220**：`instruction.md:55-56` closed 与 cancelled 两条要求互斥且未给交付路径；现象 5"新的读取也照样能提交"与基线
  （`pool.py:124` 关闭后 submit 已抛 `closed`）不符。
- 218：现象 3/4 与冻结基线实测不符（基线实抛 `kind="os"`、泄漏表现为"全给"而非"句柄错位"），待确认。

### 4.10【中等】C16 —— 失败证据的粒度

`aggregate_results.ps1` 落盘的 `cases[]` 只有 `test_id` + `passed`，pytest 的 `--json-report` 产物写在临时目录并在
`finally` 中删除（如 215 `run_tests.ps1:103`、`:223`）。缓解在于 215/216/219/220/218 的 `jobs/*/verifier/test-stdout.txt`
保留了 `-rA --tb=short` 的断言原文与期望/实际值，失败项**尚可复核**；221 因无 jobs，交付物内没有任何失败实例可核。
建议把逐 case 的期望/实际值或 pytest JSON 一并落盘。

### 4.11【中等】记录与实物不一致

- **216**：`jobs/_index/qualification_summary.json:224-235` 记 `model-qwen-1` reward=1、passed=16，实际
  `jobs/model-qwen-1/verifier/reward.json` = `{"reward":0}`（该 job 14/16）；`model-qwen-3` 通过数记 14，实际 13
  （`assembly_report.json` 记 0，与 reward.json 一致）。修正后 Opus 3 > Qwen 1，**区分度结论不变**。
- **220**：`verifier/README.md:22` 声明套件 SHA256 `67126ff1…`，实测两份副本均为 `23f35618…`；
  `verifier/README.md:28-29`、`solution/README.md:98` 写"F2P 7 / P2P 7"，而 `required_testcases.json`/`rubric.json`/
  `judge.toml`/`rubric.conditions.json` 均为"F2P 4 / P2P 10"。
- **221**：`source.json` 仍写基础镜像是 Server Core；`verifier/oracle/README.md:22` 写 ltsc2022 的 `os.version=10.0.26100`
  与 Dockerfile 的 20348 矛盾。
- **飞书分数字段 vs 包内 jobs**（清单外补充）：218 飞书填 Qwen 1/3，包内重跑后为 2/3；220 飞书填 Qwen 1/3、Opus 3/3，
  包内为 Qwen 0/3、Opus 2/3；215/216 飞书 Qwen 2/3 vs 包内 1/3。字段未随 10-16 的重跑更新。

### 4.12【中等】220 的 P2P 用例稳定性

甲方 2026-10-16 意见第 5 条记录：真实容器第三轮 NOP 的 `p2p-keys-distinguish-handles-on-one-port` 失败
（"两次 take 没有交出第二个句柄的完成项，预期键 0x22，实际为 None"）。包内 12 个 job 中该用例全部 PASS，
说明它是**间歇性**失败：用例本身在测"恰好一次交付"（`test_wciocp_semantics.py:161-181` 的 `by_handle` 字典若两次
`take()` 返回同一请求即得 None）。这与 4.6 中"同包另一条用例名与实现不符"同属 D 组覆盖/稳定性问题。

---

## 五、结论

1. **一致性**：飞书当前已有的 5 个交付附件（215/216/218/219/220）与本地题包**逐字节完全一致**；
   218 已于 10-16 13:10 换为完成镜像改造的新版并完成同身份重跑；221 尚未提交，无法比对。
2. **清单 v3 自查**：28 项中没有一项能在 6 个包上"全体免疫"，最需要动作的是
   **216 的身份不一致（4.1）**、**C8 故障语义（4.2）**、**218 的 F2P 分类（4.3）**、
   **221 的 prepare/分组硬伤（4.8）**，以及**镜像三处声明不一致（4.7）** —— 后两项在提交前修掉成本最低。
3. **与甲方最新意见的一致性**：本次自查独立复现了甲方 2026-10-16 意见中的第 1（216 身份）、
   第 2（基建故障语义）、第 3（218 两条 F2P 基线已过）、第 5（220 的 P2P 稳定性）条，
   说明该意见的静态部分成立；意见中关于"用例未真正验到题面要求"的第 3/4 条，在 215/219/220 上也能找到同类证据（4.4/4.6）。
4. **区分度**：5 个有 jobs 的包全部满足 `Opus > Qwen`（3>1、3>1、3>2、3>1、2>0），对照模型标识为 `claude-opus-5`，
   无"双方零分""对照模型不是 Opus5"这两类清单问题。
5. 本次未做任何修改；以上均为结论陈述与建议。

---

## 六、证据落点

- 本报告：`harbor-windows/_index/windows-checklist-v3-selfcheck-20261016.md`
- 口径与检查表：`_qc_runs/feishu-consistency-20261016-r2/checklist-v3.md`
- 飞书快照与 wff 记录：同目录 `feishu-records.ndjson`、`feishu-records.manifest.json`、`feishu-wff-records.json`、`feishu-wff-reasons.md`
- 一致性比对：同目录 `zip/`（本次下载的 5 个附件）、`feishu-vs-local-r2.json`、`feishu-vs-local-r2.md`、`compare_feishu_local_r2.py`
- jobs 与区分度：同目录 `jobs-summary.json`、`jobs-summary.txt`、`summarize_jobs.py`、`extra_checks.py`
- 包身份校验：同目录 `identity-check.json`、`identity_check.py`（复用甲方 `windows-harbor-qc/scripts/inspect_delivery.py` 的 dirhash 实现）
- required/rubric 一致性：同目录 `check_required_vs_rubric.py`
- 各包逐项结论：同目录 `pkgs/wsparse-215.md`、`wvas-216.md`、`wspawn-218.md`、`wcancel-219.md`、`wciocp-220.md`、`wtoken-221.md`
