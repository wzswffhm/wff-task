# Trae 执行说明 — 2026-09-28-4-networkx-pareto-paths

> **除 Trae 双跑外的所有步骤已完成**：题包构建 + 三路验证（本地 / 离线 Docker / 官方编排器）+ 飞书去重登记 + Trae 工作区生成 + 一键收尾脚本。
> 现在只差**你在 Trae GUI 里跑两组**（这一步没有 CLI，必须人工；OBM 规范也禁止我驱动 Trae）。

---

## 题目一句话

为 **networkx** 增加多目标（帕累托）最短路径查询：

```
nx.pareto_paths(G, source, target, weight="weight", cost="cost", *, max_cost=None, max_weight=None)
```

返回起终点之间**所有互不支配的 (cost, weight) 组合**，并为每个组合给出**属性精确吻合的简单见证路径**；同时满足双上界过滤、四类边界结局（起终点同点 / 节点缺失 / 不可达 / 被上界挡空）、纯函数、确定性，以及数千节点规模下的时限。

---

## 已完成并验证的部分

| 项 | 结果 |
|---|---|
| 题号 | `2026-09-28-4`（原子预留，scene 指纹 `b00fb844…`） |
| 上游 | `networkx/networkx` @ tag `networkx-3.6.1` = `7530809bfa1ea7ed6fdf918a4d1431488953cb1f`（零运行时依赖） |
| 参考实现 | `refimpl/pareto_paths.py`，**1500 例暴力枚举对拍全部通过** |
| 本地 verifier | **NOP=0 / ORACLE=1**（F2P 20 / P2P 129） |
| 离线 Docker（`--network=none`） | **NOP=0 / ORACLE=1**（官方编排器 `verify_agent_patch.py --docker`） |
| `validate_proposals` / `check_skill_language` / `check_package` | 全部通过（仅 Windows exec 位 2 项为环境限制，Linux 复核 PASS） |
| 飞书去重登记 | record_id `recvwv3v2JNGvk`，读回 = **不重复**、标注员 `wff` |
| Trae 工作区 | `work/2026-09-28-4-networkx-pareto-paths/trae-runs-v1/`（两个仓库均 `HEAD=72a2b821…` 基线，改动数 0，`upstream_sha256=7a027ddd…`） |

---

## 执行步骤

### 第 1 步 · Trae 跑 no-skill

1. 打开 **Trae CN**（或 TraeCode IDE，见文末"用哪个产品"），模型选 **`Doubao-Seed-Evolving`**。
2. 「打开文件夹」→
   `C:\Users\Administrator\Desktop\OBM\work\2026-09-28-4-networkx-pareto-paths\trae-runs-v1\4-no-skill\4-no-repo`
   - ⚠️ 打开的是**仓库目录 `4-no-repo`**，不是它的上一层 `4-no-skill`。
   - ⚠️ **绝不要用隔离 worktree / 沙箱副本模式**——判分读的是这个目录的 `git diff`，用隔离副本会得到空 diff。
3. 用编辑器打开题面 `...\4-no-skill\PROMPT.md`（5539 字节，**在仓库目录之外**），**全选复制** → 粘进 Agent 对话框 → 发送。
4. 等它自己改码、跑测试、给出最终回复（**中途不要打断**）。
5. 完成后告诉我，或直接执行第 2 步。

### 第 2 步 · 判分 no-skill（期望 reward=0）

在 WSL 里跑：

```bash
tr -d '\r' < /mnt/c/Users/Administrator/Desktop/OBM/work/2026-09-28-4-networkx-pareto-paths/tools/run_post_trae.sh | bash -s -- no-skill
```

- 期望：`reward=0`、退出码 **10**（`ready_for_with_skill`）。
- 若 `reward=1`（exit 20）→ **题目太简单，需要加难**（这正是上一题 2026-09-28-3 的结局），流水线会中止，我们再议。
- 若退出码 22 → 基础设施错误，把输出发我。

### 第 3 步 · Trae 跑 with-skill

1. 「打开文件夹」→ `...\trae-runs-v1\4-with-repo\4-with-repo`
2. 复制 `...\4-with-repo\PROMPT.md`（14929 字节，**在题目后多附了「## 专家解题思路」**）全文 → 粘贴 → 发送。
3. 等完成。

### 第 4 步 · 一键收尾（判分 + 质检 + 打包 + 包检）

```bash
tr -d '\r' < /mnt/c/Users/Administrator/Desktop/OBM/work/2026-09-28-4-networkx-pareto-paths/tools/run_post_trae.sh | bash -s -- all
```

期望一路到 `output/deepSWE_2026-09-28-4-networkx-pareto-paths.zip`。

### 第 5 步 · 飞书提交

按 `skills/obm-task-production/references/feishu-submission.md` 提交（需你驱动）。

---

## 关于 `run_post_trae.sh`

它覆盖流程图里 **第 4/5 步的"判分" + 第 6 步全部**（FINAL_CHECK + zip + 对 zip 跑 check_package），**不含**第 7 步飞书提交，也**不代替**你在 Trae 里跑题。

| 步骤 | 是否覆盖 |
|---|---|
| 4 · Trae no-skill 双跑 | ❌ 题要你在 Trae 里跑；它只做**判分** |
| 5 · Trae with-skill 双跑 | ❌ 同上 |
| 6 · 最终质检 + 打包 | ✅ 全自动 |
| 7 · 飞书提交 | ❌ 需你驱动 |

特性：
- **任何一步不达标即中止**，不会伪造实验结果。
- **可重入**：已有有效 no-skill（reward=0）会跳过重复判分；已是 `passed` 会跳过 with-skill 判分。所以「先 `no-skill`、再 `all`」是安全的。
- **防误判**：工作区无任何代码改动时判定「Trae 还没跑」并拦下（用与 `create_patch` 完全相同的口径）；确属 Agent 失败未改码时加 `--force` 继续。
- 指定工具名（写入 `EXPERIMENT_RESULT.json` 的 `agent.runner`）：
  ```bash
  tr -d '\r' < .../run_post_trae.sh | bash -s -- all "" "TRAECODE"
  # 或环境变量：RUNNER="TRAE SOLO CN" bash /root/run_post_trae.sh all
  ```

---

## 卡点预防

- **`PROMPT.md` 找不到**：它在**仓库目录之外**（`4-no-skill\PROMPT.md`），Trae 打开 `4-no-repo` 后侧边栏看不到它——用系统编辑器/资源管理器单独打开即可。也可以直接看我给你的文件卡片。
- **请勿把 `PROMPT.md` 复制进仓库目录**（上题复制后被要求还原）：它会计入未跟踪文件，虽已排除 git diff，但没必要引入变数。
- **跑之前先确认** Trae 不是隔离 worktree 模式（见第 1 步第 2 条）。

---

## 用哪个产品

| 产品 | 可用性 |
|---|---|
| **TraeCode IDE（打开文件夹）** | ✅ 首选，改动落在原目录 |
| **TraeCode Plugin** | ✅ 同上 |
| **TraeCode CLI** | ⚠️ `-w/--worktree` 是**隔离**模式，本题**别加**；且需企业旗舰套餐 |
| **TRAE SOLO / TRAE Work** | ⚠️ 默认倾向隔离工作区，必须确认它把改动写进了**当前仓库目录** |

**严格说——只要能被你驱动、能改这两个仓库、且用 `Doubao-Seed-Evolving` 的 agentic 工具都可以**，不限于 Trae（"Trae" 只是 OBM 默认载体；本地链路只对"仓库 diff + 独立 verifier"负责，不校验是谁跑的）。唯一硬性约束是：**两组对照实验必须真实发生、可核验，不能伪造**。
