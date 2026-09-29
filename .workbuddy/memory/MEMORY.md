# MEMORY.md — wff-task 项目长期记忆

## 仓库架构（2026-09-29 重构后）

**唯一仓库**：`git@github.com:wzswffhm/wff-task.git`（**PRIVATE**，分支 `main`）

工作目录 `C:\Users\Administrator\Desktop\wff-task` **整体即该仓库根**。所有内容由这一个仓库统一管理。

| 目录 | 内容 |
|---|---|
| `Harbor/` | harbor 题包工作区（原 harbor 仓库，已合并） |
| `OBM/` | `Benchmark/`（第三方数据集）、`work/`（实验产物）、`output/`（结果） |
| `skills/` | 8 套 skill：`harbor-16`、`harbor-sota`、`harbor-work`、`caveman`、`obm-*`（4 套） |
| `.workbuddy/` | 会话记忆 |

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
