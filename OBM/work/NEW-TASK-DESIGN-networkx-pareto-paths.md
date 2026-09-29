# 新题设计稿（候选 -4）— networkx 精确多目标帕累托路径

> 触发：`2026-09-28-3`（marshmallow diff）no-skill 被 Doubao-Seed-Evolving **37 轮直接做对**（reward=1 → needs_task_hardening），
> 用户决定**弃题换更难**。本文是替换题的设计与前置核查记录。

## 一、为什么上一题被做对（决定新题怎么设计）

- 上题的 `C_agent_task` 把可观察契约写得近乎算法（签名 / op 语义 / path 语法 / 遍历顺序 / 递归规则 / 未知键策略 / 纯函数），强模型只需"照着实现"。
- 探针证明它**实现得完全正确**（14 项未被 F2P 覆盖的契约行为零分歧）→ 不是判分太松，是**任务本身推理量不足**。
- 契约必须清晰（规范硬要求，模糊会触发"只能猜契约"拒收），所以**加难只能加"推理/设计"本身**：算法正确性、全局一致性、复杂度。

## 二、前置核查（已完成）

| 项 | 结果 |
|---|---|
| 本地官方题库（113 题） | `networkx / pareto / frontier / resource-constrained / multi-objective / budget / dominance` **全部 0 命中** |
| 飞书共享库（101 条） | 无 Pareto / 约束最短路 / 多目标题；**NetworkX 被用过 1 次**（`2026-09-26-23` 原子增量拓扑计划） |
| 同仓库复用先例 | 飞书库内 Click ×4、dateutil ×3、attrs/Mashumaro/cachetools/uniseg ×2 → 复用仓库是常态，**判重看能力/场景** |
| 结论 | 能力维度**全新**；仓库复用可接受（需在去重说明中写明能力差异） |

**取源可行性**
- GitHub / codeload 直连**不可达**；**gitee 镜像可 clone**（已实测 networkx 成功）。
- networkx：`dependencies = []`（**零运行时依赖**，离线 Docker 极易构建）；267 个测试文件 / **4533 个测试函数**（P2P 富矿）。

## 三、选题

- **benchmark**：`deepSWE`；**proposal_type**：`A`；**allow_network**：`false`
- **repo**：`networkx/networkx`（gitee 镜像取源）
- **related_question**：`abs-stepped-slices` 或库内最贴近"图算法/优化"的官方题（待定，须在 `benchmark_tasks.json` 的 113 个 task_id 内）
- **能力类型**：图论精确优化（**多目标帕累托最优 + 约束路径**）—— 本项目与共享库中均无

### 公开契约（草案，定稿时必须完整可判定）

新增 `nx.pareto_budgeted_paths(G, source, target, weight="weight", cost="cost")`：

- 返回"**简单路径**"可达的、**非支配** (cost, weight) 对的**完整**帕累托前沿；
- 支配定义：`(c1,w1)` 支配 `(c2,w2)` ⟺ `c1<=c2 且 w1<=w2 且 (c1<c2 或 w1<w2)`；
- 输出按 `cost` 升序（`cost` 相同则按 `weight` 升序）**确定性**排列；每条记录 `{cost, weight, path}`；
- `path` 是该 (cost,weight) 下**字典序最小**的节点序列（并列裁决规则明确）；
- `source == target` → 单条 `{cost:0, weight:0, path:[source]}`；不可达 → `NetworkXNoPath`；
- 边缺属性按 0；**负 cost/weight → `ValueError`**；支持 `Graph` 与 `DiGraph`；
- **纯函数**：不修改 `G`；对节点重命名/等效图重排结果不变；
- 规模要求：在约定规模的图上须在时限内完成（逼迫真正做标号+支配剪枝，而非枚举全部简单路径）。

### 为什么它"硬"（针对上一题的失败模式）

1. **支配剪枝的正确性**：剪错会**静默丢前沿点**——这是标号法最经典的错误；判分用暴力枚举做 oracle，必抓。
2. **完整性 + 精确性**：不能少、不能多（多一个被支配点即失败）。
3. **字典序见证路径**：必须恰为最小序列，容易细节出错。
4. **简单路径语义**：零权环若不处理会出现无限标号。
5. **复杂度**：暴力枚举指数级；规模用例逼迫设计真算法。
6. **repo 集成**：networkx 的 `@nx._dispatchable` 装饰器、图类分派、复用 `NetworkXNoPath`。

### 判分设计

- **F2P（行为级，oracle 驱动）**：随机小图（数十例）与暴力枚举比对**前沿集合**与**见证路径最优性**；边界：`source==target`、不可达、零权环、并列裁决、`ValueError`、确定性（重复调用 + 节点重命名不变性）；外加一条规模用例（时限内）。
- **P2P**：networkx `shortest_paths` / `algorithms/flow` 等**无额外依赖**的测试子集。

## 四、剩余工作量（下一步）

1. 定稿 `related_question` 与 `domain`（受 `benchmark_tasks.json` 约束）。
2. 写**参考实现**（标号 + 支配剪枝 + 字典序见证），并用暴力 oracle 自证。
3. 写 proposal.json（含内联 `expert_experience_skill` 正文）、`sources/skill/SKILL.md`（四条难点与 D 一一对应、不泄漏）。
4. `sources/app`（networkx 基线副本 + Dockerfile + `upstream.tar.gz` `--prefix=networkx/`）、离线 wheels（pytest 等）。
5. verifier（`grader.py` / `config.json` / `test.sh` / `test.patch` / `tests/` / `Dockerfile`）。
6. provenance + sources/README.md。
7. NOP=0 / Oracle=1（本地 + 离线 Docker + 官方编排器）。
8. 飞书去重登记（读回"不重复"后才可建正式包与 Trae 工作区）。
9. `prepare_trae_runs` → 用户跑 Trae 两侧 → 一键收尾。

## 五、风险

- **同仓库复用**：networkx 已被 `2026-09-26-23` 用过，但能力不同；去重说明中必须显式对比（否则可能被判"疑似重复"）。
- **难度是否足够**：目标是把 no-skill 逼到失败或 >100 轮；若新题仍被轻松做对，需再叠一层（如加"参数化最小预算 B*"或"跨图重放的增量维护"）。
- **gitee 镜像漂移**：镜像的 HEAD 可能与官方不一致，需记录取到的具体 commit 并在 provenance 说明来源。
