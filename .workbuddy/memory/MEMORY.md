# MEMORY.md — wff-task 项目长期记忆

## 仓库架构（2026-09-29 重构后）

**唯一仓库**：`git@github.com:wzswffhm/wff-task.git`（**PRIVATE**，分支 `main`）

工作目录 `C:\Users\Administrator\Desktop\wff-task` **整体即该仓库根**。所有内容由这一个仓库统一管理。

| 目录 | 内容 |
|---|---|
| `harbor-16/` | **题包类型目录**：**harbor-16** skill 产物（内部 RL 题包，`zq*` 批次、`block-storage-*`） |
| `harbor-sota/` | **题包类型目录**：**harbor-sota** skill 产物（外发供应商题包 `wff-eval-*`） |
| `OBM/` | **题包类型目录**：`Benchmark/`、`work/`、`output/`；根部只放公用配置/脚本 |
| `deliverables/` | **★ 解析材料产出区**：`<YYYY-MM-DD>_<材料名>/`，材料名保持原拼写 |
| `skills/` | **★ 唯一的 skill 目录**：`OBM`、`harbor-16`、`harbor-sota`、`harbor-work`、`caveman`、`wff-workspace-discipline`、`harbor-windows` |
| `.workbuddy/` | 会话记忆 |

> **待登记**：`harbor-windows` 对应的题包类型目录（建议 `windows-harbor/`）尚未创建，生产时再建并登记于根 `README.md`。

## 目录纪律（强制，由 skill `wff-workspace-discipline` 约束）

**铁律一 · 根目录单一制**：`README.md`、`.gitignore`、`deliverables/`、`skills/` **各只允许一个**。禁止根级备份/临时目录（`X.backup-*`、`X-2/`、`tmp/`）。

**铁律二 · 题包类型目录**：`OBM/`、`harbor-16/`、`harbor-sota/` 是**题包类型目录**（代表某 skill 的题包集合），**可扩展**（如 Windows-Harbor 作业需新建自己的类型目录）。规则：
- 单包 = 类型目录下**独立子目录**，一题一目录
- 类型目录**根部只放公用**配置/脚本/缓存（参考 `OBM/model.env`、`OBM/tools/`）
- 题目专属内容**禁止上浮**到类型目录根部，避免污染其他题包

**铁律三 · deliverables 命名规则**：解析材料产出放 `deliverables/<YYYY-MM-DD>_<材料名>/`：
- 目录名 = **产出日期** + 材料文件名（去扩展名）
- 日期用 `date +%F` 取真实值，不凭记忆推算
- 材料名**保持原拼写**（不改错别字，`windwos` 不纠正成 `windows`）
- 一材料一目录；目录内产物按内容命名，**不强制**与材料同名

**已登记题包类型目录**：`OBM/`、`harbor-16/`、`harbor-sota/`。新增须经确认并登记于根 `README.md`。

**注意**：原 `Harbor/` 文件夹已于 2026-09-29 删除（其中的 skill 副本、脚本、文档已归档至 `skills/harbor-16/workspace/`）。skill 只保留在 `skills/` 一处，**不要再从其他位置放置 skill 副本**。

## skills/ 目录中的 skill

| skill | 说明 |
|---|---|
| `OBM` | 统一 OBM skill（含 subskills：production-trae、review、run-qc） |
| `harbor-16` | Harbor 内部 RL 出题全流程（+ `workspace/` 归档的脚本与文档） |
| `harbor-sota` | 外发评测题包生产（规范 v4） |
| `harbor-work` | 龙猫-阿里 A/B 标注 |
| `caveman` | 精简输出模式 |
| `wff-workspace-discipline` | 落盘纪律（根目录洁净 + 题包类型目录 + deliverables 命名） |
| `harbor-windows` | **Windows 专项 Coding Bench 题包生产**（规范 `windwos-第二版`）+ 校验/脚手架/多模型验证脚本 |

**skill `name` 字段规范**：必须用小写连字符形式（如 `harbor-16`），**不可含空格**（如 `Harbor 16` 会导致调用失败）。

## skills/harbor-windows（Windows 专项 Coding Bench）

原名 `windows-coding-bench`，2026-09-29 改名为 `harbor-windows`（与 `harbor-16`/`harbor-sota` 命名风格统一）。
按《Windows 专项 Coding Bench 数据采购》（`windwos-第二版`，替代 v1.0.2）生产标准 Harbor Task。

```
skills/harbor-windows/
├── SKILL.md                          # 主入口：10 步生产流程 + 交付物清单 + 10 陷阱 + 14 否决
├── references/01-spec-requirements.md ~ 09-gz-package-analysis.md
├── scripts/validate_package.py       # 题包结构与身份一致性校验（PASS/FAIL/FLAG）
├── scripts/build_delivery_extras.py  # 批量生成 delivery-extras 骨架
├── scripts/run_model_validation.py   # ★ 4 模型自动化验证 + 区分度准入计算
├── scripts/model_endpoints.template.json  # 端点/凭据配置模板
├── scripts/README.md                 # 三脚本完整用法
├── assets/harbor-skeleton/           # 五件套骨架（可复用 grade.py / test.ps1 / Dockerfile）
└── assets/metadata-templates/        # 伴随材料 JSON 模板
```

**三条底线**：① Windows 价值反事实判定（换 Linux 后实现/根因/Evaluator 若不变 → 淘汰）；② 二值判分（required F2P+P2P 全过=1，否则=0；异常=INVALID，**不得伪装成 0 分**）；③ 身份唯一（`task_id + task_version + task_hash`；镜像 tag 不是身份，须另存 Digest）。

**可复用模式（来自实测 27 题供应商包）**：`===SWELIVE_INVALID <reason>===` 标记、reward 三件套完整性校验、`parser(log)->{test:status}` 契约、`verification_evidence` 3+3 声明块、`run_evidence` 六字段、`UV_OFFLINE=1` 离线镜像、非 wall-clock 基线 commit。

### 多模型验证端点（`run_model_validation.py`）

| key | label | base_url | model | 次数 |
|---|---|---|---|---|
| `qwen3.8-max` | Qwen3.8-Max-0902 | `https://llm-cz4pcezs463b102x.cn-beijing.maas.aliyuncs.com/apps/anthropic` | `qwen3.8-max` | 3 |
| `opus-5` | Opus 5 | `https://api.blvr.top` | `claude-opus-5` | 3 |
| `glm-5.3` | GLM-5.3 | 同 aliyun | `GLM-5.3` | 1 |
| `kimi-k3` | Kimi K3 | 同 aliyun | `Kimi K3` | 1 |

- 协议 Anthropic Messages（`POST {base_url}/v1/messages`，`x-api-key` + `anthropic-version: 2023-06-01`）
- **aliyun base_url 必须带 `/apps/anthropic` 后缀**，否则 404
- 凭据环境变量：`HARBOR_WINDOWS_ALIYUN_KEY`（3 个 aliyun 模型共用）、`HARBOR_WINDOWS_BLVR_KEY`
- **脚本是"模型调用层"，不是评测沙箱**：只发起调用/存轨迹/区分 VALID-INVALID/算区分度；
  `per_testcase.json` 初值 `NOT_RUN`、`report.json.score` 初值 `null`，**正式分须由平台 harness 回填**
- 依赖 `httpx`，已装于 `C:\Users\Administrator\.workbuddy\binaries\python\envs\default`

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

## ⚠️ 安全：真实明文密钥的 5 个位置（2026-09-29 全库扫描）

**已推送至 GitHub 私有仓库 `wzswffhm/wff-task`**：

| # | 位置 | 密钥前缀 | 类型 |
|---|---|---|---|
| 1 | `skills/harbor-windows/scripts/run_model_validation.py`（第 63/89/102 行） | `sk-ws-H.PIDYYYX` | aliyun MaaS（3 模型共用） |
| 2 | 同上（第 76 行） | `sk-l8hraN17` | blvr（Opus） |
| 3 | `skills/harbor-16/workspace/docs/check.md`（第 3 行） | `sk-ws-H.ERLPMXH` | aliyun MaaS（旧） |
| 4 | `OBM/model.env`（`key=`） | `ark-9bd32e64` | 火山方舟 |
| 5 | `OBM/feishu-gsb.toml` | `cli_aaf0…` / `ou_35041…` | 飞书应用凭据 |

**仅为端点（无 Key，低风险）**：`skills/harbor-16/references/notes-22.md`、`ops-notes.md`
（`llm-sn32yenb08wvkx41…compatible-mode/v1`）、`skills/OBM/subskills/run-qc/config/obm.paths.json`（`ark…/api/plan/v3/`）。

**合规做法（不是泄漏）**：`skills/harbor-sota/` 全程用 `${OPENAI_API_KEY}` / `${OPENAI_BASE_URL}` / `${JUDGE_GATEWAY}` 占位符，规范明令逐字保留。

详见 `skills/harbor-windows/references/10-api-keys-and-endpoints.md`（含扫描命令与轮换建议）。

> 排除项：`OBM/.venv/` 下 `openai` 包源码含大量 `api_key` 字样，是库代码非凭据，扫描时须 `grep -v "\.venv/"`。

**历史**：原 `Harbor/check.md` 含明文 Key，已随 `Harbor/` 删除并归档至 `skills/harbor-16/workspace/docs/check.md`（即上表第 3 项）。
`Harbor/` 与 `skills/` 原本是独立 git 仓库，内层 `.git` 已移除，**现为普通目录**；原远程 `wzswffhm/harbor` 与 `wzswffhm/wff-skills` 已不再由本地同步。

## Git 约定

- **认证**：SSH（`~/.ssh/id_ed25519`，绑定账号 `wzswffhm`）。**绝不改回 HTTPS**——本机 `credential.helper` 存在双配置冲突（PortableGit 的 `helper-selector` + GCM），HTTPS 会反复弹出 CredentialHelperSelector。
- **必须开启 `core.longpaths=true`**：`Harbor/` 内存在超过 260 字符的深层路径，否则 checkout 失败。
- `core.autocrlf=false`（避免 CRLF 批量改写）。
- 工作流：`git add -A && git commit -m "..." && git push`。
  - **⚠️ 仅在用户明确要求提交时才执行**；否则改动只留在工作区（见「用户偏好」）。
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
- **不要自动提交代码**：改完文件后**只本地落盘**，**必须等用户明确说"提交/推送"才 commit + push**。
  （2026-09-29 用户明确要求；此前默认改完即提交的行为需纠正。）
- **删除/清理操作不必逐次确认**：用户已明确授权直接执行（2026-09-29）。
- 遇到能力/凭据受限时，倾向"先把工具链做完、待条件就绪即可跑通"，而非阻塞等待。
