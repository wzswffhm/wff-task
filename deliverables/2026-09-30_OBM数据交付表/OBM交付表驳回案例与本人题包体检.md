# OBM 数据交付表：他人驳回案例分析与本人题包体检

- 检查日期：2026-09-30
- 数据来源：飞书「OBM数据交付表」 wiki 节点 `R9dbw2Dm6ioXbrkefZScH1dFnfk`（`obj_token = ZqH1bHq4AaTIqrsg4sfctdknnuf`，表 `tblEzvAKrSNJNkwi`）
- 拉取方式：`lark-cli base +record-list`，`--as user`（身份 `wff` / `ou_35041b…`），全表 361 行
- 本地快照：`OBM/feishu-records/obm-delivery-20260930.ndjson`（+ `.manifest.json`）

---

## 一、结论速览

1. **交付表共 361 行，其中被明确驳回或要求返修的共 17 行**（状态 `驳回` 2、`待返修` 15），另有 32 行的 `驳回理由` 字段写有实质意见（部分行状态仍显示 `待质检`，说明状态字段与驳回理由存在不同步）。
2. 他人被驳回的原因高度集中在**四类**：打包与命名不一致、包内混入非交付材料、`proposal_verify` 缺题目专属可观察判据、`expert_experience_skill` 非中文或不结合本题。真正因**verifier 存在实质漏洞**被判 FAIL 的只有 3 例。
3. **本人（`标注人 = wff`）在表中只有 1 条记录**：`deepSWE_2026-09-29-1-pycasbin-decision-trace`，状态 `待质检`，`驳回理由` 为空——**目前尚未被驳回**。
4. 该题包经本地全量复检，**未命中他人的任何一类高频驳回原因**：`sources/README.md` 完整、无题面/`task.toml`/`solution`/`calibration`/`.git` 混入、题目名与附件名及解压最外层目录三处一致、压缩包内容与本地目录逐文件 sha256 一致、`proposal_verify` 有逐项可观察判据、`F2P 514 / P2P 312` 远超门槛、proposal 与 skill 中文检查 PASS、8 条难点均有 skill 专章。
5. **唯一需要留意的两处轻微覆盖缺口**（详见 5.2.2）：契约声明了「四个公开类型从包顶层可导入」与「方法在 `CoreEnforcer` 所有子类可用」，但 F2P 测试只 `from casbin import Enforcer` 并使用基类，未对这两条做断言。属边缘接口未单测，非核心行为缺失；补 2 个测试即可闭合。
6. 工作区里另有 **3 个 9-28 批次题包（diskcache / marshmallow / networkx）尚未提交**，它们**同时命中两类高频驳回原因**：proposal 与 skill 的英文未包裹 + 模板化句式（语言检查 FAIL），以及 `F2P` 节点数远低于 71 的现行门槛。若原样提交，大概率被打回。

---

## 二、交付表整体状态分布

| 状态 | 行数 |
|---|---|
| 已同步 | 250 |
| 待质检 | 83 |
| 待返修 | 15 |
| （空） | 6 |
| 质检通过 | 3 |
| 驳回 | 2 |
| 已领取 | 2 |
| **合计** | **361** |

> 注意：`驳回理由` 字段存在复用现象（274 行为空、41 行写「已同步」、12 行写「格式校验通过」描述）。判断是否被驳回需**同时看 `状态`、`交付状态`、`质检结论`、`驳回理由` 四个字段**，单看 `状态` 会漏。

---

## 三、他人被驳回原因分类（32 条实质意见）

### 第 1 类｜打包与命名不一致（9 条）

| 题目 | 标注人 | 具体原因 |
|---|---|---|
| terminal_bench4_jsonlines-versioned-recovery-repository | 用户049061 | 题目名 / 附件 basename / 解压最外层目录三者不一致 |
| terminal_bench3_drift_retraction_replay | 用户049061 | 压缩包没有统一最外层目录，`proposal.json` 直接位于根部 |
| terminal_bench4_diskv_journal_repair_v7 | 用户049061 | 解压后是 `qc/` 质检证据目录 + 嵌套 zip，没有正式交付结构 |
| terminal_bench3-pebble-atomic-checkpoint | 刘豪 | 附件 basename 用连字符、最外层目录用下划线 |
| terminal_bench3-bbolt-durable-prefix-log | 刘豪 | 题目名用连字符、附件用下划线 |
| terminal_bench4_2026-09-27-8-binary-index-rebuilder | 田世宇 | 附件带 `repair-20260928` 后缀，题目名与目录未同步 |
| terminal_bench4_2026-09-28-11-1005-wal-recovery-manifest | 田世宇 | 同上 |
| terminal_bench4_2026-09-28-1000-jsonl-shard-reconciler | 田世宇 | 同上 |
| terminal_bench4_2026-09-28-1015-1015-ndjson-schema-auditor | 田世宇 | 同上 |
| terminal_bench4_2026-09-28-21-1020-csv-canonicalizer | 田世宇 | 同上 |
| froniterSWE_fits-archive-recovery | 周云福 | 飞书记录根本没有交付压缩包附件 |

**要害**：`题目名 == 附件 basename（去 .zip）== 解压最外层目录` 必须三处逐字一致，任何 `-`/`_` 混用或补丁版本后缀不同步都会被直接打回。

### 第 2 类｜包内混入非交付材料（7 条）

| 题目 | 标注人 | 混入内容 |
|---|---|---|
| terminal_bench3_versioned-changefeed | 刘豪 | `sources/task/instruction.md` 完整题面 |
| terminal_bench4_2026-09-28-230-policy-replay-200 | 田世宇 | `sources/app/instruction.md` + `sources/app/task.toml` |
| terminal_bench3_bitemporal_checkpointed_flow_with_task_materials | 用户049061 | `sources/task/instructions.md`、`SPEC.md`、task 运行材料 |
| terminal_bench4_bbolt_snapshot_replicated | 用户049061 | `solution/main.go`、`solve.sh` 参考实现 |
| deepSWE_go_task_resumable_dag_sessions | 林丹 | `sources/calibration/` 校准日志、mutant/baseline/reference 运行结果 |
| terminal_bench4_bbolt-checkpoint-merge-2026053 | 孙旷 | `sources/starter/repo/.git/` Git 过程元数据 |
| （上表多条重复出现） | — | 同上 |

**要害**：正式 Step4 包里只允许 `proposal.json` + `sources/`（含 `sources/README.md`）。题面、`task.toml`、`SPEC.md`、参考实现、校准日志、`.git` 全部禁止。

### 第 3 类｜`proposal_verify` 只有主题列表、没有可观察判据（14 条，**最高频**）

| 题目 | 标注人 | 缺失的判据 |
|---|---|---|
| deepSWE_2026-09-28-1-testify-mock-order | 用户575691 | 菱形依赖、环、跨实例边、竞争调用的期望返回与计数变化 |
| deepSWE_2026-09-28-3-multierror-tree | 用户575691 | 嵌套错误、重复叶、连接错误、类型化空值、环的 `Is/As` 与格式化预期 |
| deepSWE_2026-09-28-4-gjson-query-plan | 用户575691 | 每类输入的期望结果、失败码、原文与索引快照隔离 |
| deepSWE_2026-09-28-5-dns-truncation-plan | 用户575691 | 预期压缩大小、`OPT/TSIG` 保留、过期计划拒绝 |
| deepSWE_2026-09-28-6-prometheus-descriptor-audit | 用户575691 | `Describe` 调用次数、超时/恐慌结果、注册表不变性 |
| deepSWE_2026-09-28-9-logr-context-snapshot | 用户575691 | 快照不得输出、奇数键降级、调用深度保持 |
| programbench_2026-09-28-10/13/14/15/17（5 条） | 田世宇 | 只写「运行官方 eval 并记录 score」，缺字形布局、终端状态、边界输入、错误路径等题目专属判据 |
| terminal_bench4_2026-09-27-8 / -11-1005 / -1000 / -1015 / -21（5 条） | 田世宇 | 同上，另需补 WAL 校验和、版本向量、CSV 引号换行等 |

**要害**：`proposal_verify` 必须是「本题哪类输入 → 期望观察到什么行为 / 退出码 / 失败条件」的逐条清单，不能写成测试主题概括或「跑官方评测看分数」。

### 第 4 类｜`expert_experience_skill` 不合格（4 条）

| 题目 | 标注人 | 问题 |
|---|---|---|
| deepSWE_2026-09-26-2-hpack-transactional-blocks | 欧阳 | 字段里只写英文「见 sources/skill/SKILL.md」，未提供中文经验正文 |
| terminal_bench4_consensus-snapshot-recovery-2026048 | 孙旷 | 通用「不变量/状态迁移排查」流程，未结合本题；`proposal_verify` 还混入 `context`/`baggage`/`span` 等无关字段 |
| swe_marathon_event-window-reconciliation-2026049 | 孙旷 | 与其他题共用同一套通用流程 |
| deepSWE_policy-graph-migration-2026050 | 孙旷 | 同上 |

**要害**：`expert_experience_skill` 必须是**字段内**的中文口语化正文，且针对本题具体机制；不能只引用外部文件，也不能套用跨题通用模板。

### 第 5 类｜verifier 实质缺陷导致质检 FAIL（3 例，最严重）

| 题目 | 标注人 | 状态 | verifier 问题 |
|---|---|---|---|
| terminal_bench4_redissmq_queue_store_cutover-remount-20260923-final | 林丹 | 驳回 | 未实现公开声明的「5 秒成功率 + 10 秒超时滑动窗」，`rollbackToRedis` 结果不被断言 → **错误实现可以通过** |
| programbench_contract-pack-audit | 罗竣元 | 驳回 | 缺 `sources/README.md`；十万行用例只限制时间/产物大小，未测峰值内存，无法判定 C 契约的「不得整表驻留内存」 |
| deepSWE_diskcache-leased-work-queue | 刘豪 | 质检通过但结论 FAIL | 缺 `sources/README.md`；失败原因枚举、性能计时区间、允许的标准库三处契约与 verifier 不一致 |
| terminal_bench4_vision_ddp_incident_hard_v3 | 孙旷 | 质检通过但结论 FAIL | 主评测进程不受限加载候选 pickle；缺非零学习率下的独立梯度/参数 oracle |
| terminal_bench3_billy-memfs-transactions | 罗竣元 | 质检通过但结论 FAIL | 缺 `sources/README.md`；Oracle 的只读事务无条件成功，与 B 契约「基础状态修改后旧事务必须冲突」矛盾 |

**要害**：verifier 必须覆盖 `C_agent_task` 里公开声明的**每一条**约束；声明了却没断言 = 错误实现可蒙混通过 = 直接驳回。同时 `sources/README.md` 缺失是硬性格式错误。

---

## 四、本人题包在交付表中的状态

| 项目 | 值 |
|---|---|
| record_id | `reczz28HEThWtwwu` |
| 题目名or编号 | `deepSWE_2026-09-29-1-pycasbin-decision-trace` |
| 标注人 | `wff`（`ou_35041bb28c45c5be1213b2b1af040d90`） |
| 关联benchmark | `deepSWE` |
| 状态 | **待质检** |
| 交付压缩包 | `deepSWE_2026-09-29-1-pycasbin-decision-trace.zip`（附件已上传） |
| 最终检测skill的检测结果截图 | `FINAL_CHECK.png`（附件已上传） |
| 驳回理由 | *（空）* |

**结论：本人目前没有任何被驳回的记录。** 表中其余 3 个本地题包（diskcache / marshmallow / networkx）**从未提交到交付表**，因此不计入他人评审范围。

---

## 五、本人题包逐项体检

本地共有 4 个正式题包（`OBM/output/`），逐一对照上表第 1–5 类高频驳回原因复检。

### 5.1 汇总矩阵

| 检查项（对照他人驳回原因） | 2026-09-28-2 diskcache | 2026-09-28-3 marshmallow | 2026-09-28-4 networkx | 2026-09-29-1 pycasbin |
|---|---|---|---|---|
| 是否已提交交付表 | ❌ 未提交 | ❌ 未提交 | ❌ 未提交 | ✅ 待质检 |
| `sources/README.md` 存在且逐项说明 | ✅ | ✅ | ✅ | ✅ |
| 无题面 / `task.toml` / `SPEC.md` | ✅ | ✅ | ✅ | ✅ |
| 无 `solution/` / `calibration/` / `.git` | ✅ | ✅ | ✅ | ✅ |
| 题目名 = 目录名 = zip 名 | — 未打包 | — 未打包 | — 未打包 | ✅ 一致 |
| `proposal_verify` 有题目专属可观察判据 | ✅ 有明细 | ✅ 有明细 | ✅ 有明细 | ✅ 详尽 |
| `expert_experience_skill` 中文、题目专属 | ✅ | ✅ | ✅ | ✅ |
| proposal 语言检查 | ❌ **FAIL** | ❌ **FAIL** | ❌ **FAIL** | ✅ PASS |
| skill 中文检查 | ❌ **FAIL** | ❌ **FAIL** | ❌ **FAIL** | ✅ PASS |
| `F2P` 节点数（现行门槛 ≥71） | ❌ **13** | ❌ **11** | ❌ **41** | ✅ **514** |
| `P2P` 节点数（现行门槛 ≥71） | ❌ **31** | ✅ 826 | ✅ 129 | ✅ 312 |
| 节点重复 | 0 | 0 | 0 | 0 |
| `check_package.py` | FAIL（语言 + 可执行位） | FAIL（语言 + 可执行位） | FAIL（语言 + 可执行位） | PASS（仅 Windows 可执行位告警） |

### 5.2 已提交题包 `pycasbin-decision-trace` 详查

`check_package.py` 结果：除 2 条 Windows 平台固有的 `test.sh` / `grader.py` 可执行位告警（打包时写 0o755，容器内复检通过）外，其余全部 PASS；语言检查 PASS（proposal 汉字 5480，skill 汉字 2076 / 英文字母 0）。

- **包内材料**：`sources/verifier/examples/` 为回归测试的 model/policy 夹具、`tests/` 为上游测试副本 + 新增 `test_decision_trace.py`、`app/.github/` 为上游自带的 CI 配置（非 `.git` 过程元数据）。上述用途均在 `sources/README.md` 中逐项写明，并附三条 `docker build/run` 复现命令。**未被 README 漏述的目录。**

### 5.2.1 打包与命名三处一致性（含压缩包内部实解）

| 比对项 | 实际值 | 一致 |
|---|---|---|
| 交付表 `题目名or编号` | `deepSWE_2026-09-29-1-pycasbin-decision-trace` | 基准 |
| 交付表附件 basename（去 `.zip`） | `deepSWE_2026-09-29-1-pycasbin-decision-trace` | ✅ |
| 压缩包解压最外层目录 | `deepSWE_2026-09-29-1-pycasbin-decision-trace/`（361 个条目全部位于该唯一根下） | ✅ |

压缩包内部结构为 `<root>/proposal.json` + `<root>/sources/`，**没有** `instruction.md`、`task.toml`、`SPEC.md`、`solution/`、`calibration/`、`.git/`。压缩包 319 个文件与本地 `output/` 目录 319 个文件**逐文件 sha256 完全一致**（无「上传了旧版本」风险）。

> 本地文件名带 `.attach-verified` / `.run1-rehearsal` 后缀，仅为本地版本标记；**上传到飞书后的附件名已恢复为标准名**，不构成命名不一致。

### 5.2.2 公开契约与 verifier 断言覆盖矩阵

`proposal_verify` 声明 F2P 514 节点、P2P 312 节点，并记录本地 NOP=失败 / Oracle=通过的实测结果（两侧均在禁网下完成）。逐条抽取 `C_agent_task` 的公开声明，与 63 个唯一 F2P 测试函数（参数化展开为 514 节点）对照：

| C 契约声明 | 对应断言 | 状态 |
|---|---|---|
| `allowed` 恒等于 `enforce()` | `test_traced_allowed_agrees_with_enforce`、`test_traced_allowed_matches_expected_table` | ✅ |
| `matched` 求值顺序 / 只含被求值且匹配为真 | `test_matched_indexes`、`test_eval_matcher_false_rule_is_not_matched`、`test_role_hierarchy_beyond_max_level_is_not_matched` | ✅ |
| `decisive` 长度零或一、是中断点规则 | `test_decisive_holds_at_most_one_rule`、`test_decisive_is_a_subset_of_matched`、`test_decisive_indexes` | ✅ |
| `disabled` 语义 | `test_disabled_enforcer_reports_bypass`、`test_enabled_enforcer_marks_disabled_false`、`test_disabled_enforcer_does_not_validate_request_shape` | ✅ |
| `effect` 三条取值规则（含 `indeterminate` 不中断） | `test_matched_effects`、`test_decisive_rule_has_a_determinate_effect`、`test_without_eft_token_every_match_effect_is_allow` | ✅ |
| 五效果族中断条件 + 放行时 `decisive` 为空 + 优先级永不为空 | 参数化覆盖 `[allow-override]`/`[deny-override]`/`[allow-and-deny]`/`[priority]`/`[subject-priority]` | ✅ |
| `op` 只接受 `add`/`remove` | `test_would_change_invalid_operation_is_rejected` | ✅ |
| `mutations` 单个或序列、按序施加 | `test_would_change_accepts_a_bare_mutation`、`..._applies_mutations_in_order`、`..._combines_multiple_mutations` | ✅ |
| 变更语义（策略/角色增删、角色链接副作用、重复 no-op、优先级插入） | `..._adding_a_grouping_rule_grants_access`、`..._removing_a_grouping_rule_revokes_access`、`..._adding_a_duplicate_rule_is_a_noop`、`..._priority_model_reveals_the_next_rule` 等 15 条 | ✅ |
| 空变更序列前后结论相同 | `test_would_change_with_no_mutations_is_a_noop` | ✅ |
| 不得修改引擎状态（策略、角色链接、条件角色管理器、watcher） | `test_tracing_does_not_change_the_policy`、`..._change_role_links`、`..._leaves_the_policy_untouched`、`..._keeps_registered_link_conditions`、`..._leaves_conditional_enforcer_intact`、`..._does_not_notify_the_watcher` | ✅ |
| 空策略 / 请求值个数不符 / `eval()` 空策略异常与 `enforce()` 一致 | `test_empty_policy_*`、`test_invalid_request_size_raises_runtime_error`、`test_too_many_request_values_raises_runtime_error`、`test_eval_matcher_with_empty_policy_raises_runtime_error` | ✅ |
| 不改变既有行为（既有测试继续通过） | P2P 312 节点（含上游测试副本回写防篡改） | ✅ |
| **四个公开类型的名字与「从包顶层可导入」** | 无。测试文件只 `from casbin import Enforcer`；`TraceResult` / `PolicyMatch` / `ChangeImpact` 引用次数均为 **0** | ⚠️ 缺口 |
| **两个方法加在 `CoreEnforcer`、所有具体子类都能用** | 无。F2P 仅使用基类 `Enforcer`，未覆盖 `FastEnforcer` / `SyncedEnforcer` 等子类 | ⚠️ 缺口 |

**两个缺口的风险等级：低—中。**
- 字段本身已被断言——测试通过 `.changed` / `.before` / `.after` / `.matched` / `.decisive` 做鸭子类型访问，缺的只是「类型名」与「顶层 import 路径」这一层接口形状。
- 与林丹那例（声明了 5 秒成功率与 10 秒超时滑动窗却**完全未实现**、`rollbackToRedis` 结果不被断言）性质不同：那属核心行为零覆盖，本例属边缘接口未单测。
- 但按甲方「声明了就要有对应断言」的一致尺度，这两条仍可能被写进「整改与补证建议」。补强成本很低：加 2 个测试即可（① 从 `casbin` 顶层导入四个类型并校验字段顺序；② 用 `FastEnforcer` / `SyncedEnforcer` 各跑一次 `enforce_traced` 与 `would_change`）。

### 5.2.3 难点—skill 映射（已代查）

| 难点 | `SKILL.md` 对应章节 |
|---|---|
| 1 四种效果族中断条件不同 | 先读求值循环，把「什么时候停」搞清楚 |
| 2 `matched` 边界三元集合不同 | 该记哪些规则：三个集合别混 |
| 3 `decisive` 随效果族变化 | 决定结论的那条规则要分效果族定 |
| 4 效果取值两条退化路径 | 效果取值有两条退化路径，别漏 |
| 5 沙箱深拷贝不隔离角色图 | 试算的沙箱隔离：最容易翻车的地方 |
| 6 条件角色管理器函数丢失 | 条件角色管理器上注册的函数要活下来 |
| 7 空策略路径无归属规则 | 空策略是单独的路径 |
| 8 全矩阵一致性不变量 | 我会怎么自查 + 把公开命名当成契约本身 |

### 5.3 未提交的 3 个 9-28 题包（风险项）

三个包结构层面干净（README 齐全、无题面泄漏、无参考实现），但**同时命中两类高频驳回原因**：

1. **语言合规 FAIL**（对应第 3、4 类）
   - diskcache：13 项——`SQLite`、`cache.batch`、`verifier`、`tag`、`Apache-2.0` 等技术标识未加反引号；`C_agent_task`、`B_modification_details` 与 skill 中连续使用「首先、其次、再次、最后」。
   - marshmallow：17 项——`marshmallow`、`Schema.document_diff`、`include_unknown`、`Nested`、`List` 未包裹；`A_modification_idea` 单句过长；skill description 与正文均有未包裹英文。
   - networkx：19 项——`nx.pareto_paths`、`networkx`、`cost`/`weight`、`update_edge` 未包裹；`A_modification_idea`、`proposal_verify` 单句过长；`expert_experience_skill` 出现模板序列词。
2. **`F2P` 节点数不达标**（对应第 5 类：契约声明与覆盖量对不上时最易被质疑）
   - diskcache 13 / 31、marshmallow 11 / 826、networkx 41 / 129，均低于现行「F2P、P2P 各 ≥71」门槛。

> 补充说明：`F2P ≥71` 是 09-29 之后加入 skill 规范的新门槛，按规范原文「旧题包不因这条新增目标被追溯判为失败」。但这三个包**尚未提交**，一旦提交即按现行标准评审，因此仍构成实际风险。另外 `networkx` 的 `sources/verifier/config.json` 只有 `f2p_node_ids` / `p2p_node_ids` 两个键，缺 `benchmark`、`task_id`、`proposal_name`、`grader`、`test_entry`、`scoring` 等字段，与其他三个包不一致，需要对齐。
>
> 另：登记表 `OBM/task-registry.json` 里的 `2026-09-28-1-module-cache-flag-invalidation` 状态为 `packaged`，但包路径指向 `_qc-demo\batch\...`，该目录在本机已不存在，属于**登记表与实际资产脱节**，建议核对后修正或删除该条。

---

## 六、建议的下一步

| 优先级 | 事项 |
|---|---|
| P0 | `pycasbin-decision-trace` 保持现状等待质检；难点—skill 映射已代查通过（见 5.2.3）。可选加固：补 2 个 F2P 测试闭合 5.2.2 的两处接口覆盖缺口（顶层导入四个类型并校验字段顺序；用 `FastEnforcer`/`SyncedEnforcer` 各跑一次），需重跑 NOP/Oracle 并重新打包上传 |
| P0 | 若要提交 9-28 三个包：先修正语言合规（技术标识加反引号、删除「首先/其次/再次/最后」、拆长句），再补齐 `F2P` 到 ≥71 并重跑 NOP/Oracle |
| P1 | 对齐 `networkx` 包的 `config.json` 字段结构；核查 `task-registry.json` 中指向 `_qc-demo` 的失效条目 |
| P1 | 提交前固定执行三连：`validate_proposals.py` → `check_proposal_language.py` / `check_skill_language.py` → `check_package.py`；打包后核对 `题目名 == 附件 basename == 最外层目录` |
| P2 | 其余未被驳回但状态显示 `待质检` 的行（尤其 `驳回理由` 非空的行）说明状态字段滞后，建议在回写表中避免只更新单一字段 |

---

## 附录：复现命令

```sh
# 飞书身份核对
node "$RUNJS" auth status --json --verify --as user

# 拉取交付表全量
node "$RUNJS" base +record-list \
  --base-token ZqH1bHq4AaTIqrsg4sfctdknnuf \
  --table-id tblEzvAKrSNJNkwi \
  --format ndjson --output ./feishu-records/obm-delivery-20260930.ndjson \
  --overwrite --limit 2000 --as user

# 题包体检（工作目录 OBM/）
P=./.venv/Scripts/python.exe
SK=C:/Users/Administrator/Desktop/wff-task/skills/OBM
"$P" "$SK/proposal_validator/validate_proposals.py" output/<包名>
"$P" "$SK/scripts/check_proposal_language.py" output/<包名>/proposal.json
"$P" "$SK/scripts/check_skill_language.py"   output/<包名>/sources/skill/SKILL.md
"$P" "$SK/scripts/check_package.py"          output/<包名> --benchmark deepSWE
```
