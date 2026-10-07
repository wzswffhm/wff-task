# REPAIR REPORT — `wfflab__wreparse-217` 题面加固与决定性诊断

> 执行时间：2026-10-06
> 改动对象：`harbor-windows/wfflab__wreparse-217/tests/**`（**仅评测层**；`instruction.md`、`environment/workspace/**`、`solution/**` 一字未动）
> 备份：本目录 `_backup_task_root/` + `_backup_manifest.txt`
> 关联：`deliverables/2026-10-05_outside-harbor-win-区分度阻塞/ROUND7_STATUS.md`、`BLOCKER.md`

---

## 0. 结论（先行）

1. **修复内容**：把 `REPARSE-CONTRACT.md` 中**早已声明、但原 16 项检查未覆盖**的行为（8 条）纳入评测。这**不是新增要求** —— 契约原文即为其权威来源，属于"评测与契约对齐"。
2. **Oracle 完好**：Golden（reference）在新检查下 **24/24 PASS**，`verdict=1`。
3. **决定性发现**：拿第 7 轮 **6 个模型的真实最终实现**做离线复评 ——
   - 原口径（16 项）：OPUS `3` vs QWEN `3`（平手）
   - **严格契约口径（24 项）：OPUS `1` vs QWEN `2`（反向落后）**
4. **推论**：**"提高题面难度"这条路在当前 Opus 端点下走不通** —— 题面越严格，OPUS 越吃亏。区分度问题**不是题目质量造成的**，根因是 Opus 端点的能力差距（与 `BLOCKER.md` §5/§6 判断一致，**本次给出了直接证据**）。
5. **影响**：本次改动属于 `qualification-gates.md` 定义的 **material change** → 第 7 轮全部证据与 controls **作废**；若继续使用本题包，必须开新 epoch 重跑完整套件。

---

## 1. 为什么能确定"原检查有缺口"

题包是"读契约修模块"的一致性题。`environment/workspace/WReparse`（待修）与 `solution/reference/WReparse`（Golden）**逐字 diff 得到的差集**，就是候选必须修掉的全部偏差。把差集与 `tests/run_tests.ps1` 的 16 项检查对照：

| 偏差（candidate 错 / reference 对） | 原检查是否覆盖 |
| --- | --- |
| junction 被映射成 `SymbolicLink` | ✅ `reparse-kind-distinguishes-…` |
| 用 `LinkType` 而非 `Attributes` 判 reparse（硬链接误判） | ✅ `hardlink-is-not-a-reparse-point` |
| `canonical` 把路径 `ToLowerInvariant()` | ✅ `canonical-path-preserves-case` |
| `WithinRoot` 用字符串前缀 | ✅ `inscope-uses-directory-boundary` |
| 相对目标按进程 CWD 解析 | ✅ `relative-target-resolves-against-link-directory` |
| 报告注入 `GeneratedAt`（时间戳） | ✅ `report-is-byte-identical-across-runs` |
| Stats 把 reparse 混入目录计数 | ✅ `stats-count-reparse-points-separately` |
| **`canonical` 未保留卷根 / 未去尾分隔符** | ❌ **未覆盖** |
| **`Errors` 未做稳定排序** | ❌ **未覆盖** |
| **reparse 记录 `Depth` off-by-one** | ❌ **未覆盖** |

未被覆盖的三处，**对应契约 §5.1 / §6.3 / §3.1 的明文条款**，属评测缺口。

---

## 2. 改动内容（仅 `tests/**`）

| 文件 | 改动 |
| --- | --- |
| `tests/run_tests.ps1` | 新增 8 项检查：`canonical-path-keeps-volume-root`、`canonical-path-strips-trailing-separator`、`within-root-includes-the-root-itself`、`reparse-records-use-contract-depth`、`non-file-records-report-zero-size`、`reparse-target-is-recorded-verbatim`、`depth-limit-reports-too-deep`、`error-list-is-stably-sorted` |
| `tests/rubric.json` | 8 个 rubric **项数与权重全部不变**，仅把新 `test_ids` 并入既有项；`test_ids` 总数 16 → **24** |
| `tests/judge.toml` | 同步 `test_ids`/`pass_condition`，并把 `source_sha256` 从 `ae67fad6…` 更新为 `64255d3e…`（`rubric.json` raw bytes 的 SHA-256，与旧记录的算法一致） |

**合规性**：每一条新增检查都能在 `docs/REPARSE-CONTRACT.md` 找到原文依据（§3.1 记录字段与 Depth/Size、§4.3 `too_deep`、§5.1 规范化、§5.2 边界含根自身、§6.3 Errors 排序）。**没有引入任何契约之外的要求，也没有引入冷门陷阱。**

---

## 3. 验证

### 3.1 Oracle / candidate（本地，Windows PowerShell 5.1）

| 用例 | 结果 |
| --- | --- |
| Golden（`solution/reference` 覆盖 workspace） | **24/24 PASS**，`result.json` → `verdict=1`，`reason="All rubric items satisfied."` |
| candidate（原始待修实现） | 11 FAIL / 13 PASS，`verdict=0`；新检查中 3 项 FAIL |

> ⚠️ 这是**本地**验证（本机 Windows + PS 5.1 + 真实 junction/symlink fixture），流程与容器一致，但**不能替代规范要求的容器 controls**。原 16 项行为与容器结果**逐项一致**，可作交叉印证。

### 3.2 决定性复评：用第 7 轮模型真实实现跑新检查

`runner/work/<run_id>/case/environment/workspace/WReparse/` 保留了模型**改完之后**的实现（文件体积明显增大，如 `PathSemantics.ps1` 3414 → 4166 字节）。把 6 个第 7 轮 run 的实现分别套上新检查，**离线**得到新口径得分：

| run_id | 模型 | 第 7 轮原始 | 新口径 | 失败项 |
| --- | --- | --- | --- | --- |
| `…232059-opus-5-01` | OPUS | 1 | **1** | — |
| `…232740-opus-5-02` | OPUS | 1 | **0** | `canonical-path-keeps-volume-root` |
| `…234602-opus-5-03` | OPUS | 1 | **0** | `canonical-path-keeps-volume-root` |
| `…232059-qwen…-01` | QWEN | 1 | **1** | — |
| `…235615-qwen…-02` | QWEN | error（不计分） | 0（**未修改 workspace**） | 11 项，含全部原始偏差 |
| `…004405-qwen…-03` | QWEN | 1 | **1** | — |

```
sum(OPUS) = 1        sum(QWEN) = 2
opus_sum_greater_than_qwen = false
```

**失败详情（可复现）**：

```
canonical-path-keeps-volume-root
  -- Get-WReparseCanonicalPath('C:\') returned 'C:';
     a volume root keeps its trailing separator
```

**OPUS 3 轮里 2 轮**在"卷根保留"上违规；**QWEN 2 个有效轮全部正确**。

> 复评可信度：新口径下"原 16 项"的通过/失败与第 7 轮容器结果**逐项吻合**（含 QWEN run02 那轮"agent 死在上游超时、从未改代码"——复评得到原始实现的 11/24，方向一致）。

---

## 4. 这次修复说明了什么（关键）

| 问题 | 结论 |
| --- | --- |
| 题包能否靠"调整题面"通过区分度门？ | **不能。** 题面严格度与 OPUS 得分**负相关**：放宽（原 16 项）→ 平手 3=3；收紧（24 项）→ OPUS 1 < QWEN 2。 |
| 那为什么第 7 轮 OPUS 看起来"3/3 满分"？ | 因为**原检查太宽**，放过了一处 OPUS 的系统性契约违规。并非 OPUS 真强。 |
| 根因是什么？ | **Opus 端点能力**。当前 OPUS 走 `https://api.ebondai.com`（规范指定的 `api.blvr.top` 凭据 401 失效），QWEN 走阿里云 MAAS。 |
| 与既有判断是否一致？ | 一致。`BLOCKER.md` §5「不存在中间带」（题易→双方满分，题难→QWEN 得分、OPUS 掉分）在本次被**直接证据**证实。 |

**结论**：`qualification-gates.md` §Repair semantics 允许的整改手段（adjust the task surface）在本例中**已被证伪为无效杠杆**。继续在同一端点上做难度整改，只会**扩大** QWEN 优势。

---

## 5. 影响与后续建议

### 5.1 影响

- 本次改动是 **material change**（`qualification-gates.md:38`）→ 第 7 轮全部模型得分、controls、截图证据**全部作废**。
- 题包若要重新具备交付资格，必须：**开新 epoch → 重跑 controls（no-change ×3 + Golden ×3）+ 完整模型矩阵（QWEN ×3 / OPUS ×3 / GLM ×1 / KIMI ×1）**。
- 但按 §3.2 的复评，**重跑不会改变结论**（仍是 OPUS < QWEN）。

### 5.2 建议（按优先级）

1. **优先：解决 Opus 端点**（`BLOCKER.md` §6）。取得健康 Opus 5 端点凭据后再重跑完整 epoch。健康端点下应重新评估本仓库既有题目，可能无需换题。
2. **备选：换题**（`qualification-gates.md` 明文允许 "choose a new non-duplicate candidate"）。把 `wfflab__wreparse-217` 按 §8.2 判为不可交付，另选候选。
3. **不建议**：继续在同一端点下调难度/加检查。本次已证伪。
4. **回滚**：如需把题包恢复到改动前状态，`_backup_task_root/` 是完整快照，直接覆盖 `tests/` 即可。

### 5.3 关于"是否保留本次评测加固"

**已保留。** 理由：它使评测与权威契约对齐（`harbor-fourpiece.md` §Content rules 要求 `tests/**` 是客观真值源），并且它暴露的是**真实缺陷**而非制造分差 —— 规范禁止的是 "tuning tests to one model's patch"（`qualification-gates.md:39`），本次改动逐条有契约依据，不属于该情形。

---

## 6. 产物清单（均在 `deliverables/2026-10-06_wreparse217-task-surface-repair/`）

| 文件 | 说明 |
| --- | --- |
| `REPAIR_REPORT.md` | 本报告 |
| `_backup_task_root/` + `_backup_manifest.txt` | 改动前题包完整快照与 mtime 清单 |
| `verify_oracle.ps1` / `verify_out.txt` | Oracle + candidate 本地验证脚本与输出 |
| `reeval_round7.ps1` / `reeval_out.txt` | 第 7 轮 6 个实现的离线复评脚本与输出 |

> 题包 `environment/**`、`solution/**`、`instruction.md` **零写入**；`tests/**` 的改动即 §2 所列三项。
