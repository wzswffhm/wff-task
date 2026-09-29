# Trae 执行 SOP + 后处理一键流水线 — 2026-09-28-3-marshmallow-doc-diff

> 本文回答两件事：**Trae 到底怎么跑**，以及**跑完之后 3（FINAL_CHECK）/4（打包）怎么自动完成**。

## 0. 前置（已完成，无需你再做）

- WSL 里 docker 可用（29.1.3），基础镜像已拉取；`python3` 已装 Pillow。
- 两个 Trae 工作区仓库已设 `core.autocrlf=true`（**关键**：NTFS 上整树 CRLF、基线 blob 是 LF，不设它会产出“全仓库换行符 churn”垃圾 patch，判分必错）。
- 修正后的 `verify_agent_patch.py` 会在判分时把 `model.patch` 应用到 `sources/app` 之后再构建（原脚本不应用，见 `PIPELINE-FIXES.md`）。

## 1. 跑 no-skill（必须你在 Trae 里手动做）

1. 打开 **Trae CN 桌面版**，模型选 `Doubao-Seed-Evolving`。
2. 用 Trae **打开文件夹**：
   `C:\Users\Administrator\Desktop\OBM\work\2026-09-28-3-marshmallow-doc-diff\trae-runs-v1\3-no-skill\3-no-repo`
   - ⚠️ 打开的是**仓库目录** `3-no-repo`，不是它的上一层 `3-no-skill`。
3. 打开 `...\3-no-skill\PROMPT.md` 复制**全文**，粘进 Agent 对话框发送。
   - ⚠️ 该文件**在仓库目录之外**，与 `3-no-repo` 同级；Trae 的文件树以打开的仓库目录为根，因此看不到它。请用资源管理器 / 记事本 / 编辑器「打开文件」来打开，不要指望在 Trae 侧边栏里找到。
4. 等 Agent 自己改代码、跑测试、给出**最终回复**。中途不要打断、不要追加消息、不要点停止/重试。
5. （可选）在 `3-no-skill\RUN_RECORD.md` 记开始/结束时间、轮次。

## 2. 判分 no-skill（一条命令）

```bash
tr -d '\r' < /mnt/c/Users/Administrator/Desktop/OBM/work/2026-09-28-3-marshmallow-doc-diff/tools/run_post_trae.sh \
  | bash -s -- no-skill
```
- 期望：`reward=0`，退出码 `10`（ready_for_with_skill）。
- 若 =1 → 题目太简单（退出码 20）；若工作区没改动 → 脚本会拦下并提示你“Trae 还没跑”。

## 3. 跑 with-skill（同样在 Trae 里手动）

1. 用 Trae **打开文件夹**：
   `...\trae-runs-v1\3-with-repo\3-with-repo`
2. 打开 `...\3-with-repo\PROMPT.md`（同样在仓库目录之外）复制**全文**粘进去——这份在题目后**多附了“## 专家解题思路”**，发送。
3. 等 Agent 给出最终回复。

## 4. 判分 with-skill 并自动完成 3、4（一条命令）

```bash
tr -d '\r' < /mnt/c/Users/Administrator/Desktop/OBM/work/2026-09-28-3-marshmallow-doc-diff/tools/run_post_trae.sh \
  | bash -s -- all
```
`all` 会依次自动做：
| 步骤 | 脚本 | 期望 |
|---|---|---|
| 1 | stage 题包到 ext4 + 补 exec 位 | 755 |
| 2 | `grade_manual_trae.py --mode no-skill` | reward=0, exit 10 |
| 3 | `grade_manual_trae.py --mode with-skill` | reward=1, exit 0 → status=passed |
| 4 | `capture_final_check.py` | `FINAL_CHECK.json.ok=true` |
| 5 | `build_delivery_zip.py` | 产出 `output/deepSWE_2026-09-28-3-marshmallow-doc-diff.zip` |
| 6 | `check_package.py <zip>` | PASS |

任何一步不达标即中止，**不会伪造实验结果**。也可以分步跑：`... -- no-skill | with-skill | final | zip`。

> **`all` 的可重入性**：若 `EXPERIMENT_RESULT.json` 里已有有效的 no-skill（reward=0），`all` 会**跳过**重复判分；若状态已是 `passed`，也会跳过 with-skill 判分。所以先跑过 `-- no-skill` 之后再跑 `all` 是安全的。

### `all` 与流程图步骤的对应

| 流程图步骤 | `all` 是否覆盖 |
|---|---|
| 4 · Trae no-skill **双跑** | ❌ 需你在 Trae GUI 里跑；`all` 只做其中的**判分** |
| 5 · Trae with-skill **双跑** | ❌ 同上；`all` 只做其中的**判分** |
| 6 · 最终质检 + 打包 | ✅ 全部自动 |
| 7 · 飞书提交 | ❌ 不包含，需单独做 |

即：`all` 是「**Trae 两次运行都完成之后**」的一键收尾，覆盖第 4/5 步的判分 + 第 6 步全部；它**不代替**你在 Trae 里跑题，也**不含**飞书提交。

> 之后就是飞书提交（`references/feishu-submission.md`）：写题目文件夹名/编号、benchmark、标注人=wff、状态；上传 ZIP 与 `FINAL_CHECK.png`；读回确认后再把状态改为“待质检”。

## 5. 用哪个产品？（TraeCode / TRAE SOLO(=Work) / 其它）

对本题而言**产品名不重要，能力才重要**。只需要满足四点：

1. 能"打开文件夹"，且**在原目录内改文件**；
2. ⚠️ **不要用隔离 worktree / 沙箱副本模式**——本题判分读的是 `3-no-repo` / `3-with-repo` 两个仓库的 diff；若 Agent 在隔离副本里改，diff 为空，会被判成"没做"（no-skill 与 with-skill 都会是 0，实验作废）；
3. 能选到模型 `Doubao-Seed-Evolving`；
4. 能多轮自主改码 + 跑测试。

对照：

| 产品 | 定位 | 本题注意 |
|---|---|---|
| TraeCode IDE | 编程向 AI IDE | 直接用"打开文件夹"即可，改动落在原目录 ✅ |
| TraeCode Plugin | VS Code/JetBrains 插件 | 同上，只要在打开的仓库里改 |
| TraeCode CLI | 命令行/CI | `-w/--worktree` 是**隔离**模式，本题**不要**加；且需企业旗舰套餐 |
| TRAE SOLO / TRAE Work | 通用 agent（偏"给任务全自动干"） | 默认倾向隔离工作区，需确认改动写到**当前仓库目录** |

**记录口径**：实验记录里的 `agent.runner` 默认写 `Trae CN (user manual)`。若你用的是别的产品，用 `--runner` 覆盖，保持证据真实：

```bash
# 第 3 个参数即 runner
tr -d '\r' < .../run_post_trae.sh | bash -s -- all "" "TRAECODE"
# 或用环境变量
RUNNER="TRAE SOLO CN" bash /root/run_post_trae.sh all
```

## 6. 关于 Trae 的 CLI（可选，需你确认）

TraeCode 确实有非交互 CLI（`traecli -p "..."`、`--allowed-tool`、`--json`、`-w` worktree），但：
- **需要 TRAE 企业版旗舰套餐**；
- OBM `SKILL.md` 明确禁止 Codex 启动/接管/操作 Trae（含 `trae-cn`、界面自动化、heartbeat），当前流程规定由**用户手动**执行。

所以默认仍走手动。若你**有企业旗舰套餐**且**认可偏离该规范**，可在仓库目录内自行执行（我这边不代跑）：
```bash
# 在 3-no-skill/3-no-repo 目录内
traecli --allowed-tool Bash,Edit,MultiEdit,Write -p "$(cat ../PROMPT.md)" --json
```
若要走这条路，我建议改为「traecli 产出的 patch 直接喂给 `verify_agent_patch.py`」，此时就不再需要 `grade_manual_trae.py` 的窗口流程——需要我适配就告诉我。
