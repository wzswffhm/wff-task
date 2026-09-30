# MEMORY.md — wff-task 项目长期记忆

> 最后整理：2026-09-30。全部内容由**一个** git 仓库统一管理。

## 1. 仓库与目录架构

**唯一仓库**：`git@github.com:wzswffhm/wff-task.git`（PRIVATE，分支 `main`）。
工作目录 `C:\Users\Administrator\Desktop\wff-task` **整体即仓库根**。

| 目录 | 内容 |
|---|---|
| `OBM/`、`harbor-16/`、`harbor-sota/` | **题包类型目录**（某 skill 的题包集合），可扩展 |
| `deliverables/` | 解析材料产出区：`<YYYY-MM-DD>_<材料名>/`，材料名保持原拼写 |
| `skills/` | 唯一的 skill 目录 |
| `.workbuddy/` | 会话记忆 |

**待登记**的题包类型目录（生产时再建，并登记于根 `README.md`）：
`harbor-windows` → `windows-harbor/`；`harbor-legal` → `legal/`；`harbor-finance` → `finance/`。

## 2. 目录纪律（由 skill `wff-workspace-discipline` 约束）

- **铁律一 · 根目录单一制**：根级只允许 `README.md`、`.gitignore`、`deliverables/`、`skills/` + 已登记题包类型目录；禁止备份/临时目录。
- **铁律二 · 题包类型目录**：根部**只放公用**配置/脚本；题目专属内容进**独立子目录**（一题一目录），禁止上浮。
- **铁律三 · deliverables 命名**：解析产出放 `deliverables/<date>_<材料名>/`；日期用 `date +%F` 取真实值；材料名**保持原拼写**（`windwos` 不"纠正"为 `windows`）。

**历史**：原 `Harbor/` 已于 2026-09-29 删除，内容归档至 `skills/harbor-16/workspace/`。
skill **只保留在 `skills/` 一处**，不要再从其他地方放副本。

## 3. skills/ 清单与注册机制

| skill | 说明 |
|---|---|
| `OBM` | 统一 OBM skill（subskills：`production-trae` / `review` / `run-qc`） |
| `harbor-16` | Harbor 内部 RL 出题（`zq*` 批次，pytest 程序化评分） |
| `harbor-sota` | 外发供应商题包（**旧版规范 v4**，`judge.toml`+`gating.toml`） |
| `harbor-windows` | Windows 专项 Coding Bench（二值判分） |
| `harbor-legal` | **法律领域出题**（Law1–Law6）+ 内联交付标准 |
| `harbor-finance` | **金融领域出题**（专项 1000 + Weakness 1000）+ 内联交付标准 |
| `harbor-work` | 龙猫-阿里 A/B 标注 |
| `caveman` | 精简输出模式 |
| `wff-workspace-discipline` | 落盘纪律 |

**frontmatter `name` 必须小写连字符形式**（`Harbor 16` 含空格会导致调用失败）。

### ★ 注册机制：目录联结（junction）

`skills/` **不是** WorkBuddy 的扫描路径；可自动发现的只有 `~/.workbuddy/skills/`（用户级）与 `{项目}/.workbuddy/skills/`（项目级）。

`~/.workbuddy/skills/` 下 9 个条目**全部是指向 `wff-task/skills/<name>` 的 junction**：
`OBM`、`caveman`、`harbor-16`、`harbor-sota`、`harbor-windows`、`harbor-work`、
`wff-workspace-discipline`、`harbor-legal`、`harbor-finance`。

- **创建**：`New-Item -ItemType Junction -Path "<链接>" -Target "<目标>"`（无需管理员权限，2026-09-30 实测可用）
  - ⚠️ `cmd /c mklink /J` **已被安全策略阻断**；Git Bash 也不可用（`/J` 被当路径转换，报 `无效开关 - "C:"`）。
- **删除链接**：`[System.IO.Directory]::Delete($link, $false)` —— 只删链接，不递归删目标。
- **好处**：改仓库文件即改用户级 skill，零同步零漂移；`git status` 干净。
- **禁止复制同步**：历史 `skills/harbor-16/workspace/sync-skills.ps1` 三向 copy 已弃用（复制必然漂移）。

已清理的重复 skill（2026-09-29 精确比对后删除）：`harbor-skill` → 由 `harbor-16` 覆盖；
`harbor-eval-bundle` → 由 `harbor-sota` 覆盖。`agent-created-skills.json` 已重置为空数组。

## 4. 出题类 skill 要点速查

### 4.1 法律 / 金融（2026-09-30 新建，取代 6 个细分 skill）

**粒度原则**：skill 对齐**规范文件**，不对齐题型细分；**不为交付标准单设 skill**。

| skill | 规范来源 | 结构 |
|---|---|---|
| `harbor-legal` | 《RL0-1 数据生产规范（法律）》 | `references/01–03`（出题设计）+ `delivery/00–08`+`templates/`+`assets/`（交付标准，内联） |
| `harbor-finance` | 《基于 weakness 和 skill 的数据构造方案（金融）》 | `references/01–08`（总纲/5 类专项/weakness/C 级/埋点 rubric）+ 同上 `delivery/` |

- **`delivery/` 在两 skill 下各存一份且必须逐字一致**（校验：`diff -r skills/harbor-legal/delivery skills/harbor-finance/delivery`）。
- 原独立 skill `harbor-rewardkit` 已内联并删除（不再存在于 `skills/` 与 junction 列表）。
- **法律口径映射（高频返修点）**：法律规范的 `weight = -3/-7/-10` 交付时须改写为 `weight = 3.0/7.0/10.0` + `negate = true`（交付态**严禁负 weight**）；`type=Gradient`+`levels{1,.75,.5,.25,0}` → `type=likert`+`points=5`（judge 1–5 归一化 `(raw−1)/4` 恰对应）。两式数学等价。
- **金融配额**：专项 1000（5 类 × 200）+ Weakness 1000；每类 weakness ∈[50,250]；C1–C5 配比 120/250/350/180/100；同一知识点出题 <3 道。
- 共同验收门：参考答案 >0.85；三模型均分 <0.7 且至少一个模型有得分；人工质检发现 hack 直接打回。

### 4.2 harbor-windows（Windows 专项 Coding Bench）

原名 `windows-coding-bench`，2026-09-29 改名。按《Windows 专项 Coding Bench 数据采购》（`windwos-第二版`）生产。

```
skills/harbor-windows/
├── SKILL.md                       # 10 步流程 + 交付物清单 + 10 陷阱 + 14 否决
├── references/01-spec-requirements.md ~ 09-gz-package-analysis.md
├── scripts/validate_package.py    # 结构与身份一致性校验（PASS/FAIL/FLAG）
├── scripts/build_delivery_extras.py
├── scripts/run_model_validation.py  # ★ 4 模型自动验证 + 区分度准入
├── assets/harbor-skeleton/        # 五件套骨架（可复用 grade.py / test.ps1 / Dockerfile）
└── assets/metadata-templates/
```

**三条底线**：① Windows 价值反事实判定（换 Linux 后实现/根因/Evaluator 若不变 → 淘汰）；
② 二值判分（required F2P+P2P 全过=1；异常=INVALID，**不得伪装成 0 分**）；
③ 身份唯一（`task_id + task_version + task_hash`；镜像 tag 不是身份，须另存 Digest）。

**可复用模式**：`===SWELIVE_INVALID <reason>===` 标记、reward 三件套校验、`parser(log)->{test:status}` 契约、
`verification_evidence` 3+3 声明块、`run_evidence` 六字段、`UV_OFFLINE=1` 离线镜像。

**多模型端点**（`run_model_validation.py`）：

| key | base_url | model | 次数 |
|---|---|---|---|
| `qwen3.8-max` | `https://llm-cz4pcezs463b102x.cn-beijing.maas.aliyuncs.com/apps/anthropic` | `qwen3.8-max` | 3 |
| `opus-5` | `https://api.blvr.top` | `claude-opus-5` | 3 |
| `glm-5.3` | 同 aliyun | `GLM-5.3` | 1 |
| `kimi-k3` | 同 aliyun | `Kimi K3` | 1 |

- 协议 Anthropic Messages（`POST {base_url}/v1/messages`，`x-api-key` + `anthropic-version: 2023-06-01`）
- **aliyun base_url 必须带 `/apps/anthropic` 后缀**，否则 404
- 凭据环境变量：`HARBOR_WINDOWS_ALIYUN_KEY`、`HARBOR_WINDOWS_BLVR_KEY`
- 脚本是**模型调用层**，不是评测沙箱；正式分须由平台 harness 回填

### 4.3 OBM

原 4 个 `obm-*` 目录整合为单一 `OBM` skill：根目录 = production 主流程（OpenAI 兼容接口版）；
`subskills/production-trae`（Trae 手动版，与主流程互斥）/ `subskills/review` / `subskills/run-qc`。
子流程 frontmatter 已加 `OBM-` 前缀。

## 5. Harbor 内容分类（内部 RL vs 外发）

| 特征 | `harbor-16`（内部 RL） | `harbor-sota`（外发 v4） |
|---|---|---|
| `task.toml` schema | 1.3 | 1.4 |
| 评分 | `tests/quality.toml` + pytest | `tests/graded/judge.toml` + `tests/gating/gating.toml` |
| 参考答案 | `solution/`（oracle.patch） | `solution/golden_output/` + `tests/golden_output/` |
| 命名 | `zq*` 飞书作业号 | 供应商+领域+分类+时间，L2~L5 |

> **rewardkit 20260913（法律/金融用）与 v4 口径不同，同一批次内不得混用。**

## 6. ⚠️ 安全：真实明文密钥位置（2026-09-29 全库扫描，已推送至私有仓库）

| # | 位置 | 前缀 | 类型 |
|---|---|---|---|
| 1 | `skills/harbor-windows/scripts/run_model_validation.py`（63/89/102 行） | `sk-ws-H.PIDYYYX` | aliyun MaaS |
| 2 | 同上（76 行） | `sk-l8hraN17` | blvr（Opus） |
| 3 | `skills/harbor-16/workspace/docs/check.md`（3 行） | `sk-ws-H.ERLPMXH` | aliyun（旧） |
| 4 | `OBM/model.env`（`key=`） | `ark-9bd32e64` | 火山方舟 |
| 5 | `OBM/feishu-gsb.toml` | `cli_aaf0…` / `ou_35041…` | 飞书凭据 |

- **仅端点无 Key（低风险）**：`skills/harbor-16/references/notes-22.md`、`ops-notes.md`、`skills/OBM/subskills/run-qc/config/obm.paths.json`。
- **合规非泄漏**：`skills/harbor-sota/` 全程用 `${OPENAI_API_KEY}` / `${JUDGE_GATEWAY}` 占位符，规范明令逐字保留。
- 扫描须排除 `OBM/.venv/`（`openai` 包源码含大量 `api_key` 字样，是库代码非凭据）。
- 扫描命令与轮换建议见 `skills/harbor-windows/references/10-api-keys-and-endpoints.md`。

## 7. Git 约定

- **认证走 SSH**（`~/.ssh/id_ed25519`，账号 `wzswffhm`）。**绝不改回 HTTPS**——本机 `credential.helper` 双配置冲突（PortableGit `helper-selector` + GCM）会反复弹窗。
- 必须开 `core.longpaths=true`（存在 >260 字符深层路径）；`core.autocrlf=false`。
- 工作流：`git add -A && git commit -m "..." && git push`
  - **⚠️ 仅在用户明确要求提交时才执行**；否则改动只留在工作区。
- **新增内容前先确认无内层 `.git`**（否则被记为 gitlink 占位符，内容不入库）；清理后需 `git rm -r --cached . -f` 再重新 `git add`。
- 本机存在两套 Git；`user.name=v_wffanwang` / `user.email=v_wffanwang@tencent.com`。
- **gh CLI** 在 `C:\Program Files\GitHub CLI\gh.exe`，不在默认 PATH，需 `export PATH="/c/Program Files/GitHub CLI:$PATH"`。
- `reg.exe` 被安全策略列入黑名单，无法执行。

## 8. 大文件约束

`OBM/Benchmark/terminal-bench-main/` 下 3 个超 50MB 文件：
`mysql/datadir.tar.zst` **94.68 MB**（逼近 100MB 硬限）、`GSEA_Linux_4.4.0.zip` 62 MB、`ensembl-vep-release-115.tar.gz` 60 MB。
**风险**：今后新增 >100MB 单文件 push 会被拒，需改用 Git LFS。

## 9. 排除项

`OBM/.venv/`（自带 `.gitignore` 内容 `*`，可 `pip install` 重建，且含硬编码绝对路径）、
`.git-archives/`、`.DS_Store`、`__pycache__/`、`*.pyc`。

## 10. 文档与术语纪律（2026-09-30 教训）

- **规范原文术语 ≠ 自造编号，必须区分**：
  凡自行归纳的编号（如交付门禁 `G1–G6`、Skill Discovery 抓手 `D1–D3`）**必须在首次出现处标注"归纳编号，规范原文无此表述"**，
  否则后续会被当作规范要求引用（已发生：`G1–G6` 在三份 PDF 中均 0 命中）。
- **断言"某结论出自规范"前先 `grep` 原文定位行号**，不要凭归纳记忆断言。
- **同一文档内禁止同一编号有两种含义**（曾发生：交付门禁 G1–G5 vs Skill 生成/编辑五形态 G1–G5；后者已改 `S1–S5`）。
- 两个 skill 的 `delivery/` 为**同源双份**，改一处须同步另一处并用 `diff -r` 校验。

## 11. 用户偏好

- 中文交流，**结论先行 + 结构化表格**；偏好紧凑可执行的说明。
- 涉及全局配置或破坏性操作时，希望先了解影响面再决定。
- 倾向"直接做完、不做额外处理"的直给风格，但接受必要的技术约束说明。
- **不要自动提交代码**：改完只本地落盘，**等用户明确说"提交/推送"**才 commit + push（2026-09-29 明确要求）。
- **删除/清理操作不必逐次确认**（已授权直接执行）。
- 能力/凭据受限时，倾向"先把工具链做完、待条件就绪即可跑通"，而非阻塞等待。
