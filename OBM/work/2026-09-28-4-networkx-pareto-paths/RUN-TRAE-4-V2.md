# Trae 执行说明（v2 · 加难版）— 2026-09-28-4-networkx-pareto-paths

> **为什么有 v2**：v1 的 no-skill 被 Doubao-Seed-Evolving 直接做对（reward=1，F2P 20/20），按流水线规则判定题目偏简单。本版在**同一道题**上叠加了三条**互相耦合**的能力，把契约从"实现一个函数"扩到"实现一组必须彼此一致的接口"。
> v1 的证据完整保留在 `trae-runs-v1/`，**不要删除**。

---

## v2 相对 v1 新增的三条耦合能力

| # | 新增 | 为什么它制造真实难度 |
|---|---|---|
| 1 | **投影入口** `nx.pareto_frontier(...)`：只返回排序后的 `(cost, weight)` 配对 | 必须恒等于主入口结果的配对投影；另写一套逻辑就会出现"一个入口过滤了上界、另一个没过滤""一个抛异常、另一个返回空列表"的分叉 |
| 2 | **可调用属性**：`weight` / `cost` 可为 `f(u, v, data)` 函数 | 三个入口都要支持，且与属性名写法结果完全一致；解析若不集中在一处，"缺失属性按 0"会只在某一种写法下成立 |
| 3 | **可变图索引** `nx.ParetoIndex`：`pareto / frontier / update_edge / remove_edge / reset / graph` | 任意增删边之后查询结果必须等于"对当前图重新计算"；带缓存/增量的实现最容易返回陈旧结果（删掉参与最优解的边、覆盖同端点不同属性的边），且构造索引不得改动调用方的图 |

另外把规模用例扩到两条：`pareto_paths` 在 4000 节点/16000 边上 <30s；索引的"构造+一次 update+一次 remove+两类查询"在 3000 节点/12000 边上 <30s。

**F2P 从 20 条扩到 41 条**，P2P 仍为 129 条（上游 shortest_paths 基线可过用例）。

---

## 已完成并验证（v2）

| 项 | 结果 |
|---|---|
| 参考实现 | `refimpl/pareto_paths.py`（三入口），暴力 oracle 自证：**292 例随机对拍 + 索引差分（随机变更序列）+ 顺序无关 + 可调用等价 + 异常语义 全过** |
| 本地 verifier | **NOP=0 / ORACLE=1**（F2P 41 / P2P 129） |
| 离线 Docker（官方编排器 `verify_agent_patch.py --docker`） | **NOP=0 / ORACLE=1** |
| `validate_proposals`（两份副本） / `check_skill_language` / `check_package` | 全部通过（`check_package` 仅剩 Windows exec 位 2 项，Linux 复核 PASS） |
| 飞书去重 | v1 已登记（record `recvwv3v2JNGvk`，判断=不重复）；v2 是同题加难，**无需重复登记** |
| 工作区 | `work/2026-09-28-4-networkx-pareto-paths/trae-runs-v2/`（两仓库 `HEAD=72a2b821…`，改动数 0） |

题面指纹（`trae-runs-v2/BASELINE.json`）：
- `proposal_sha256` = `904db96e…`，`skill_sha256` = `80820cfc…`，`verifier_sha256` = `c1f2d255…`
- `no_skill_prompt_sha256` = `e562e09d…`，`with_skill_prompt_sha256` = `dcec241a…`

---

## 执行步骤

### 第 1 步 · Trae 跑 no-skill
1. 打开 **Trae CN**（或 TraeCode IDE），模型选 **`Doubao-Seed-Evolving`**。
2. 「打开文件夹」→
   `C:\Users\Administrator\Desktop\OBM\work\2026-09-28-4-networkx-pareto-paths\trae-runs-v2\4-no-skill\4-no-repo`
   - ⚠️ 打开的是**仓库目录 `4-no-repo`**；**绝不要用隔离 worktree / 沙箱副本模式**。
3. 用编辑器打开 `...\trae-runs-v2\4-no-skill\PROMPT.md`（9745 字节，**在仓库目录之外**），全选复制 → 粘进 Agent → 发送。
4. 等它改码、跑测试、给出最终回复（**中途不要打断**）。

### 第 2 步 · 判分 no-skill（期望 reward=0）

```bash
tr -d '\r' < /mnt/c/Users/Administrator/Desktop/OBM/work/2026-09-28-4-networkx-pareto-paths/tools/run_post_trae_v2.sh | bash -s -- no-skill
```

- 期望 `reward=0`、退出码 **10**。
- 若又判出 `reward=1`（exit 20）→ 说明这条难度轴仍然不够，流水线中止，我们再讨论换轴（见 `NO-SKILL-TOO-EASY-FINDINGS.md` 第三节）。
- 若退出码 22 → 基础设施错误，把输出发我。

### 第 3 步 · Trae 跑 with-skill
打开 `...\trae-runs-v2\4-with-repo\4-with-repo`，复制 `...\4-with-repo\PROMPT.md`（24186 字节，多附「专家解题思路」）全文 → 粘贴 → 发送 → 等完成。

### 第 4 步 · 一键收尾

```bash
tr -d '\r' < /mnt/c/Users/Administrator/Desktop/OBM/work/2026-09-28-4-networkx-pareto-paths/tools/run_post_trae_v2.sh | bash -s -- all
```

期望一路到 `output/deepSWE_2026-09-28-4-networkx-pareto-paths.zip`。

### 第 5 步 · 飞书提交（需你驱动）

---

## 注意

- **v1 与 v2 是两套工作区**：`trae-runs-v1/` 保留 v1 证据（含 `EXPERIMENT_RESULT.json` = `needs_task_hardening`），`trae-runs-v2/` 是本轮要跑的。收尾脚本 `run_post_trae_v2.sh` 只操作 v2。
- `run_post_trae.sh`（无 `_v2`）仍指向 v1，**本轮不要用它**。
- 题面依旧在仓库目录**之外**（用系统编辑器打开），不要复制进仓库。
- 脚本可重入：已有有效 no-skill（reward=0）会跳过重复判分；已是 `passed` 会跳过 with-skill 判分。
