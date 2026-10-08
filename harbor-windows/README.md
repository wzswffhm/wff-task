# harbor-windows —— Windows 专项 Coding Bench 题包类型目录

本目录是 **`harbor-windows` skill 的产物区**，按《Windows 专项 Coding Bench 数据采购》
（`windwos-第二版`，2026-09-28，替代 v1.0.2）生产。

## 目录纪律

本目录是**题包类型目录**：根部只放公用说明；**每个题包各自独立成子目录，互不影响、可单独打包交付**。
（细则由 skill `wff-workspace-discipline` 约束。）

> **不设批次层**：题包平铺于本目录下，每题自包含。
> 本目录内所有相对路径均以 `harbor-windows/` 为基准。

> ## ⚠️ 范围声明（2026-10-08）
>
> **本目录当前实际交付 2 个题包**：
>
> | task_id | 主方向 | 难度 |
> |---|---|---|
> | `wfflab__wfmt-215` | 编码与区域（二进制容器格式，近似映射） | L4 |
> | `wfflab__wreparse-217` | 文件系统与路径（NTFS 重解析点） | L3 |
>
> 历史版本的 `README.md` 与 `_index/` 材料是按**完整仓库的 9 / 16 题范围**编写的
> （清单为 `wsync-142 / wreserved-201 / wads-202 / wacl-203 / wpathext-204 / wreg-205 /
> wencoding-206 / wps-207 / wrotate-208` 及 `wproc-209 / winstall-210 / wstamp-211 / wtask-216` 等），
> 与本目录实物不符。上述材料已于 **2026-10-08 按实物 2 题重新对齐**；
> 其余题包位于完整仓库工作区，不在本次交付范围内。

```text
harbor-windows/
├── README.md                        # 本文件（公用）
├── VALIDATION.md                    # 公用：完整验证流程（环境/软件/模型/判据）
├── _index/                          # 公用：跨题汇总材料（目录级，非批次）
│   ├── tasks_index.csv                      # 2 题清单（身份 + 方向 + F2P/P2P + 状态）
│   ├── knowledge_tree_coverage_report.csv   # 12 个 Windows 方向的覆盖统计
│   ├── validation_report.md                 # 验收状态汇总
│   ├── model_summary.csv                    # 多模型运行汇总
│   ├── model_validation_summary.json        # 多模型区分度准入（机器可读）
│   ├── model_validation_report.md           # 多模型区分度准入（人读）
│   ├── known_issues.md                      # 已知问题（K1–K20，含适用性标注）
│   ├── CHANGELOG.md                         # 版本与结构变更记录
│   ├── EXTERNAL_IMAGES.json                 # 镜像清单（本地 Image ID）
│   ├── checksums.sha256                     # 本目录制品校验和（2 题范围，515 文件）
│   └── validate-report.json                 # 历史产物，见「校验」一节
├── wfflab__wfmt-215/                # 题包 1（含 extras/）
└── wfflab__wreparse-217/            # 题包 2
```

### 单题结构

```text
<task-id>/
├── task.toml                    # Outside Harbor 契约 + 标准 Harbor 字段
├── instruction.md               # 题面
├── source.json                  # 溯源（task_id / source_type / license / lineage / authorization）
├── platform_import.json         # 平台导入 JSON（仅 215 有）
├── environment/                 # 标准五件套之一
│   ├── adapter.toml             # 本地 runner 的 Outside Harbor 适配（task_root / 各阶段钩子）
│   ├── Dockerfile               # 标准 Harbor 的镜像定义（构建上下文 = environment/）
│   ├── prepare.ps1              # 夹具/工作区准备（217 为转发到 tests/prepare.ps1）
│   ├── run.ps1 / restore.ps1 / cleanup.ps1 / validate_environment.ps1
│   └── workspace/               # 候选工作区（唯一可变路径见 [policy].mutable_paths）
├── solution/
│   ├── solve.ps1                # 参考解（支持 -WorkspaceRoot，兼容两种布局）
│   ├── solve.bat                # 标准 Harbor 入口（Windows 容器只发现 .bat）
│   ├── README.md
│   └── oracle.patch             # 仅 215 有
├── tests/
│   ├── test.ps1                 # 判分入口（写 C:\logs\verifier\{report.json,reward.*}）
│   ├── test.bat                 # 标准 Harbor 入口
│   ├── prepare.ps1              # 仅 217 有（Harbor 无 prepare 钩子，由 test.bat 调用）
│   ├── run_tests.ps1 / aggregate_results.ps1 / judge.toml / rubric.json / required_testcases.json
├── extras/                      # 题级伴随材料（仅 215 有：metadata / model_runs / _platform-import）
└── jobs/                        # 作业记录：每次跑分一个 <job-id>/{agent,verifier}
    ├── _index/                  #   jobs_index.csv + 资格汇总
    ├── <job-id>/job.json        #   判定与来源
    ├── <job-id>/agent/          #   agent.log / run.json / <agent>.txt
    └── <job-id>/verifier/       #   result.json + 原始产物（checks.json / test.log / report.json / reward.txt）
```

> **`jobs/`（作业记录）**：按平台交付结构，`jobs/` 与 `<task-id>/` 平级；仓库内先落
> `<task-id>/jobs/`，组装批次包时平级上移。每条记录含判定（`job.json`）、agent 侧（`agent/`）
> 与判分侧（`verifier/`）三部分。原始 `agent.log` / `checks.json` / `test.log` / `stderr.log`
> 已从本地 runner 存储（`deliverables/2026-10-04_outside-harbor-win/runner/runs/`）回填，
> 并以 `test_log_sha256` 逐条对账（215 = 16/16、217 = 17/17 全部匹配）；
> Harbor 轮次的原始产物（`report.json` / `reward.txt` / `test-stdout.txt`）由容器直接产出。

## 题包清单（2 题）

| # | task_id | 包 | 主方向 | L | F2P/P2P | 多模型区分度 | 状态 |
|---|---|---|---|---|---|---|---|
| 1 | `wfflab__wfmt-215` | `wfmt` 0.9.3 | 编码与区域（二进制容器格式） | L4 | 8/7 | Opus 2.0 > Qwen 0.0 | 交付就绪（结构 + 判分 + 对照 + 区分度 + Harbor 加载） |
| 2 | `wfflab__wreparse-217` | `WReparse` 1.0.0 | 文件系统与路径 | L3 | 13/11 | Opus 3.0 > Qwen 2.0 | 交付就绪（同上） |

合计 **required 39 条**（F2P 21 + P2P 18）。覆盖 12 个 Windows 主流方向中的 2 个。

> 逐题明细见 `_index/tasks_index.csv`；验收汇总见 `_index/validation_report.md`；
> 区分度见 `_index/model_validation_report.md`。

## 标准 Harbor 兼容（2026-10-08 整改）

两题现已满足标准 Harbor CLI 契约，可直接被平台加载、构建与评分：

| 契约要求 | 实现 |
|---|---|
| `[task].name = "org/name"` | 两题在 `[task]` 中声明 `name`（本地 runner 用的 `id` 原样保留） |
| `[environment].os` / `workdir` | 两题声明 `os = "windows"`、`workdir = "C:\\testbed"` |
| 镜像来源 | **不设** `[environment].docker_image` → Harbor 构建 `environment/Dockerfile`；顶层 `docker_image` 保留给本地 runner |
| Windows 入口 | `tests/test.bat`、`solution/solve.bat`（Windows 容器只发现 `.bat`） |
| prepare 阶段 | Harbor 无 prepare 钩子：215 无此需求；217 由 `tests/test.bat` 先调用 `tests/prepare.ps1` |

实测（本机 Docker Desktop **Windows 容器模式** + Harbor CLI 0.22.0）：

- `Task.is_valid_dir()` 两题均为 `True`；`harbor run --path <题包目录>` **单题直跑**（无需 `--include-task-name`）；
- 镜像由 Harbor 自行构建并在容器内跑通（215 另经 `docker build --no-cache` 全新构建验证）；
- **不依赖任何 QC 扩展**（默认环境）同样通过：`--agent oracle` → `Reward 1`；
- 控制与门禁：Oracle ×3 = `VALID/1`、NOP ×3 = `VALID/0`（两题）。

复现：

```powershell
$env:DOCKER_CONTEXT="desktop-windows"
harbor run --path .\harbor-windows\wfflab__wreparse-217 --agent oracle --n-attempts 3 --n-concurrent 1 --max-retries 0 --yes
harbor run --path .\harbor-windows\wfflab__wreparse-217 --agent nop    --n-attempts 3 --n-concurrent 1 --max-retries 0 --yes
```

## 校验

```bash
# 平铺模式：自动识别本目录下每个含 task.toml 的题包
python ../skills/harbor-windows/scripts/validate_package.py --package . --schema-version 1.3

# 单题
python ../skills/harbor-windows/scripts/validate_package.py --harbor-assets ../wfflab__wreparse-217
```

- `_index/checksums.sha256`：已按**当前 2 题范围**重算（533 个文件，含 `jobs/`），
  每行格式 `<sha256>  <相对路径>`，路径以 `harbor-windows/` 为基准。
- `_index/tasks_index.csv` 的 `task_hash` 采用**题包定义树哈希**，规则为：

  ```text
  sha256 over: 对 task 根下除 jobs/ 与 platform_import.json 外的全部文件，
               按「正斜杠相对路径」升序，依次喂入 "<relpath>\n<该文件 sha256>\n"
  ```

  > `platform_import.json` **自身记录该哈希**，必须排除出被哈希集合，否则自引用：
  > 文件一写入，哈希即失效。
  >
  > ⚠️ 2026-10-08：215 原先记录的 `77221d28…` 即因该自引用而失效（且它还是修改
  > `platform_import.json` **之前**算出的值）；现按上述规则重算。

  215 = `1f911851b886488a843df37507b5b28f8628997b2243bec465cf3242e71c9eda`
  217 = `f48fbd3f2d6a871498e198b9f71c0490a4c9a49230c2710868b7751625d5536f`
- `_index/validate-report.json`：**历史产物**，由 `skills/harbor-windows/scripts/validate_package.py`
  在旧的 9 题范围下生成（其中 `PASS=256` 等计数对应旧范围）。该 skill 未随本目录交付，
  故本轮未重算；正式验收前须在当前 2 题范围重新生成。

## 多模型区分度验证

```bash
export HARBOR_WINDOWS_ALIYUN_KEY=<aliyun key>   # qwen / glm / kimi 共用
export HARBOR_WINDOWS_BLVR_KEY=<blvr key>       # opus

# 题包根目录即 --tasks；--out 指向各题 extras/ 的父目录
python ../skills/harbor-windows/scripts/run_model_validation.py \
    --tasks . --out . --out-layout flat

# 平台 harness 回填正式分后，只算区分度
python ../skills/harbor-windows/scripts/run_model_validation.py \
    --score-only --out . --out-layout flat
```

> 凭据不入库。端点配置存放于仓库外的用户级目录。两题当前均已达标：
> 215（Opus 2.0 > Qwen 0.0）、217（Opus 3.0 > Qwen 2.0）；
> 详见 `_index/model_validation_report.md` 与各题 `jobs/_index/qualification_summary.json`。
