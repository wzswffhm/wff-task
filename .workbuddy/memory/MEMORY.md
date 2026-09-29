# MEMORY.md — wff-task 项目长期记忆

## 仓库架构（2026-09-29 重构后）

**唯一仓库**：`git@github.com:wzswffhm/wff-task.git`（**PRIVATE**，分支 `main`）

工作目录 `C:\Users\Administrator\Desktop\wff-task` **整体即该仓库根**。所有内容由这一个仓库统一管理。

| 目录 | 内容 |
|---|---|
| `harbor-16/` | **harbor-16** skill 产物：内部 RL 题包（`zq*` 批次、`block-storage-*`） |
| `harbor-sota/` | **harbor-sota** skill 产物：外发供应商题包（`wff-eval-*`，含 gating/graded/golden_output） |
| `OBM/` | `Benchmark/`（第三方数据集）、`work/`（实验产物）、`output/`（结果） |
| `skills/` | **★ 唯一的 skill 目录**：`OBM`、`harbor-16`、`harbor-sota`、`harbor-work`、`caveman` |
| `.workbuddy/` | 会话记忆 |

**注意**：原 `Harbor/` 文件夹已于 2026-09-29 删除（其中的 skill 副本、脚本、文档已归档至 `skills/harbor-16/workspace/`）。skill 只保留在 `skills/` 一处，**不要再从其他位置放置 skill 副本**。

## skills/ 目录中的 skill

| skill | 说明 |
|---|---|
| `OBM` | 统一 OBM skill（含 subskills：production-trae、review、run-qc） |
| `harbor-16` | Harbor 内部 RL 出题全流程（+ `workspace/` 归档的脚本与文档） |
| `harbor-sota` | 外发评测题包生产（规范 v4） |
| `harbor-work` | 龙猫-阿里 A/B 标注 |
| `caveman` | 精简输出模式 |

**skill `name` 字段规范**：必须用小写连字符形式（如 `harbor-16`），**不可含空格**（如 `Harbor 16` 会导致调用失败）。

## skills/OBM 统一 skill

原 4 个 `obm-*` 目录已整合为单一 `OBM` skill（原目录已删除）。结构：

- 根目录 = **production 主流程**（OpenAI 兼容接口版），frontmatter `name: OBM`
- `subskills/production-trae/` = Trae 手动版生产（备选，与主流程**互斥**，references 不同）
- `subskills/review/` = proposal 内容审查
- `subskills/run-qc/` = 本地跑题与质检

路由表在 `skills/OBM/SKILL.md`，安装说明在 `skills/OBM/README.md`。
子流程 frontmatter 名称已加 `OBM-` 前缀（`OBM-production-trae`、`OBM-review`、`OBM-run-qc`）。

## Harbor 内容分类判定依据

区分内部 RL 题包与外发题包：

| 特征 | harbor-16（内部 RL） | harbor-sota（外发供应商） |
|---|---|---|
| `task.toml` schema | 1.3 | 1.4 |
| 评分 | `tests/quality.toml` + pytest 程序化 | `tests/graded/judge.toml` + `tests/gating/gating.toml` |
| 参考答案 | `solution/`（oracle.patch） | `solution/golden_output/` + `tests/golden_output/` |
| 命名 | `zq*` 飞书作业号 / assignment_id | 供应商+领域+分类+时间，L2~L5 分级 |

详见 `Harbor/分类说明.md`。

## ⚠️ 安全

`Harbor/check.md` 含**明文 API Key**（阿里云 MaaS OPENAI_API_KEY），已随仓库推送至 GitHub 私有仓库。用户当时选择不处理，**建议轮换该 Key**。

**重要**：`Harbor/` 与 `skills/` 原本是独立 git 仓库，其内层 `.git` 已按需求移除，**现为普通目录**。原远程 `wzswffhm/harbor` 与 `wzswffhm/wff-skills` 已不再由本地同步。

## Git 约定

- **认证**：SSH（`~/.ssh/id_ed25519`，绑定账号 `wzswffhm`）。**绝不改回 HTTPS**——本机 `credential.helper` 存在双配置冲突（PortableGit 的 `helper-selector` + GCM），HTTPS 会反复弹出 CredentialHelperSelector。
- **必须开启 `core.longpaths=true`**：`Harbor/` 内存在超过 260 字符的深层路径，否则 checkout 失败。
- `core.autocrlf=false`（避免 CRLF 批量改写）。
- 工作流：`git add -A && git commit -m "..." && git push`。
- **新增内容时必须先确认无内层 `.git`**：内层仓库会被记录为 gitlink 占位符（模式 `160000`），内容不会入库。清理后需 `git rm -r --cached . -f` 再重新 `git add`。

## 大文件约束

`OBM/Benchmark/terminal-bench-main/` 下有 3 个文件超过 GitHub 建议的 50MB：

- `tasks/live-database-cutover/environment/mysql/datadir.tar.zst` — **94.68 MB**（逼近 100MB 硬限制，再加 5MB 就会被拒）
- `tasks/gsea-proteomics/environment/data/GSEA_Linux_4.4.0.zip` — 62 MB
- `tasks/atrx-vep-crispr/**/ensembl-vep-release-115.tar.gz` — 60 MB

**风险**：今后若新增超 100MB 的单文件，push 会被直接拒绝，需改用 Git LFS。

## 排除项

- `OBM/.venv/` — venv 自带 `.gitignore`（内容 `*`）自动排除。同 `node_modules`，可由 `pip install` 重建，且含硬编码绝对路径。
- `.git-archives/`、`.DS_Store`、`__pycache__/`、`*.pyc` 等。

## 本机 Git 环境

- 存在两套 Git：`C:\Program Files\Git` 与 WorkBuddy 便携版 `~/.workbuddy/binaries/PortableGit/versions/1.2.0`。
- `user.name=v_wffanwang` / `user.email=v_wffanwang@tencent.com`。
- **gh CLI** 已装于 `C:\Program Files\GitHub CLI\gh.exe`（v2.101.0），**不在默认 PATH**，需 `export PATH="/c/Program Files/GitHub CLI:$PATH"`。
- `reg.exe` 被安全策略列为黑名单程序，无法执行。

## 用户偏好

- 中文交流，偏好结构化表格与结论先行。
- 涉及全局配置或破坏性操作时，希望先了解影响面再决定。
- 倾向"全部推送、不做额外处理"的直给风格，但接受必要的技术约束说明。
