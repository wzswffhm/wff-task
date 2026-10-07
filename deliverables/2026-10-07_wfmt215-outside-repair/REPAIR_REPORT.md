# `wfflab__wfmt-215` — Outside-Harbor 范式整改与本地校准

> 日期：2026-10-07　工作区：`harbor-windows/wfflab__wfmt-215`
> 备份：`_backup_task_root/`（整改前全量，563 个文件）
> 目标：把该题从「平台导入范式」对齐到 `wfflab__wreparse-217` 的 **Outside Harbor** 范式，
> 使本地 runner（`deliverables/2026-10-04_outside-harbor-win/runner`）可跑四模型资格门禁。

---

## 1. 为什么选 `wfflab__wfmt-215`

对 `harbor-windows/` 全部 18 题的**历史模型得分**做全量扫描（`extras/model_runs/*/run-*/report.json`），
只有两题的 QWEN 出现过失分——这是「`Opus 严格大于 Qwen`」门禁唯一的区分度来源：

| task | QWEN 历史 | OPUS 历史 | 判断 |
|---|---|---|---|
| **wfflab__wfmt-215** | **[0,1,1] = 2** | [None,0,0] = 0 | ✅ **QWEN 有 0 分波动**；OPUS 的 0 来自弱端点（`api.ebondai.com`），换端点后有反弹空间 |
| wfflab__wsync-142 | [1,0,0] = 1 | [0,0,0] = 0 | 已 `replaced` 封存 |
| wfflab__wproc-209 | [1,None] | [0,0,0] = 0 | OPUS 三轮全 0（12/13 稳定失手），难度过高 |
| wfflab__winstall-210 | [1,1,1] = 3 | [1,0,1] = 2 | QWEN 满分 → 换端点后大概率平手 |
| wfflab__wacl-203 / wencoding-206 / wtask-216 / wreserved-201 | 均 3 | 均 3 | 薄题，双方满分 |
| 其余 10 题 | 3 | 无 OPUS 记录 | 未验证 |

→ `wfmt-215` 的分布与 `wreparse-217` 的取胜形态一致（**QWEN 非满分 + OPUS 端点为唯一变量**），
故选定它作为第 2 个 Outside Harbor 题。

---

## 2. 范式差异与整改清单

| 维度 | 原（平台导入范式） | 新（Outside Harbor 范式） |
|---|---|---|
| 判分入口 | `tests/test.ps1` → `grade.py`（F2P/P2P + reward.txt） | `tests/test.ps1` → `run_tests.ps1` → `aggregate_results.ps1`（`checks.json` → `result.json`） |
| 判据 | `swelive_spec.json`（列表） | `rubric.json`（5 组加权，合计 1.0）+ `judge.toml`（绑定 sha256） |
| 隐藏测试 | `test_patch.diff`（git apply 注入） | `tests/hidden/test_wfmt_semantics.py`（直接注入 scratch 副本） |
| 运行时绑定 | 平台 harness | `environment/adapter.toml`（prepare/validate/test/restore/cleanup 五段） |
| 身份 | 无 `source.json` | `source.json`（`task_version` 升 **2.0.0**） |
| 题面/环境/参考解 | 不变 | **不变**（`instruction.md` / `environment/workspace` / `solution/oracle.patch` 零改动） |

**改动明细**
- 新增：`source.json`、`environment/adapter.toml`、`environment/{prepare,run,restore,cleanup,validate_environment}.ps1`、
  `tests/{run_tests.ps1,aggregate_results.ps1,rubric.json,judge.toml}`、`tests/hidden/test_wfmt_semantics.py`、`solution/solve.ps1`、`solution/reference/wfmt/**`
- 改造：`task.toml`（补 `[task]` / `[policy]`；`docker_image` 对齐 servercore；`task_version` → 2.0.0）
- 归档：`tests/{grade.py,swelive_spec.json,test_patch.diff}` → `extras/_platform-import/`
- 清理：`environment/workspace/.pytest_cache/`（原题残留的构建产物污染，已删除）

**红线遵守**：`instruction.md`、`environment/workspace/**`（含 `wfmt/` 初态、`docs/FORMAT.md`、`assets/*.wfmt`）
**逐字节未动**（见 §4 校验）。

---

## 3. 判据设计（5 组 / 15 检查 / 权重合计 1.0）

| rubric_id | weight | 检查数 | 覆盖 |
|---|---|---|---|
| `sample-compatibility` | 0.20 | 3 | 样本 `verify` / 逐字节回写 / 记录序列 |
| `checksum-semantics` | 0.20 | 3 | 标准 CRC 校验值 / 篡改检测 / 校验和覆盖范围 |
| `error-classification` | 0.20 | 3 | `truncated` / `magic` 分类 + `verify()` 永不抛异常 |
| `streaming` | 0.15 | 3 | `iter_records` 惰性 / 流式截断 / `read_all` 一致 |
| `roundtrip-robustness` | 0.25 | 3 | 多字节 varint / 空 payload / 生成数据往返 |

得分为**二值门**：5 组全部满足 → `score = 1`，否则 `0`（`weighted_score` 仅作诊断）。

---

## 4. 本地校准结果（本机 Windows PowerShell 5.1 + Python 3.13 + pytest 8.3.5）

| 对照 | 命令 | 结果 | 期望 | 判定 |
|---|---|---|---|---|
| **no-change** | `environment/run.ps1`（未改工作区） | `checks: 7 passed, 8 failed, 15 total`；`score=0`，`weighted=0.25` | 至少一个核心 F2P 失败、正式分 0 | ✅ |
| **golden** | `solution/solve.ps1` → `environment/run.ps1` | `checks: 15 passed, 0 failed`；`score=1`，`weighted=1.0` | 全部 PASS、正式分 1 | ✅ |

- no-change 失败的 8 项**恰好**是 `swelive_spec.json` 声明的 8 个 `FAIL_TO_PASS`；
  通过 7 项**恰好**是 7 个 `PASS_TO_PASS` → **F2P/P2P 划分经实测确认**。
- 可见冒烟测试 `tests/test_wfmt_basic.py` 在 base 上 3/3 通过（题面 F 条款前提成立）。
- 校准后工作区已用 `_wfmt_base_copy` 逐文件 sha256 校验恢复（7/7 一致）。

日志：`_calib_base.log`、`_calib_golden.log`

---

## 5. 下一步

1. **镜像构建** —— `outside-harbor/wfflab__wfmt-215:1.0`。
   ⚠️ 该题 Dockerfile 需要容器内联网（chocolatey/git + Python 3.12.9 embed + `pip install pytest`），
   与 `wreparse-217` 的极简离线 Dockerfile 不同；若构建失败，需改为**离线注入**（把宿主 Python 运行时打进镜像）。
2. **control 对照** —— `--mode no-change --runs 3` + `--mode golden --runs 3`（同一 epoch）。
3. **模型矩阵** —— `--mode candidate --models QWEN --runs 3`（先跑，压 rubrics 分），
   再 OPUS×3（`4router` 端点）+ GLM×1（`lmuai`）+ KIMI×1。
4. **门禁结算** —— `summarize_model_runs.py --after <epoch>`，要求 `sum(OPUS) > sum(QWEN)` 且 counts 齐。
5. **交付** —— 截图四件套 + 打包（根 = 批次目录）。

## 6. 风险

| # | 风险 | 处置 |
|---|---|---|
| R1 | 容器内联网不可用 → 镜像构建失败 | 改离线注入方案（宿主 Python 运行时拷入构建上下文） |
| R2 | QWEN 在 2.0.0 口径下三轮全过（历史 [0,1,1] 属旧口径） | 若平手，按规范 **adjust the task surface**（不调 turn 预算） |
| R3 | OPUS 在 4router 下仍 < 3 | 换端点或换题 |
| R4 | 本题 Windows 价值偏弱（纯 Python 字节级语义，Linux 亦可跑） | 已记入 `extras/quality_review.md` 待复核；不影响本轮门禁 |
