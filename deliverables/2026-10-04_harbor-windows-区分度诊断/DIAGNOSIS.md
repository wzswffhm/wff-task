# harbor-windows 8.2 区分度阻塞诊断（2026-10-04）

## 0. 结论

**在当前可用的模型端点配置下，规范 8.2 的区分度准入（`Opus5.model_score_sum > Qwen.model_score_sum`）
无法通过任何出题手段满足。**

根因不在题目，而在 **Opus 5 的端点**：

| 端点 | 状态 |
|---|---|
| `https://api.blvr.top`（SKILL.md 7.1 第 172 行指定的 opus 提供方） | **凭据失效**：`HTTP 401 Invalid token` |
| `https://api.ebondai.com`（当前实际使用） | 可用，但 `claude-opus-5` 在本 benchmark 上的能力**显著低于** Qwen3.8-Max-0902 |

因此 8.2 的解法是**更换/修复 Opus 5 端点凭据**，而不是继续换题。

---

## 1. 定量证据（全部来自本仓 16 道题的实跑记录）

### 1.1 逐检查错误率（per-check error rate）

统计口径：对每道题、每个模型、每一轮 VALID 运行，取 `per_testcase.json` 中所有
`PASS/FAIL` 判定，逐条累计。

| 模型 | 检查执行数 | 失败数 | 逐检查错误率 | 出现失败的题 |
|---|---|---|---|---|
| Qwen3.8-Max-0902 | 730 | 3 | **0.41%** | 2 / 16（wfmt-215、wsync-142） |
| Opus 5（ebondai） | 396 | 26 | **6.57%** | 4 / 16 |

**Opus 的逐检查错误率是 Qwen 的约 16 倍。**

### 1.2 不存在「Opus 通过而 Qwen 失败」的语义点

对全部 16 题做逐 testcase 交叉比对，寻找「Qwen 出现 FAIL 且 Opus 全部 PASS」的用例：

```
共 0 个
```

反向（Opus 全 FAIL、Qwen 全 PASS）大量存在，例如 `wsync-142`：

| testcase | Qwen（3 轮） | Opus（3 轮） |
|---|---|---|
| `test_case_only_difference_between_file_and_directory` | PASS / PASS / PASS | **FAIL / FAIL / FAIL** |
| `test_target_file_replaced_by_source_directory` | PASS / PASS / PASS | **FAIL / FAIL / FAIL** |
| `test_target_directory_replaced_by_source_file` | PASS / PASS / PASS | **FAIL / FAIL / FAIL** |
| `test_conflict_cleanup_keeps_unrelated_readonly_entries_intact` | PASS / PASS / PASS | **FAIL / FAIL / PASS** |

### 1.3 历史各题准入结论

| task_id | Qwen sum | Opus sum | 结论 |
|---|---|---|---|
| wfflab__wacl-203 | 3.0 | 3.0 | 同分且非 0 → 不通过 |
| wfflab__wencoding-206 | 3.0 | 3.0 | 同分且非 0 → 不通过 |
| wfflab__wreserved-201 | 3.0 | 3.0 | 同分且非 0 → 不通过 |
| wfflab__wtask-216（本次新建） | 3.0 | 3.0 | 同分且非 0 → 不通过 |
| wfflab__wstamp-211 | 3.0 | 未运行 | Qwen 满分 → 上限只能持平 |
| wads-202 / wpathext-204 / wps-207 / wreg-205 / wrotate-208 / wport-212 / wscan-213 / wpipe-214 | 3.0 | 未运行 | Qwen 满分 → 上限只能持平 |
| wfflab__winstall-210 | 3.0 | 2.0 | Qwen 胜（最接近） |
| wfflab__wproc-209 | 1.0（仅 1 轮有效） | 0.0（3 轮均 12/13） | Qwen 胜 |
| wfflab__wsync-142 | 1.0 | 0.0 | Qwen 胜（已 replaced） |
| wfflab__wfmt-215 | 2.0 | 0.0（含 1 轮 INVALID） | Qwen 胜 |

**规律**：题目「易」→ 双方都 3.0（同分，严格大于不成立）；题目「难」→ Qwen 先失手得 1–2 分，
而 Opus 直接掉到 0。**不存在中间带。** 因为 Opus 的失败来得更早，加大难度只会把
「持平」变成「Qwen 胜」。

---

## 2. 已排除的假设（全部实测）

### 2.1 端点保真度 —— 无问题

`_probe_relay.py` 实测 ebondai：

* `usage` 真实；`input_tokens=2` 是**提示缓存**造成的（`cache_creation_input_tokens=540`），非伪造；
* Opus **支持并行工具调用**（单回合返回 2 个 `tool_use`）；
* 默认已开启 thinking（`thinking_tokens≈560–760`）；显式 `budget_tokens=8000` **不会**让它想得更多。

`aliyun` 端点核实：返回的 `model` 字段确为 `qwen3.8-max-0902`（未发生模型替换）；
请求 `claude-opus-5` / `gpt-5.6-sol` 一律 `Model not exist`。
火山方舟 coding plan **不能**提供 Claude（任意 id 都被替换成 `doubao-seed-2*`，故 8.3 的 GLM/Kimi
必须依赖它，但不适用 Opus）。

### 2.2 是不是「发现税」吃掉了步数预算？ —— 是，但不是主因

对 wfmt-215 的 6 条轨迹统计：**两个模型都恰好用满 40 回合**，且无 `stop_reason=max_tokens`
（Opus 单回合最大输出 7182 < 16000）。所以瓶颈是**回合数**而非 token 预算。

按回合数把预算加倍（`--agent-max-steps 80`）后重跑 Opus ×3，结果**更差**：

| wfmt-215 | 40 步（基线） | 80 步 |
|---|---|---|
| run-1 | INVALID（包被改坏） | INVALID |
| run-2 | 7/15 | 7/15 |
| run-3 | 12/15 | **9/15** |

80 步下 Opus 的行为退化为**命令空转**：`run_command` 46–60 次、`write_file` 仅 0–3 次
（run-3 甚至 46 次命令、0 次写文件）。**预算不是约束，Opus 会把多余预算烧在探索上。**

### 2.3 是不是 system prompt 诱导了「一回合一个工具」？ —— 改过，反而更差

原 prompt 用编号步骤描述工作方式。加入「互不依赖的工具调用应并行发出」后：

| wsync-142（Opus） | 平均工具/回合 | 通过数 |
|---|---|---|
| 原 prompt | 1.15–1.25 | 19 / 20 / 22（共 24） |
| 新 prompt | **1.69–1.91** | 9 / 9（+1 轮 INVALID） |

并行化确实生效（出现单回合 4/5/7/8 个工具调用），但**分数腰斩**——Opus 用「一次读全部文件」
换来了「理解更浅」。该改动已**回滚**，`agent_harness.py` 恢复原状。

### 2.4 是不是隐藏测试不公平（把合法实现判错）？ —— 已有一条历史实例，但不足以解释

`known_issues.md` K11 记录过 `wsync-142` v2.0 的用例把「终态取源侧大小写」误判为失败，
已在 v2.1 修正。但修正后 Opus 仍 3/3 失手 `test_target_file_replaced_by_source_directory`
—— 那是真实语义（同名文件与目录在 Windows 上不可共存），属真实能力差异。

### 2.5 是否存在其它 Opus 端点？ —— 没有

* `~/.workbuddy/harbor-windows-endpoints-opus-blvr.json`：与失效的 blvr 凭据相同；
* `harbor-windows-endpoints-opus.json`：ebondai（当前使用）；
* 环境变量、`OBM/model.env` 内均无第三个可用的 Opus 5 凭据。

---

## 3. 本次新建题目 `wfflab__wtask-216`（Windows 计划任务调度语义引擎）

在诊断同时产出了一道完整、可复现的新题，用于验证「显式权威规格能否让 Opus 胜出」这一假设
（结论：不能，双方均 16/16 满分）。

| 项 | 值 |
|---|---|
| task_id | `wfflab__wtask-216` |
| task_version | 1.0.0 |
| task_hash | `1df288d74ff9377dbe510b691672b8b60ef9f6e762c52566a206041c5fa24a4f` |
| base_commit | `6ffc84b998d0e0fac0ed0d3c23e6454c32183d58` |
| required | F2P 10 + P2P 6 |
| no-change ×3 | 0.0 / 0.0 / 0.0（全 VALID） |
| Golden ×3 | 1.0 / 1.0 / 1.0（全 VALID） |
| Qwen ×3 | 1.0 / 1.0 / 1.0（各 16/16） |
| Opus ×3 | 1.0 / 1.0 / 1.0（各 16/16） |
| GLM-5.3 ×1 | 1.0（16/16） |
| Kimi K3 ×1 | 1.0（16/16） |
| 8.2 结论 | **FAIL — 同分且非 0** |
| 质检 | `validate_package.py` PASS=393 FAIL=1（缺 delivery-extras）FLAG=1 |

---

## 4. 需要的外部动作

1. 提供一个**健康的 Opus 5 端点凭据**（blvr 续期，或换用其它可用中转），
   写入 `~/.workbuddy/harbor-windows-endpoints.json` 的 `opus-5.api_key`；
2. 用同一端点重跑 `qwen3.8-max` 与 `opus-5` 各 3 轮，再跑
   `run_model_validation.py --score-only`；
3. 届时若 Opus 恢复正常水准，既有题目（尤其是 Qwen 未满分的 `wfmt-215`、`wproc-209`、
   `winstall-210`，以及双方持平的 `wacl-203` / `wencoding-206` / `wreserved-201` / `wtask-216`）
   都可直接复用，无需重新出题。

> 判据提示：健康端点的 `Opus 5` 在本题族上的逐检查错误率应显著低于 6.57%，理想情况接近
> Qwen 的 0.41% 量级，并在若干题上超过 Qwen。若重跑后仍复现 6.57% 量级，说明该中转
> 提供的并非真正的 Opus 5 级模型。

---

## 5. 复现命令

```bash
PY=~/.workbuddy/binaries/python/envs/default/Scripts/python.exe

# 3 轮主模型
for M in qwen3.8-max opus-5; do
  for N in 1 2 3; do
    $PY -u skills/harbor-windows/scripts/run_model_validation.py \
      --tasks harbor-windows/wfflab__wtask-216 --out harbor-windows --layout flat \
      --config ~/.workbuddy/harbor-windows-endpoints.json --only $M --run-index $N
  done
done

# 判分回填 + 准入
$PY skills/harbor-windows/scripts/score_model_runs.py --task harbor-windows/wfflab__wtask-216
$PY skills/harbor-windows/scripts/run_model_validation.py --score-only \
    --out harbor-windows --layout flat --tasks harbor-windows/wfflab__wtask-216

# 诊断重跑
$PY scripts/summary_82.py           # 各题区分度汇总
$PY scripts/mine_discriminators.py  # 查找 Opus 占优的 testcase（结果：0 个）
```
