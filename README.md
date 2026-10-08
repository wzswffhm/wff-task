# wff-task

统一的 OBM / Harbor 题包生产与交付工作区。所有内容由单一私有仓库管理：
`git@github.com:wzswffhm/wff-task.git`（PRIVATE）

## 目录结构

```text
wff-task/
├── README.md              # 本文件：工作区总说明（唯一顶层 README）
├── .gitignore             # 唯一的顶层 gitignore，统一管理忽略规则
├── OBM/                   # OBM 题包生产工作区
│   ├── model.env          # 公用：模型 API 配置
│   ├── feishu-gsb.toml    # 公用：飞书配置
│   ├── task-registry.json # 公用：题目登记表
│   ├── tools/             # 公用：跨题复用的构建/登记脚本
│   ├── upstream/          # 公用：上游源码缓存（已移出 Git，本地保留）
│   ├── Benchmark/         # 公用：第三方基准数据集（已移出 Git，本地保留）
│   ├── feishu-records/    # 公用：飞书知识库记录快照
│   ├── _env-records/      # 公用：环境探测与安装/取证记录
│   ├── work/<题号>/        # 每题独立的工作区（中间产物）
│   └── output/<题包>/      # 成品题包（proposal.json + sources/）
├── deliverables/          # ★ 解析材料产出区（<日期>_<材料名>/，材料名保持原拼写）
├── harbor-16/             # 题包类型目录：harbor-16 skill 产物（内部 RL 题包）
├── harbor-sota/           # 题包类型目录：harbor-sota skill 产物（外发供应商题包）
├── harbor-weakness/       # 题包类型目录：harbor-weakness skill 产物（金融弱点题包）
├── harbor-rl/             # 题包类型目录：harbor-rl skill 产物（RL 数据生产，尚未出题）
├── harbor-windows/        # 题包类型目录：harbor-windows skill 产物（Windows 专项 Coding Bench）
└── skills/                # ★ 唯一的 skill 目录
    ├── OBM/               # OBM 生产全流程（含 subskills）
    ├── harbor-16/         # Harbor 内部 RL 出题
    ├── harbor-sota/       # 外发评测题包生产
    ├── harbor-rl/         # RL 数据生产
    ├── harbor-weakness/   # 金融弱点题包生产
    ├── harbor-work/       # 龙猫-阿里 A/B 标注
    ├── caveman/           # 精简输出模式
    ├── wff-workspace-discipline/  # 落盘纪律（约束产物位置）
    └── harbor-windows/            # ★ Windows 专项 Coding Bench 题包生产（windwos-第二版）
```

## 目录职责约定

**公用文件只留在类型目录根部，题目产物只放自己的子目录。** 以 OBM 为例：

- `OBM/model.env`、`OBM/feishu-gsb.toml`、`OBM/task-registry.json`、`OBM/tools/` — **项目级公用**，跨题共享
- `OBM/work/<题号>/` — 每题的工作区（运行记录、baseline、trae-runs、探针脚本等）
- `OBM/output/<题包>/` — 该题的成品交付物

单个题目的中间产物**不得**散落到父级目录。

### 判定标准

| 内容类型 | 存放位置 | 示例 |
|---|---|---|
| 跨题复用的配置 / 脚本 | 父级 | `OBM/model.env`、`OBM/tools/make_delivery_zip.py` |
| 上游源码与数据集缓存 | 父级 | `OBM/upstream/*`、`OBM/Benchmark/*` |
| 环境探测 / 安装 / 取证记录 | 父级 | `OBM/_env-records/*` |
| 某题专属脚本、日志、构建产物 | 该题目目录 | `OBM/work/<题号>/tools/*`、`.../build-artifacts/*` |
| 候选题（尚未立项） | `work/candidates/` | 仅有 `scene-profile.json` 的题目 |
| 解析材料的产出 | `deliverables/<日期>_<材料名>/` | `deliverables/2026-09-29_windwos-第二版/` |

`harbor-16/`、`harbor-sota/`、`harbor-weakness/`、`harbor-rl/`、`harbor-windows/`、`OBM/` 均为**题包类型目录**：类型目录根部**只放公用**配置/脚本/缓存，单个题包各自独立子目录，互不污染。后续新增题包类型时同此组织，并在此登记。

类型目录内保留两类下划线前缀的**非题包目录**：`_index/`（跨题索引与汇总）、`_reference/`（外部参考包解压归档，如甲方质检工具、供应商样例包）。

### 根目录洁净规则（强制）

**以下条目只允许存在一个**：`README.md`、`.gitignore`、`deliverables/`、`skills/`。

**题包类型目录可扩展**，当前已有：`OBM/`、`harbor-16/`、`harbor-sota/`、`harbor-weakness/`、`harbor-rl/`、`harbor-windows/`。新增类型目录须先经确认并登记于本节与上方目录树。

- **禁止**在根目录直接创建任何文件（报告、脚本、临时文件）。
- **禁止**根级备份/临时目录（`X.backup-*`、`X-2/`、`tmp/`）。
- **解析材料产出** → 必须落 `deliverables/<日期>_<材料名>/`，材料名**保持原拼写**（不纠正错别字）。
- **题包专属内容** → 只能进该题包自己的子目录，禁止上浮到类型目录根部。

细则由 skill `wff-workspace-discipline` 约束。


## 关键约定

| 项目 | 说明 |
|---|---|
| 认证 | **SSH**（`~/.ssh/id_ed25519`）。不要改回 HTTPS，否则会反复弹出凭据窗口 |
| `core.longpaths` | **必须为 `true`**（harbor 题包内有超 260 字符的深层路径） |
| skill 命名 | frontmatter `name` 必须为小写连字符形式（如 `harbor-16`），不可含空格 |
| 大文件 | `OBM/Benchmark/terminal-bench-main/` 下有 3 个 >50MB 文件，最大 94.68MB 逼近 GitHub 100MB 硬限制 |
| skill 位置 | 只在 `skills/` 一处，不要在其他目录放置副本 |

## 工作流

```bash
git add -A && git commit -m "描述改动" && git push
```

> ⚠️ **多任务并行时不要用 `git add -A`**：工作区经常同时存在其他任务正在进行的改动
> （例如运行中的判分任务产物、别人正在编辑的题包），`git add -A` 会把它们一并提交。
> 请按路径精确暂存：`git add <本次涉及的具体目录…>`，提交前用
> `git diff --cached --name-status` 核对范围。

## 各 skill 说明

各 skill 的使用方法见其自身目录内的 `SKILL.md` 与 `README.md`：

- `skills/OBM/README.md` — OBM 全流程安装与使用
- `skills/harbor-16/SKILL.md` — Harbor 内部 RL 出题规范
- `skills/harbor-sota/SKILL.md` — 外发题包生产规范
- `skills/harbor-windows/SKILL.md` — Windows 专项 Coding Bench 题包生产（含校验、骨架与自动化模型验证脚本）
- `skills/wff-workspace-discipline/SKILL.md` — 落盘纪律

## 查看题包交付状态

- **harbor-16 题包**：看 `jobs/` 是否含 baseline/nop + oracle + 难度门（16 条 trial，`<1`≥13、`=1`≥1）
- **harbor-sota 题包**：看是否含完整五件套 + `tests/gating/` + `tests/graded/` + `tests/golden_output/`
- **OBM 题包**：看 `output/` 下是否含 `proposal.json` 与 `sources/`
- **harbor-windows 题包**：跑 `python skills/harbor-windows/scripts/validate_package.py --package harbor-windows`，
  须满足五件套齐全 + required F2P/P2P 二值判分 + `<task-id>/extras/` 与 `_index/` 齐全 + 镜像 Digest 另存；
  模型区分度用 `python skills/harbor-windows/scripts/run_model_validation.py --layout flat` 自动化验证
  （题包平铺于 `harbor-windows/` 下，无批次层；当前仅保留已过资格门禁的
  `wfflab__wreparse-217`、`wfflab__wfmt-215`）
- **甲方质检（windows-harbor-qc）**：参考包已归档在 `harbor-windows/_reference/windows-harbor-qc/`，
  用法 `python <该目录>/scripts/run_qc.py --input <题包目录或ZIP> --out <空目录>`：先做静态检查
  （必备件 / 身份一致性 / aggregate-v1 报告协议），通过后才会在 **Windows 容器**里跑 Oracle / NOP 动态门禁
