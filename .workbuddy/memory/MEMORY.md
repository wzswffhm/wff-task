# MEMORY.md — wff-task 项目长期记忆

## 目录职责

- `skills/` — 各套 skill 的集合目录，**本身即 `wzswffhm/wff-skills` 私有仓库的工作副本**（仓库根 = skills 目录）。
- `OBM/` — 任务/实验相关代码与数据（约 5900 文件）。

## skills/ 仓库约定

- 远程：`git@github.com:wzswffhm/wff-skills.git`（分支 `main`，**私有仓库**）。
- 认证方式：**SSH**（`~/.ssh/id_ed25519`）。**不要改回 HTTPS**，否则会触发 CredentialHelperSelector 反复弹窗。
- 工作流：`git add -A && git commit -m "描述改动" && git push`。`git pull` 已配置为 merge（`pull.rebase=false`）。
- 目录结构：每个 skill 一个顶层目录，内含带 `name` + `description` frontmatter 的 `SKILL.md`。
- 当前 skill 清单：`caveman`、`harbor-16`、`harbor-sota`、`harbor-work`、`obm-review-skills`、`obm-run-qc-bundle`、`obm-task-production`、`obm-task-production-openai`。
- `.gitignore` 已排除：`.DS_Store`、`Thumbs.db`、`__pycache__/`、`*.py[cod]`、`.venv/`、`node_modules/`、`.vscode/`、`.idea/`、`*.log`、`*.tmp`。

## 本机 Git 环境注意点

- `credential.helper` 存在**双配置冲突**：PortableGit 系统级 gitconfig 的 `helper-selector` + `~/.gitconfig` 中指向 PortableGit 的 `git-credential-manager.exe`。
- 该冲突会导致使用 **HTTPS 远程**时反复弹出凭据选择窗口。涉及 `git.woa.com` / `gitee.com` 等 HTTPS 远程时需留意（`~/.gitconfig` 已为这两者配置 `provider=generic`）。
- 本机存在两套 Git：`C:\Program Files\Git` 与 WorkBuddy 便携版 `~/.workbuddy/binaries/PortableGit/versions/1.2.0`。`user.name=v_wffanwang` / `user.email=v_wffanwang@tencent.com`。

## 用户偏好

- 中文交流，偏好结构化表格与结论先行。
- 涉及全局配置变更时希望先了解影响面。
