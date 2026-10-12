# environment/skills/ 技能包封装规范

> 适用于所有在环境中安装**功能型 Skill** 的题型（Skill Discovery / Skill Generation·Editing / Skill Dependency / Workflow）。
> 当前实现方式是**把技能写入 `environment/skills/` 目录**，由 Dockerfile `COPY` 进镜像。

## 1. 标准目录结构

```text
<题目编号>/
├── task.toml                      # 任务声明
├── instruction.md                 # 显式说明"通过 <skill-name> skill 完成，禁止其它方式"
├── environment/
│   ├── Dockerfile                 # COPY skills/ /skills/   ← skill 在这里被装进环境
│   ├── skills/
│   │   └── <skill-name>/
│   │       ├── SKILL.md           # Anthropic Skill 格式：frontmatter(name/description/compatibility) + 正文 SOP
│   │       ├── scripts/           # read_document.py / propose_edits.py / add_comment.py …
│   │       └── references/        # SKILL.md 引用的补充规则（anchors.md 等）
│   └── input_files/               # 任务输入
├── solution/
│   ├── solve.sh
│   └── golden_output/
└── tests/
    ├── test.sh
    ├── finalize.py
    ├── rubrics.toml
    ├── prompt.md
    └── __golden_output/
```

> 技能目录下的**目录名 = `metadata.skill_set` 里的条目名 = `SKILL.md` frontmatter 的 `name`**，三者必须逐字一致。

## 2. SKILL.md 的写法（决定 skill 是否"不可省略"）

```markdown
---
name: contract-redliner
description: Redline Word (.docx) contracts with native tracked changes and margin comments …
    Use when asked to redline, mark up, revise a .docx legal document — every edit must be a
    real tracked change applied via the bundled scripts, never by rewriting the file.
compatibility: Requires Python 3.10+ with python-docx==1.2.0, docx-revisions, lxml.
---
# Contract Redliner

（正文：分步 SOP、脚本用法、失败恢复、"绝不能用别的方式改文档"的硬规则
这些"特有行为规则 / 阈值 / 映射"就是让 Skill 不可省略的关键）
```

**三条硬性要求**：

1. **frontmatter 三个字段齐备**：`name` / `description` / `compatibility`。
   - `description` 必须写清"**什么时候该用**"（trigger 语义），让模型能判断适用场景。
   - `compatibility` 写明运行前提（Python 版本、依赖包及版本），与 `requirements.txt` 对齐。
2. **正文必须含**：分步 SOP（步骤 + 条件分支 + 完成检查）、脚本用法（命令与参数）、失败恢复路径、**硬规则**（"绝不能用别的方式做 X"）。
3. **必须包含"特有信息"**——否则 skill 只是可有可无的 contextual document：
   - 特殊阈值 / 内部映射规则 / 自定义字段定义 / 业务优先级 / fallback 顺序；
   - 或多个 authoritative source 冲突时的处置规则（如"必须暂停并向用户确认，禁止自行选择"）；
   - 或环境特化 SOP（如 `Draft → Compliance Review → Manager Approval → Publish`，少一步状态即失败）。

## 3. instruction.md 的技能入口写法（强制）

**必须显式列明**（不得只写技能名让 Agent 猜路径）：

```markdown
## 可用技能

本环境已安装以下技能，`SKILL.md` 的容器内绝对路径如下；脚本相对路径以该技能目录为基准：

| 技能 | 适用描述 | SKILL.md 路径 |
| --- | --- | --- |
| `contract-redliner` | 对 .docx 合同进行带修订痕迹的批注与修订 | `/skills/contract-redliner/SKILL.md` |
| `docx-diff-checker` | 对 .docx 做结构与格式校验 | `/skills/docx-diff-checker/SKILL.md` |
```

**并在硬约束段落里显式强调**：

```markdown
Every edit and every comment goes through the contract-redliner skill installed in this
environment — never write `[ADD:…]` / `[DELETE:…]` markup, and never modify the document
by any other means.
```

> ⚠️ **不得泄露**：`expected_skill_dependencies` 中的**必要技能身份**、以及**干扰项技能的身份**。
> 任务书只列"有哪些技能可用"，不暗示"哪个是必需的""哪个是干扰项"——那是模型要自己判断的。

## 4. Dockerfile 中的技能装配

```dockerfile
COPY skills/ /skills/
```

- 技能所需依赖**仍写入 `environment/requirements.txt`**，按原模板在构建期安装。
- 确保**实际 Agent 用户**能读取技能及引用资料、执行脚本：

```dockerfile
RUN chmod -R a+rX /skills
# 若脚本需执行权限
RUN find /skills -name "*.py" -o -name "*.sh" | xargs -r chmod +x
```

## 5. 与 metadata 的对应关系

| metadata 字段 | 对应关系 |
|---|---|
| `skill_set` | 与 `environment/skills/<name>/` **逐一对应**；**可含干扰项**（Skill Discovery 场景） |
| `expected_skill_dependencies` | `skill_set` 的**子集**：不依赖它任务必失败的 skill |
| 发现类任务 | `expected_skill_dependencies` 应**严格小于** `skill_set`（存在故意的无关 skill） |

> **不能仅因安装了技能就认定存在依赖。**

## 6. 自检清单（有 skill 的题）

| # | 检查项 |
|---|---|
| 1 | 技能目录名、`metadata.skill_set` 条目、`SKILL.md` frontmatter `name` **三者一致** |
| 2 | 任务书技能入口表列出了**全部**可用技能的名称、描述、`SKILL.md` 绝对路径与脚本基准目录 |
| 3 | 任务书**未**暗示哪个技能必需 / 哪个是干扰项 |
| 4 | Dockerfile 的 `COPY skills/ /skills/` 路径与任务书中的路径**一致** |
| 5 | 技能依赖写进 `requirements.txt` 并在构建期安装 |
| 6 | 以**实际 Agent 用户**验证：技能文档可读、脚本可执行 |
| 7 | SOP 的**条件分支**与**复核说明**完整（不是单向线性步骤） |
| 8 | `expected_skill_dependencies ⊆ skill_set`、`expected_tool_dependencies ⊆ tool_set` |
| 9 | 技能中的**特有规则**（阈值/映射/优先级/fallback）确实会**影响 final answer** |

> 该检查属于**环境与说明自检**，**不增加过程评分**，也不替代 golden 预检。
