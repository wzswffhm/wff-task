# harbor-windows —— Windows 专项 Coding Bench 题包类型目录

本目录是 **`harbor-windows` skill 的产物区**，按《Windows 专项 Coding Bench 数据采购》
（`windwos-第二版`，2026-09-28，替代 v1.0.2）生产。

## 目录纪律

本目录是**题包类型目录**：根部只放公用说明；**每个题包各自独立成子目录，互不影响、可单独打包交付**。
（细则由 skill `wff-workspace-discipline` 约束。）

> **不设批次层**：9 个题包平铺于本目录下，每题自包含。
> 本目录内所有相对路径均以 `harbor-windows/` 为基准。

```text
harbor-windows/
├── README.md                        # 本文件（公用）
├── VALIDATION.md                    # 公用：完整验证流程（环境/软件/模型/判据）
├── _index/                          # 公用：跨题汇总材料（目录级，非批次）
│   ├── tasks_index.csv                      # 9 题清单（身份 + 方向 + F2P/P2P + 状态）
│   ├── knowledge_tree_coverage_report.csv   # 12 个 Windows 方向的覆盖统计
│   ├── validation_report.md                 # 验收状态汇总
│   ├── model_summary.csv                    # 多模型运行汇总（当前全 PENDING）
│   ├── known_issues.md                      # 已知问题（K1–K9）
│   ├── CHANGELOG.md                         # 版本与结构变更记录
│   ├── EXTERNAL_IMAGES.json                 # 镜像清单（Digest 待回填）
│   ├── checksums.sha256                     # 全目录制品校验和
│   └── validate-report.json                 # 机器校验报告
└── <task-id>/                       # 9 个自包含题包，彼此独立
    ├── task.toml                    # ┐
    ├── instruction.md               # │ 标准 Harbor 五件套
    ├── environment/                 # │
    ├── solution/oracle.patch        # │
    ├── tests/                       # ┘  test.ps1 / grade.py / swelive_spec.json / test_patch.diff
    ├── platform_import.json         # 平台导入 JSON（原 outside_harbor/<task-id>.json）
    ├── extras/                      # 题级伴随材料（原 delivery-extras/tasks/<task-id>/）
    │   ├── metadata/                #   source_and_license / labels / lineage_and_contamination / manifest
    │   ├── evidence/                #   no_change / golden / clean_room / negative_and_equivalent_controls / cleanup_and_restore
    │   ├── model_runs/              #   qwen3.8-max-0902 / opus-5 / glm-5.3 / kimi-k3
    │   ├── testcase_mapping.csv
    │   ├── quality_review.md
    │   └── remediation_and_retest.md
    └── jobs/                        # 作业记录：每次跑分一个 <job-id>/{agent,verifier}
        ├── README.md                #   来源、口径、缺口声明
        ├── _index/                  #   jobs_index.csv + 资格汇总副本
        └── <job-id>/                #   job.json + agent/run.json + verifier/result.json
```

> **`jobs/`（作业记录）**：按平台交付结构，`jobs/` 与 `<task-id>/` 平级；仓库内先落
> `<task-id>/jobs/`，组装批次包时平级上移。由 `skills/harbor-windows/scripts/build_jobs.py`
> 从资格汇总（`model_runs_summary_*.json`）生成；交付 ZIP 由 `package_task_zip.py` 打出（含 `jobs/`）。
> 原始 `agent.log` / `test.log` 位于被 `.gitignore` 忽略的 runner `runs/`，未留存时只做
> **可核对的最小重建**并显式声明缺口，不得伪造轨迹。

## 题包清单（9 题）

| # | task_id | 包 | 主方向 | L | F2P/P2P | 状态 |
|---|---|---|---|---|---|---|
| 1 | `wfflab__wsync-142` | `wsync` | 文件系统与路径 | L4 | 7/9 | 对照验证通过；待补 K1/K3 |
| 2 | `wfflab__wreserved-201` | `wsafename` | 文件系统与路径 | L4 | 7/8 | 结构校验通过；待补 K1–K3 |
| 3 | `wfflab__wads-202` | `wdl` | 文件系统与路径 | L4 | 7/6 | 结构校验通过；待补 K1–K3 |
| 4 | `wfflab__wacl-203` | `wpublish` | 安全与身份 | L4 | 7/6 | 结构校验通过；待补 K1–K3 |
| 5 | `wfflab__wpathext-204` | `wexec` | Shell 与自动化 | L4 | 7/6 | 结构校验通过；待补 K1–K3 |
| 6 | `wfflab__wreg-205` | `wregconfig` | 系统管理 | L4 | 6/6 | 结构校验通过；待补 K1–K3 |
| 7 | `wfflab__wencoding-206` | `wtextio` | 编码与区域 | L4 | 7/6 | 结构校验通过；待补 K1–K3 |
| 8 | `wfflab__wps-207` | `wjob` | Shell 与自动化 | L4 | 7/6 | 结构校验通过；待补 K1–K3 |
| 9 | `wfflab__wrotate-208` | `wrotate` | 文件系统与路径 | L4 | 7/6 | 结构校验通过；待补 K1–K3 |

合计 **required 107 条**（F2P 62 + P2P 51）。覆盖 12 个 Windows 主流方向中的 5 个。

> 状态中的 K1/K2/K3 见 `_index/known_issues.md`（镜像 Digest / 对照验证 / 多模型区分度）。
> 逐题明细见 `<task-id>/extras/quality_review.md`；汇总见 `_index/validation_report.md`。

## 校验

```bash
# 平铺模式：自动识别本目录下每个含 task.toml 的题包
python ../skills/harbor-windows/scripts/validate_package.py --package . --schema-version 1.3

# 单题
python ../skills/harbor-windows/scripts/validate_package.py --harbor-assets ../wfflab__wsync-142
```

期望：`PASS=256  FAIL=0  FLAG=0`，退出码 `0`。

机器报告写入 `_index/validate-report.json`。校验和覆盖 459 个文件，见 `_index/checksums.sha256`。

## 多模型区分度验证（待凭据与分数就绪）

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

> 凭据不入库。aliyun 端点 Key 存放于仓库外的 `~/.workbuddy/harbor-windows.env`；
> Opus 端点（`api.blvr.top`）凭据尚未提供。
