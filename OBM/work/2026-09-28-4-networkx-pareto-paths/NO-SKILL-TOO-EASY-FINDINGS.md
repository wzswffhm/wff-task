# no-skill 通过 → needs_task_hardening 归因分析

**任务**：`2026-09-28-4-networkx-pareto-paths`
**时间**：2026-09-28 17:16
**结论**：Doubao-Seed-Evolving **未使用专家 skill** 即通过全部验证（F2P 20/20、P2P 129/129，含规模时限用例），流水线按设计中止于 `needs_task_hardening`（exit 20）。**这已是连续第二道题出现同样结局**（上一道：`2026-09-28-3-marshmallow-doc-diff`）。

---

## 一、判分事实

| 项 | 值 |
|---|---|
| no-skill reward | **1** |
| F2P | 20 / 20（missing 0、not_passed 0） |
| P2P | 129 / 129（missing 0、not_passed 0） |
| 判分环境 | 离线 Docker（`--network=none`），官方编排器 `verify_agent_patch.py --docker` |
| 产物 | `4-no-skill/verification/{VERIFICATION.json, MANUAL_RESULT.json, VERIFIER_RUN.log}`；`reward.json = 1` |

Agent 产物：新增 `networkx/algorithms/shortest_paths/multiobjective.py`（`pareto_paths`，282 行）+ 在 `shortest_paths/__init__.py` 导出 + 自建 `tests/test_multiobjective.py`（354 行）。
实现路线：**Martins 标号法**（每节点维护按 (cost, weight) 排序的帕累托前沿 + `bisect` 插入 + 父指针 + 剥离零权环得到简单见证），正是本题期望的正确算法族。

> 说明：agent 还留下了 297 个 `__pycache__/*.pyc`（它跑过测试）。它们以 `Binary files ... differ` 形态出现在 patch 中，无 `+++`/`---` 头，被评测端的补丁过滤器自动丢弃，**不影响判分**。

## 二、关键诊断：不是"测试太窄"

用一份**独立契约探针**（`tools/probe_contract4.py`）在 **F2P 未覆盖**的行为上对拍 Agent 实现 vs 参考实现：

| # | 探针 | Agent | 参考 |
|---|---|---|---|
| 01 | `max_cost` ∧ `max_weight` 同时收窄 | (4,2) | 同 |
| 02 | 上界把全部路径挡掉 → 空列表 | `[]` | 同 |
| 03 | 非字符串节点（int / tuple） | (2,3) | 同 |
| 04 | 正代价自环 | (2,2) | 同 |
| 05 | `source == target` 且存在正环 | `[(0,0,[s])]` | 同 |
| 06 | 缺省属性按 0 | (1,2) | 同 |
| 07 | 无向图 | 2 条前沿 | 同 |
| 08 | 目标存在但不可达 | `NetworkXNoPath` | 同 |
| 09 | 负值出现在**不参与任何 s-t 路径**的边上 | 不报错 | 同 |
| 10 | 自定义属性名 `weight=`/`cost=` | (3,3) | 同 |
| 11 | MultiDiGraph | `NetworkXNotImplemented` | 同 |
| 12 | 确定性（重复调用一致） | SAME | 同 |
| 13 | 纯函数（不改图） | YES | 同 |
| 14 | 零权零代价环（不得死循环、见证必须简单） | `[s,a,b,t]` | 同 |
| 15/16 | 平局（两条不同简单路径同一 (cost,weight)） | 见证合法且简单 | 同 |
| 17 | 反向平行边 | (2,2) | 同 |
| 18/19 | 源点/目标缺失 | `NodeNotFound` | 同 |
| 20 | **300 例随机对拍**（n≤8、含零代价、暴力枚举全排列 oracle） | **PASS** | **PASS** |

**逐项零分歧**。→ Agent 的实现是**完整正确的**，不存在"被弱测试漏放的错误实现"。
（附带更正：探针初版用 `combinations` 枚举简单路径，漏掉了绝大多数排列，两边都报 185 例不一致——那是**探针自身的 bug**，改用 `permutations` 后归零。这也提醒：oracle 写错会伪造出"实现有 bug"的假象。）

## 三、根因：难度轴选错了

两道题的题面结构都是 **「在 prompt 里给出一份完整、精确的行为契约，要求实现它」**。
在这种结构下，**prompt 本身就是设计文档**，模型只需把规范"翻译"成代码——而 Doubao-Seed-Evolving 在这条轴上极强。题目的难度上限被题面本身锁死了，与算法本身有多难无关（帕累托标号法并不简单，但它**被完整地描述出来了**）。

要制造难度，必须把难度放在**题面无法给出**的地方：

| 难度来源 | 能否写进 prompt | 说明 |
|---|---|---|
| 算法复杂度 | ✅ 能 | → 锁死上限（我们两次都栽在这） |
| 边界/异常语义 | ✅ 能 | 同上 |
| **缺陷定位** | ❌ 不能 | 只给症状，需在陌生代码库里定位 |
| **既有约定/内部不变量的发现** | ❌ 不能 | 约束藏在代码里（dispatch、backends、缓存、deprecation） |
| **跨模块耦合与回归压力** | ⚠️ 部分 | 需在不破坏大量既有行为的前提下改造 |
| **环境交互与多步试错** | ❌ 不能 | 构建失败→读日志→修→再跑 |

## 四、硬化方向（按性价比排序，供选择）

1. **【推荐】换难度轴：多步环境交互题**。用本地已有的 `terminal-bench-main`(68) / `swe-marathon-main`(22) 风格任务形态——需要真实构建/运行/读日志/迭代，agent 的失败面大得多。代价：要另起一套题包规范与工具链。
2. **症状诊断题**：题面只描述现象（如"某些图上前沿不完整 / 与 backend dispatch 不兼容 / 大图上内存爆炸"），要求定位并修复既有实现的隐蔽缺陷，且不破坏既有行为。难点在**定位**。代价：要我们先构造一个"有隐蔽缺陷的基线实现"，且需保证缺陷不会被一眼看穿。
3. **叠加弱可推导的耦合**：在 `pareto_paths` 之上再要求（a）只算前沿**规模**而不枚举标签、（b）增量维护（一条边变更后做有效更新）、（c）与 `nx.shortest_path(method=...)` 体系对齐。三者互相拉扯，容易出现一致性缺陷。风险：仍属"实现题"，可能再次被直接做对。
4. **歧义契约**：让契约含隐含冲突（如"顺序确定"与"与输入边序无关"在某些平局下不可同时满足），要求 agent 识别并给出裁决与论证。风险：易被判定为题目缺陷。
5. **按需求方口径交付**：第 2 条属"质量激励"、非硬门禁，可如实记为 `not_met` 并照常打包提交（本题为"合格但训练价值偏低"的样本）。注意本地 `capture_final_check`/`build_delivery_zip` 会因 `no_skill.reward != 0` 拦住，需要放宽。

## 五、当前状态（未做任何"补写证据"的动作）

- `EXPERIMENT_RESULT.json` = `needs_task_hardening`（**如实记录**）。
- `output/deepSWE_2026-09-28-4-networkx-pareto-paths/` 完整保留，**未打包**、`output/` 下无 zip。
- `trae-runs-v1/4-no-skill/` 保留原始证据（含 patch、verification、日志）。
- `4-with-repo` 工作区**未被触碰**（改动数 0），随时可用于加难后的对照，或直接作废重跑。

---

## 六、处置（2026-09-28 17:4x）：本版加难为 v2

**用户选择**第四节方向 3「在本题上叠加耦合能力」。据此落地（并对选项描述做了两处工程修正：放弃"不枚举标签"这类只能靠计时的判据；放弃与 `shortest_path(method=)` 对齐，因为它与本题"缺失属性按 0"的语义冲突）。

### v2 新增的三条耦合能力

1. **`nx.pareto_frontier(...)`** —— 只返回排序后的 `(cost, weight)` 配对，必须**恒等于**主入口结果的配对投影（带/不带双上界都要成立），边界与异常语义同主入口。
2. **可调用属性** —— `weight` / `cost` 可为 `f(u, v, data)`，三个入口都要支持，且与属性名写法给出完全相同的集合与顺序。
3. **`nx.ParetoIndex`** —— 可变图索引（`pareto` / `frontier` / `update_edge` / `remove_edge` / `reset` / `graph`）；任意增删边之后查询必须等于「对当前图直接调用函数式入口」（含空结果与异常种类）；构造索引不得改动调用方的图；`remove_edge` 对不存在的边抛 `NetworkXError`。

外加：**前沿集合与边插入顺序无关**；规模用例扩到两条（`pareto_paths` 4000n/16000e；索引"构造+变更+两类查询" 3000n/12000e，各 <30s）。

### 验证结果（全绿）

| 项 | 结果 |
|---|---|
| 参考实现自证（`refimpl/test_cross_v2.py`） | 292 例暴力 oracle 对拍 + 索引差分（随机变更序列 vs 全量重算）+ 顺序无关 + 可调用等价 + 异常语义 —— **全过** |
| 本地 verifier | **NOP=0 / ORACLE=1**（F2P **41** / P2P 129） |
| 离线 Docker（官方编排器） | **NOP=0 / ORACLE=1** |
| `validate_proposals`（两份）/ `check_skill_language` / `check_package` | 通过（`check_package` 仅剩 Windows exec 位 2 项，Linux 复核 PASS） |

### 预期与风险（如实记录）

按第三节的根因分析，**本轮仍属"prompt 给契约 → 实现"这条轴**，只是把契约从"一个函数"扩成"一组必须彼此一致的接口"。提升的是**交互密度**（三入口一致性 × 可调用属性 × 索引状态 × 顺序无关），使"某处细微不一致"的概率显著上升，且判分用**差分 oracle**（暴力枚举 + 全量重算）能抓住任何一处不一致。但这**不保证**能难住 Doubao-Seed-Evolving —— 若 v2 的 no-skill 仍判 1，按第三节结论应换难度轴（方向 1 或 2）。

### 版本与证据

- v1 证据保留：`trae-runs-v1/`（含 `EXPERIMENT_RESULT.json` = `needs_task_hardening`），**未删除、未修改**。
- v2 工作区：`trae-runs-v2/`（`HEAD=72a2b821…`，改动数 0）。
- v2 收尾脚本：`tools/run_post_trae_v2.sh`（`run_post_trae.sh` 仍指向 v1，本轮不要用）。
- v2 执行说明：`RUN-TRAE-4-V2.md`。
