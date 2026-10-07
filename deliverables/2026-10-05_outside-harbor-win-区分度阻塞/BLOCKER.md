# Outside Harbor Windows 题包 `wfflab__wreparse-217` —— 区分度门阻塞报告

> 日期：2026-10-05　工作区：`deliverables/2026-10-04_outside-harbor-win/`　题包：`harbor-windows/wfflab__wreparse-217`
> 依据：`generate-win/references/qualification-gates.md`、`skills/harbor-windows/references/08-model-validation.md`

## 0. 结论（先行）

**题包本体已全部就绪并通过所有非模型门禁；唯一未过的是模型区分度门（硬门槛 8.2）。**

该门在本机**当前可用的 Opus 5 端点下不可满足**，且**与题目质量无关**，根因是两条叠加：

1. **QWEN 已达满分天花板**：`qwen3.8-max-0902` 在 80 / 72 / 40 轮三种配置、共 5 次运行中**全部得到 1.0**，即 `sum(QWEN) = 3`（理论最大值）。门禁要求 `sum(OPUS) > sum(QWEN)`，因此**除非让 QWEN 至少失手一次，否则任何 Opus 都无法通过**——满分只会得到"平手"，而"平手"按判据同样是 FAIL。
2. **唯一可用的 Opus 5 端点能力低于 QWEN**：指定端点 `https://api.blvr.top` 凭据失效（`401 Invalid token`），实际只能走 `https://api.ebondai.com`。该端点在同一题族上的逐检查错误率是 QWEN 的约 **16 倍**，且**"加大难度"只会把"平手"变成"Qwen 胜"**（详见 §5 历史诊断）。

**需要的外部动作：提供一个健康的 Opus 5 端点凭据**（§6）。

---

## 1. 当前状态

| 项 | 结果 | 证据 |
| --- | --- | --- |
| 需求符合性（18 项必需路径） | ✅ `valid: true`，0 error / 0 warning | `evidence/requirement_conformance.json` |
| NOP / no-change ×3 | ✅ `0 / 0 / 0`，全部 `status=VALID` | `evidence/model_matrix_summary.json` |
| Oracle / Golden ×3 | ✅ `1 / 1 / 1`，全部 `status=VALID` | 同上 |
| 模型矩阵完整性 | ⚠️ 计数完整（QWEN 3 / OPUS 3 / GLM 1 / KIMI 1），但**跨配置混采**，不构成同一 epoch 的合法集合 | 同上 |
| **区分度门 8.2** | ❌ `sum(OPUS)=2` 不大于 `sum(QWEN)=3` | 同上 |
| 打包四件套 / 证据截图 / 飞书写回 | ⛔ 未执行（门禁未过，按 skill 不得上传或声称完成） | — |

对照组为 **2026-10-05 14:28–14:30 本机复跑**，非历史数据。

---

## 2. 门禁原文

`generate-win/references/qualification-gates.md`：

```text
sum(OPUS scores) > sum(QWEN scores)
```

配套判据（`skills/harbor-windows/references/08-model-validation.md`）：

- 条件 1：`Opus5.model_score_sum > Qwen3.8-Max-0902.model_score_sum`
- 条件 2：两者 `model_score_sum = 0` 且 `Opus5.testcase_pass_sum > Qwen3.8-Max-0902.testcase_pass_sum`
- **不接受**："两者正式分和**相同且不全为 0**"

> 注：本题二值判分的每轮上限为 `1.0`，3 轮 `model_score_sum` 上限即 `3.0`。

---

## 3. 证据 A：QWEN 的满分天花板

`evidence/all_runs_table.txt` 中所有 `mode=candidate` 且 `alias=QWEN` 的有效运行：

| 运行 ID | 配置文件 | 结果 | 轮次 | 结束时状态 |
| --- | --- | --- | --- | --- |
| `20261005T101421-…qwen…-01` | 80 轮 / 全 `environment` / 含 `run_shell` | **1.0** | 80 | `max_turns` |
| `20261005T110502-…qwen…-01` | 80 轮 / 仅 workspace / 含 `run_shell` | **1.0** | 80 | `max_turns` |
| `20261005T120955-…qwen…-01` | 72 轮 / 仅 workspace / 含 `run_shell` | **1.0** | 72 | `max_turns` |
| `20261005T132138-…qwen…-01` | 40 轮 / 仅 workspace / 含 `run_shell` | **1.0** | 40 | `max_turns` |

**4/4 满分，且对轮次预算不敏感。** 逐检查维度 16/16 全过。

`evidence/tool_sequence.txt` 给出 QWEN 的通过方式：`read_file×8 / list_dir×4 / run_shell×30 / write_file×6` —— 它**自建夹具、反复执行、靠反馈迭代**收敛，这正是它在本题上的优势来源。

**推论**：`sum(QWEN) = 3` 是上限值，门禁的不等式退化为 `sum(OPUS) > 3`，**无解**。唯一出路是让 QWEN 失手，见 §5。

---

## 4. 证据 B：OPUS 无法超过 QWEN

`evidence/model_matrix_summary.json` 的确定性选样（仅展示，跨配置混采）：

| 模型 | 选定运行（轮次） | 分数 | `model_score_sum` |
| --- | --- | --- | --- |
| QWEN | 80 / 72 / 40 | `[1, 1, 1]` | **3** |
| OPUS | 40 / 40 / 40 | `[1, 0, 1]` | **2** |
| GLM | 40 | `[0]` | 0 |
| KIMI | 6 | `[0]` | 0 |

判定：`opus_sum_greater_than_qwen = false` → `qualified = false`。

**OPUS 的三次 0 分不是"能力不足"，而是被轮次预算截断**（`evidence/failed_checks_diag.txt`）：

- `20261005T134359-…opus…-02`（40 轮）：`agent.status=max_turns`，**13/16 检查同时报
  `Get-WReparseReport threw: The variable '$_' cannot be retrieved`** —— 该运行在第 40 轮时**仍在阅读
  `Walker.ps1` 并推敲 `-MaxDepth` 边界语义**，文件停在重构中间态。
- GLM（40 轮）：`agent.status=max_turns`，多条检查报 `record … is missing` —— 同样未写完。

即：**收紧轮次预算惩罚的是 OPUS 而不是 QWEN**。这与"QWEN 对预算不敏感"（§3）叠加，使"调预算"这一杠杆方向相反、不可用。

---

## 5. 历史诊断（同一结论，16 题样本）

`deliverables/2026-10-04_harbor-windows-区分度诊断/DIAGNOSIS.md` 已对 `harbor-windows/` 全部 16 道题做过定量诊断：

| 模型 | 检查执行数 | 失败数 | 逐检查错误率 | 出现失败的题 |
| --- | ---: | ---: | ---: | --- |
| Qwen3.8-Max-0902 | 730 | 3 | **0.41%** | 2 / 16 |
| Opus 5（ebondai） | 396 | 26 | **6.57%** | 4 / 16 |

- 逐 testcase 交叉比对，寻找"Qwen FAIL 且 Opus 全 PASS"的语义点：**共 0 个**；反向大量存在。
- 历史准入：`wacl-203 / wencoding-206 / wreserved-201 / wtask-216` 双方均 3.0 → 同分不通过；
  `winstall-210`（3.0 vs 2.0）、`wproc-209`（1.0 vs 0.0）、`wsync-142`（1.0 vs 0.0）、`wfmt-215`（2.0 vs 0.0）→ Qwen 胜。
- 结论：**不存在中间带** —— 题目"易"→ 双方 3.0 平手；题目"难"→ Qwen 得 1–2 分而 Opus 直接 0 分。

`wsync-142` 已按规范 8.2 判为**不可交付**并被 `wproc-209` 替换（`harbor-windows/_index/known_issues.md` K13）。

---

## 6. 需要的外部动作

**提供一个健康的 Opus 5 端点凭据**（`api_key`），写入 `runner/.env.local` 的 `OPUS_*` 四项
（或 `~/.workbuddy/harbor-windows.env` 的 `HARBOR_WINDOWS_BLVR_KEY`）：

| 端点 | 探针结果（2026-10-05 14:2x） |
| --- | --- |
| `https://api.blvr.top/v1/messages`（规范指定） | ❌ `401 Invalid token (type: new_api_error)` |
| `https://api.ebondai.com/v1/messages`（当前使用） | ✅ 可达，`claude-opus-5` 返回 `PONG`，但题族能力低于 QWEN |

**验收提示**：健康端点的 Opus 5 在本题族上的逐检查错误率应显著低于 6.57%，理想接近 QWEN 的
0.41% 量级，并在若干题上**超过** QWEN。若重跑后仍复现 6.57% 量级，说明该中转提供的并非
真正的 Opus 5 级模型。

**收到凭据后的动作**：在同一端点重跑 `QWEN ×3` 与 `OPUS ×3`，重新判分与准入；若 Opus 恢复正常
水准，本仓既有题目可直接复用，无需重新出题。

> 附带说明：即便换到健康端点，**本题仍需同时提高难度**，因为 QWEN 已 4/4 满分（§3）——
> 仅换端点只会得到"双方 3.0 平手"，仍是 FAIL。提高难度属"完整返修周期"（规范上限 3 次），
> 需要端点到手后才能测得是否奏效，故不在本次执行。

---

## 7. 本轮已排除的假设（实测）

| 假设 | 实验 | 结果 |
| --- | --- | --- |
| 收紧轮次预算可形成能力区分 | 40 轮 | ❌ 反而截断 OPUS（`max_turns` + 残缺文件），QWEN 仍满分 |
| 剥夺执行反馈（移除 `run_shell`）可削弱 QWEN | 移除 `run_shell` | ❌ 方向错误：两个模型都依赖 `run_shell` 自测（QWEN 30 次 / OPUS 26 次），移除后双方同时受损，且 OPUS 写得更慢更易被截断 |
| 暴露完整 `environment/` 会降低难度 | 80 轮全暴露 vs 仅 workspace | ➖ 无区分效果（QWEN 均满分） |
| 模型别名/视图契约写错导致误判 | 修 `model_alias`、candidate 视图只给 `instruction.md` + `workspace/**` | ✅ 已修，非阻塞因素 |
| 关键根因是端点 | 双端点探针 | ✅ 确认为根因之一（§6） |

---

## 8. 复现命令

```powershell
$py  = "C:\Users\Administrator\.workbuddy\binaries\python\versions\3.13.12\python.exe"
$sk  = "C:\Users\Administrator\Desktop\generate-win"
$run = "C:\Users\Administrator\Desktop\wff-task\deliverables\2026-10-04_outside-harbor-win\runner"

# 对照组（本报告 §1 的数据来源）
powershell -NoProfile -File "$run\run.ps1" -Task wfflab__wreparse-217 -Mode no-change -Runs 3 -WorkspaceRoot $run -KeepWork
powershell -NoProfile -File "$run\run.ps1" -Task wfflab__wreparse-217 -Mode golden    -Runs 3 -WorkspaceRoot $run -KeepWork

# 汇总与准入判定
& $py "$sk\scripts\summarize_model_runs.py" --workspace-root $run --task-id wfflab__wreparse-217 --control-runs 3

# 结构符合性
& $py "$sk\scripts\validate_requirement_conformance.py" --task-path "C:\Users\Administrator\Desktop\wff-task\harbor-windows\wfflab__wreparse-217"
```

> 注意：`run.ps1` 若不传 `-KeepWork`，工作目录（500+ 文件）清理由安全钩子拦截，
> 会以 `SAFE_DELETE_BULK_CONFIRM_REQUIRED` 中断多轮循环，只跑第 1 轮。

---

## 9. 2026-10-06 复核：决定性证据（题面加固 + 离线复评）

本报告 §5 的核心判断「不存在中间带 —— 题易则双方满分、题难则 Qwen 得分而 Opus 掉分」在本次被**直接证据**证实。详细过程见
`deliverables/2026-10-06_wreparse217-task-surface-repair/REPAIR_REPORT.md`。

**做法**：把 `REPARSE-CONTRACT.md` 中**已声明但原 16 项检查未覆盖**的行为（`canonical` 卷根保留、尾分隔符、reparse 记录 Depth、Errors 稳定排序等 8 条）纳入评测，`rubric`/`judge` 同步（项数与权重不变，`test_ids` 16 → 24）。**未改 `instruction.md` / `environment/**` / `solution/**`**。

**结果**：

| 口径 | sum(OPUS) | sum(QWEN) | 门禁 |
| --- | --- | --- | --- |
| 原 16 项（第 7 轮容器实跑） | 3 | 3 | ❌ 平手 |
| **严格契约 24 项（第 7 轮实现离线复评）** | **1** | **2** | ❌ **反向落后** |

失败点：`Get-WReparseCanonicalPath('C:\')` —— **OPUS 3 轮中 2 轮返回 `'C:'`**（违反契约 §5.1「卷根保留其形态」），QWEN 2 个有效轮全对。

**三点结论**：

1. 第 7 轮 OPUS「3/3 满分」是**假象** —— 原检查太宽，放过了一处系统性契约违规。
2. **提高题面难度不是有效杠杆**：题面越严格，OPUS 相对得分越低。继续整改只会**扩大** Qwen 优势。
3. 根因仍是 **Opus 端点**（当前走 `api.ebondai.com`；规范指定的 `api.blvr.top` 凭据 401）。§6 的外部动作依然成立，且优先级最高。

**副产物**：`runner/work/<run_id>/case/environment/workspace/WReparse/` 保留了各轮模型**改完之后**的实现，可离线复评任意轮次 —— 后续判定可先做离线预判，再决定是否值得付重跑成本。

**影响**：本次评测加固属 material change → 第 7 轮证据与 controls 作废；题包若要重新具备交付资格须开新 epoch 重跑全套（但按上表，重跑不会改变结论）。
