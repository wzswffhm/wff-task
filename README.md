# wff-task

统一的 OBM / Harbor 题包生产与交付工作区。所有内容由单一私有仓库管理：
`git@github.com:wzswffhm/wff-task.git`（PRIVATE）

> 本文档同时承载**工作区落盘纪律**：原 `skills/wff-workspace-discipline` skill 的内容已**全文并入**
> 下方「落盘纪律」章节，原目录已删除，**纪律的唯一出处就是本文件**。在 wff-task 内创建、移动或
> 写入任何文件前，先按该章节确定落点。

## 目录结构

**skill 与题包同址**：每个类型目录下建 `skills/<同名 skill>/`，该类型的所有产出都收敛在自己的目录内。

**题包目录 = 飞书附件镜像**：凡从飞书拉取的题包，其目录名与层级必须与飞书交付附件解压后**逐字一致**
（见铁律四），不得改名、拍平或丢伴随文件。

```text
wff-task/
├── README.md              # 本文件：工作区总说明 + 落盘纪律（唯一顶层 README）
├── .gitignore             # 唯一的顶层 gitignore，统一管理忽略规则
├── models.local.json      # 全工作区统一模型端点配置（含明文 Key，已被 .gitignore 排除）
├── deliverables/          # ★ 解析材料产出区（<日期>_<材料名>/，材料名保持原拼写）
├── OBM/                   # 题包类型目录：OBM 题包生产
│   ├── skills/OBM/        #   └ OBM 全流程 skill（含 subskills）
│   ├── model.env          # 公用：模型 API 配置
│   ├── feishu-gsb.toml    # 公用：飞书配置
│   ├── task-registry.json # 公用：题目登记表
│   ├── tools/             # 公用：跨题复用的构建/登记脚本
│   ├── upstream/          # 公用：上游源码缓存（已移出 Git，本地保留）
│   ├── feishu-records/    # 公用：飞书知识库记录快照
│   ├── _env-records/      # 公用：环境探测与安装/取证记录
│   ├── work/<题号>/        # 每题独立的工作区（中间产物）
│   └── output/<题包>/      # 成品题包（proposal.json + sources/）
├── harbor-16/             # 题包类型目录：内部 RL 题包
│   └── skills/harbor-16/
├── harbor-sota/           # 题包类型目录：外发供应商题包
│   └── skills/harbor-sota/
├── harbor-rl/             # 题包类型目录：RL 数据生产
│   └── skills/harbor-rl/
├── harbor-weakness/       # 题包类型目录：金融弱点题包
│   ├── skills/harbor-weakness/
│   ├── work_fin-b01_<批次>-<序号>/   # ★ 批次目录 = 飞书附件名去 .zip（当前 4 个）
│   │   ├── FIN3-WKN-<序号>/          #   题包本体
│   │   ├── 交付文档.md                #   交付文档（必留）
│   │   └── 跑分产物与轨迹/            #   部分批次有，且位于批次根级
│   ├── _index/            # 跨题索引与汇总（含 152 质检报告、门禁原始输出）
│   ├── _reference/        # 外部参考包归档
│   └── _qc_runs/          # 该类型的历史质检运行记录
├── harbor-windows/        # 题包类型目录：Windows 专项 Coding Bench
│   ├── skills/harbor-windows/   # 生产 + 校验/模型验证脚本
│   ├── wfflab__wchunk-216-v1.2.0-delivery/  # ★ 目录名 = 飞书附件名去 .zip
│   ├── wfflab__wfmt-215-v2.1.0-delivery/    # ★ 同上
│   ├── _index/                  # 跨题索引与汇总（含 118-submission 返修提交材料）
│   ├── _reference/              # 外部参考包归档
│   └── _qc_runs/                # 该类型的历史质检运行记录
└── harbor-work/           # 类型目录：龙猫-阿里 A/B 标注
    └── skills/harbor-work/
```

## 落盘纪律（强制）

本工作区对**文件写到哪里**有硬性约束。产生任何文件前先按本节确定落点。

### 铁律一：仓库根目录单一制

以下条目**只允许存在一个**，禁止出现同名的第二个（如 `deliverables-2/`、`README2.md`、`skills.bak/`）：

```
README.md  .gitignore  models.local.json  deliverables/
```

除以上四件外，根目录**只允许**出现下节登记过的目录（当前为 `OBM/`、`harbor-16/`、`harbor-sota/`、
`harbor-rl/`、`harbor-weakness/`、`harbor-windows/`、`harbor-work/`）。**顶层 `skills/` 已废除**，
不要重建。质检运行记录**不再放根目录**，一律归档到对应类型目录的 `_qc_runs/`（见落点判定表）。

题包类型目录是**可扩展的**，但每新增一个类型目录都须先经用户同意并在本节登记。

- **禁止**在仓库根目录直接创建任何 `.md`、`.txt`、`.csv`、`.json`、脚本或报告文件
  （唯一例外：上表登记的 `models.local.json`，它是全工作区共用的模型端点配置）。
- 备份目录（`X.backup-*`、`X-2/`）、临时目录（`tmp/`、`new/`）一律**禁止**出现在根目录。

### 铁律二：题包按类型隔离，单包自包含

`OBM/`、`harbor-16/`、`harbor-sota/`、`harbor-rl/`、`harbor-weakness/`、`harbor-windows/`、`harbor-work/`
是**题包类型目录**。每个目录代表**一类 skill 的产物集合**。

1. **单个题包 = 类型目录下的一个独立子目录**。一题一目录，互不干扰。
2. **类型目录根部只允许放公用内容**：

   | 可放（公用） | 示例 |
   |---|---|
   | 跨题复用的配置 | `OBM/model.env`、`OBM/feishu-gsb.toml`、`OBM/task-registry.json` |
   | 跨题复用的脚本 | `OBM/tools/`、`harbor-windows/skills/harbor-windows/scripts/` |
   | 公用数据缓存 | `OBM/upstream/`（第三方基准数据集 `OBM/Benchmark/` 已于 2026-10-12 删除） |
   | 公用记录 | `OBM/feishu-records/`、`OBM/_env-records/` |
   | 跨题索引 / 参考包 | `<类型目录>/_index/`、`<类型目录>/_reference/` |

3. **题包专属内容只能放进该题包自己的目录内**，禁止上浮到类型目录根部，避免污染其他题包。
4. **skill 与产出目录同址**：`<类型目录>/skills/<同名 skill>/`（如
   `harbor-windows/skills/harbor-windows/`）。**顶层 `skills/` 已废除**；通用 skill 也一律挂到
   某个已登记目录下，不单独占用根级位置。
5. **新增题包类型时**：先 `mkdir` 类型目录，再在其中按「公用 + skills + 单包目录」三层组织，并在根 `README.md` 登记。

### 铁律三：deliverables/ 是解析材料专用产出区

`deliverables/` 用于存放**对某份材料做解析/分析后的产出**。

**命名规则**：目录名 = `<YYYY-MM-DD>_<材料文件名（去扩展名）>`，**保持材料原名原样**。

```
用户提供的材料：  windwos-第二版.pdf
                ↓
deliverables/     2026-09-29_windwos-第二版/     # 日期 + 材料主名（去扩展名）
```

- **目录名格式**：`<YYYY-MM-DD>_<材料名>`。日期取**产出当日**（用 `date +%F` 获取真实日期，不要凭记忆推算）。
- **保持原名原样**：材料名部分照抄，**包括原始拼写**（如 `windwos` 是原件的拼写，不要"纠正"成 `windows`）。
- **一材料一目录**：同一份材料的所有产出放在同一目录，不拆散。

### 铁律四：来自飞书的题包，目录名与层级必须与飞书附件完全一致

飞书多维表格是题包的**唯一事实来源**，本地目录只是它的**镜像**。凡从飞书附件拉取的题包：

1. **目录名 = 附件名去 `.zip`**，逐字照抄（大小写、版本号、日期、`fix<N>`、`_` 与 `-` 的原样混用）。
2. **完整保留附件内的层级**：不解压后重排、不拍平中间层、不丢伴随文件（如 `交付文档.md`）。
3. **禁止用 `task_id` 当目录名**：`task_id` 不含版本（`wfflab__wchunk-216` 无法区分 v1.1.0 / v1.2.0），
   也与飞书附件名不对应。`task_id` / `task_version` / `task_hash` 一律**只从包内 `task.toml` 读取**。
4. **换版即换目录**：拉取新版后移除旧目录，类型目录下与飞书当前附件**一一对应**，不留历史版本副本。
5. **拉取方式固定**：`base +record-download-attachment` 下载附件 zip → 解压到类型目录本身，
   让包内顶层目录自然落地；禁止手工拼目录、手工改名。

当前对应关系：

| 类型 | 飞书交付附件名 | 本地落点 |
|---|---|---|
| harbor-windows | `wfflab__wchunk-216-v1.2.0-delivery.zip` | `harbor-windows/wfflab__wchunk-216-v1.2.0-delivery/` |
| harbor-windows | `wfflab__wfmt-215-v2.1.0-delivery.zip` | `harbor-windows/wfflab__wfmt-215-v2.1.0-delivery/` |
| harbor-weakness | `work_fin-b01_20261011_fix11-149.zip` | `harbor-weakness/work_fin-b01_20261011_fix11-149/` |
| harbor-weakness | `work_fin-b01_20261006_fix8-150.zip` | `harbor-weakness/work_fin-b01_20261006_fix8-150/` |
| harbor-weakness | `work_fin-b01_20261006-151.zip` | `harbor-weakness/work_fin-b01_20261006-151/` |
| harbor-weakness | `work_fin-b01_20261009-152.zip` | `harbor-weakness/work_fin-b01_20261009-152/` |

harbor-weakness 的批次目录内固定为 `<批次目录>/FIN3-WKN-<序号>/` + `<批次目录>/交付文档.md`；
harbor-windows 的题包目录内固定为 `environment/ jobs/ solution/ tests/ verifier/ instruction.md task.toml`。
两类型 skill 中已写入同口径规则（`harbor-weakness/skills/harbor-weakness/`、
`harbor-windows/skills/harbor-windows/`）。

### 落点判定表（速查）

| 产出内容 | 落点 | 示例 |
|---|---|---|
| 解析某份材料的报告 / 清单 / 汇报 | `deliverables/<日期>_<材料名>/` | `deliverables/2026-09-29_windwos-第二版/` |
| 解析所需支撑材料（抽取文本、数据导出） | 同上目录 | `deliverables/2026-09-29_windwos-第二版/抽取.txt` |
| 题包中间产物、运行记录、baseline | `<类型目录>/work/<题号>/` | `OBM/work/2026-09-29-1-pycasbin.../` |
| 成品题包（飞书镜像） | `<类型目录>/<附件名去 .zip>/` | `harbor-windows/wfflab__wchunk-216-v1.2.0-delivery/` |
| 跨题复用配置 / 脚本 / 数据缓存 | 类型目录根部（公用层） | `OBM/tools/`、`OBM/upstream/` |
| 跨题索引 / 汇总报告 | `<类型目录>/_index/` | `harbor-weakness/_index/FIN3-WKN-152_质检报告.md` |
| 外部参考包解压归档 | `<类型目录>/_reference/` | `harbor-windows/_reference/windows-harbor-qc/` |
| 该类型的历史质检运行记录 | `<类型目录>/_qc_runs/` | `harbor-windows/_qc_runs/qcpass-215/`、`harbor-weakness/_qc_runs/g5-152v4-opus/` |
| 全工作区共用的模型端点配置 | 根 `models.local.json`（含明文 Key，不入库） | `models.local.json` |
| skill 本体 | `<类型目录>/skills/<name>/` | `harbor-windows/skills/harbor-windows/SKILL.md` |
| 通用 skill（无题包类型归属时） | 挂到某个已登记目录下的 `skills/<name>/` | 不单独占用根级位置 |
| 落盘纪律（规则本身） | 根 `README.md`（不再单独放 skill） | `README.md` 的「落盘纪律」章节 |

### 执行流程

1. **写文件前先判类型** —— 对照落点判定表，确定是「解析产出」「题包产物」还是「公用内容」。
2. **确定目标目录** —— 目录不存在则 `mkdir -p` 创建；题包内容先建好单包目录再放入。
3. **只在确定落点后写入** —— 不要先写到根目录/类型目录根部再"稍后整理"。
4. **发现已有污染** —— 立即移动到正确位置；已跟踪的文件用 `git mv` 保留历史。
5. **收尾自检** —— `ls` 复核根目录仍只含 `README.md`/`.gitignore`/`deliverables/` + 已登记的目录；`deliverables/` 新增时更新其索引。

### 反模式（禁止）

| ❌ 错误做法 | ✅ 正确做法 |
|---|---|
| 分析报告写到 `wff-task/报告.md` | 写 `deliverables/<日期>_<材料名>/报告.md` |
| `deliverables/某材料/` 缺日期前缀 | `deliverables/2026-09-29_某材料/` |
| 目录名把材料拼写"纠正" | 保持原件原拼写（`windwos` 不改成 `windows`） |
| 某题脚本/日志丢在 `OBM/` 根部 | 放该题的 `OBM/work/<题号>/` 内 |
| 单个题包与其他题包混在类型目录根部 | 类型目录根部只放公用内容，单包独立子目录 |
| 新建 `analysis/`、`tmp/`、`X-2/` 等根级目录 | 用 `deliverables/` 或已登记的类型目录 |
| 把 skill 丢在顶层 `skills/`（已废除该目录） | 放 `<类型目录>/skills/<同名 skill>/` |
| 把飞书批次目录拍平（`harbor-weakness/FIN3-WKN-149/`） | 保留批次层：`harbor-weakness/work_fin-b01_...-149/FIN3-WKN-149/` |
| 用 `task_id` 当飞书题包目录名（`wfflab__wchunk-216/`） | 用附件名去 `.zip`（`wfflab__wchunk-216-v1.2.0-delivery/`） |
| 丢掉批次包里的 `交付文档.md` | 交付文档随批次目录一并保留 |
| 修改后不检查目录 | 每次收尾 `ls` 复核 |

## 关键约定

| 项目 | 说明 |
|---|---|
| 认证 | **SSH**（`~/.ssh/id_ed25519`）。不要改回 HTTPS，否则会反复弹出凭据窗口 |
| `core.longpaths` | **必须为 `true`**（harbor 题包内有超 260 字符的深层路径） |
| skill 命名 | frontmatter `name` 必须为小写连字符形式（如 `harbor-16`），不可含空格 |
| 第三方数据集 | 原 `OBM/Benchmark/`（1.27 GB：frontier-swe-v2 / terminal-bench / swe-marathon / ProgramBench / deep-swe）已于 2026-10-12 删除；需要时从各自上游仓库重新拉取 |
| skill 位置 | 每个 skill 只在该类型目录下的 `skills/` 一处；顶层 `skills/` 已废除，不要放置副本 |

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

- `OBM/skills/OBM/README.md` — OBM 全流程安装与使用
- `harbor-16/skills/harbor-16/SKILL.md` — Harbor 内部 RL 出题规范
- `harbor-sota/skills/harbor-sota/SKILL.md` — 外发题包生产规范
- `harbor-rl/skills/harbor-rl/SKILL.md` — RL 数据生产
- `harbor-weakness/skills/harbor-weakness/SKILL.md` — 金融弱点题包生产
- `harbor-windows/skills/harbor-windows/SKILL.md` — Windows 专项 Coding Bench 题包生产（含校验、骨架与自动化模型验证脚本）
- `harbor-work/skills/harbor-work/SKILL.md` — 龙猫-阿里 A/B 标注

> 落盘纪律原为 `skills/wff-workspace-discipline` skill，现已**全文并入本 README**，
> 不再有对应 skill 目录；查阅规则请看本文档「落盘纪律」章节。

## 查看题包交付状态

- **harbor-16 题包**：看 `jobs/` 是否含 baseline/nop + oracle + 难度门（16 条 trial，`<1`≥13、`=1`≥1）
- **harbor-sota 题包**：看是否含完整五件套 + `tests/gating/` + `tests/graded/` + `tests/golden_output/`
- **OBM 题包**：看 `output/` 下是否含 `proposal.json` 与 `sources/`
- **harbor-weakness 题包**：看 `harbor-weakness/<批次目录>/` 下是否同时具备 `FIN3-WKN-<序号>/`
  （内含 `instruction.md` + `rubrics.json` + `task.toml` + `environment/`（input_files）+ `tests/`）
  **与 `交付文档.md`**；批次目录名与飞书 `交付物` 附件名逐条对应（当前 4 个批次，覆盖 149/150/151/152）
- **harbor-windows 题包**：跑 `python harbor-windows/skills/harbor-windows/scripts/validate_package.py --package harbor-windows`，
  须满足五件套齐全 + required F2P/P2P 二值判分 + `_index/` 齐全 + 镜像 Digest 另存；
  模型区分度用 `python harbor-windows/skills/harbor-windows/scripts/run_model_validation.py --layout flat` 自动化验证
  （题包平铺于 `harbor-windows/` 下，无批次层；当前仅保留已过资格门禁的
  `wfflab__wchunk-216-v1.2.0-delivery`、`wfflab__wfmt-215-v2.1.0-delivery`）
- **甲方质检（windows-harbor-qc）**：参考包已归档在 `harbor-windows/_reference/windows-harbor-qc/`。
  旧版动态入口 `scripts/run_qc.py`（连同包装 `run_qc.ps1` 与单测 `tests/test_run_qc.py`）已于 2026-10-12
  移除；保留 `validate_model_gate.py`（模型区分度准入）与 `windows_qc_env.py` 等附属件。
  门禁判定口径（Oracle 3×`VALID/1`、NOP 3×`VALID/0`、NOP 每轮 P2P 全 PASS 且至少一个核心 F2P FAIL）
  见该目录 `SKILL.md`；动态执行改由 `harbor-windows/skills/harbor-windows/` 下的校验脚本承担

## 题包来源

题包以**飞书多维表格为准**（标注员 = wff），本地目录从飞书附件拉取并保持一一对应：

| 类型 | 飞书来源 | 本地落点 |
|---|---|---|
| harbor-windows | 节点 `O1qjw1qFRijaf8kal5scROn9nmc`（base `EsJebL8JJaf7g4sIbItcnMFgnvg` / table `tblRDxcGkblflMBA`） | `harbor-windows/<附件名去 .zip>/` |
| harbor-weakness | 节点 `S4dVwTGtviikDPkF0wycdMernKf`（base `QpzNb4fXSamfX6sLloBcPfHNnug` / table `tblPNrBtjFfwOowN`） | `harbor-weakness/<附件名去 .zip>/`（批次目录） |

拉取方式（Base 附件必须用专用命令，`drive +download` 对 Base 附件会返回 400）：

```bash
# 列出记录拿 record_id / file_token
lark-cli base +record-list --base-token <base> --table-id <table> \
  --field-id <id> --limit 200 --as user
# 下载附件（--output 只接受当前目录下的相对路径）
cd <目标目录>
lark-cli base +record-download-attachment --base-token <base> --table-id <table> \
  --record-id <record_id> --file-token <file_token> --output ./<文件名> --as user
```

下载后**原样解压到类型目录本身**（如 `harbor-windows/`），包内顶层目录即唯一合法落点：
不要多包一层、也不要少包一层，目录名必须等于附件名去 `.zip`（见铁律四）。
