# 215 / 216 交付计划（v1.0.1）— 跑分前冻结版

> 目的：把「跑分 → 质检 → 打包 → 飞书 → 推代码」全链条一次列全，每一步先定验收标准再执行，
> 避免跑完 12 个 job 才发现缺证据、缺字段、缺上传件而返工重跑。
>
> 适用范围：`wfflab__wsparse-215-v1.0.1-delivery`、`wfflab__wvas-216-v1.0.1-delivery`
> 交付物集合：仅 215 / 216（218、221 已弃；219、220 早前已交付）

---

## 0. 冻结口径（不可在跑分后修改）

| 项 | 值 | 依据 |
|---|---|---|
| 版本 | `1.0.1` | 返修后升版，checklist §9「修复后必须提升版本和 Hash」 |
| 模型轮次 | Qwen×3 + Opus×3 | 用户 2026-10-16 口径；甲方放宽 GLM/Kimi |
| `jobs/` 数量 | **12** | `validate_model_jobs.py:115` 硬校验 12（3+3 Oracle/NOP，3+3 Qwen/Opus） |
| 区分度 | `Qwen model_score_sum < Opus model_score_sum`（严格小于） | checklist §7；相等/全零平局/双满全 FAIL |
| 执行层 | L0 物理 → **L1 Windows VM** → L2 容器 | `nested-virtualization-gate.md`；`virtualization_depth ≥ 2` |
| 镜像 | `ghcr.io/wzswffhm/wfflab-windows:{wsparse-215,wvas-216}-1.0.1` | 已在 ghcr 存在，digest 与 1.0.0 内容一致 |
| Claude Code | **不打包、不入镜像** | 用户明确要求；buyer agent 不参与本轮 |

> ⚠️ 冻结红线：`task_checksum` 绑定包内容。**跑分期间到打包前，包内任何文件都不得改动**
> （含 `jobs/` 之外的一切）。改一个字节 → 12 个 job 全部作废。

---

## 1. 阶段划分与验收标准

### 阶段 A：L1 内跑分（进行中）

**产出**：每包 `jobs/` 12 个 job 目录 + `_index/assembly_report.json`

**执行**：`_qc_runs/l1_rerun_all.ps1`（在 L1 内独立进程，两包并行）

**验收（逐条硬门禁）**：

| # | 检查 | 通过标准 |
|---|---|---|
| A1 | Oracle ×3 | 每轮 `VALID`、`reward=1`、required 全 PASS |
| A2 | NOP ×3 | 每轮 `VALID`、`reward=0`、**P2P 全 PASS**、**≥1 个 F2P FAIL** |
| A3 | Qwen ×3 | 每轮 `VALID`、reward ∈ {0,1}、testcase 集合 == required |
| A4 | Opus ×3 | 同上 |
| A5 | 分差 | `sum(Qwen) < sum(Opus)` 严格成立（含"双满"检查） |
| A6 | checksum 一致 | 12 个 job 的 `task_checksum` 全相同，且 == 当前 Task 目录重算值 |
| A7 | 无轮次筛选 | `jobs/` 就是 3 Oracle+3 NOP+3 Qwen+3 Opus，不做择优剔除 |

### 阶段 B：镜像交付证据（可提前，部分已采）

| # | 检查 | 证据文件 |
|---|---|---|
| B1 | 远端可拉取 | `docker manifest inspect` rc=0 |
| B2 | 匿名可访问 | 无凭据 pull manifest HTTP 200 |
| B3 | digest 记录 | `sha256:d29e10e4…`(215) / `sha256:4454c909…`(216) |
| B4 | 目标环境档案 | `target_profile`: windows_build / architecture / isolation / can_build_images |
| B5 | 新容器干净启动 | L1 内 `docker run` 起新容器就绪（L2 证据） |
| B6 | 同镜像跑 Oracle/NOP | **直接复用阶段 A 的 L1 内 Oracle/NOP**（同镜像、同层） |

### 阶段 C：嵌套虚拟化证据（可提前，主体已采）

| 子检查 | 内容 | 状态 |
|---|---|---|
| `outer_guest` | L0 物理机 + L1 VM 标识/拓扑 | ✅ `delivery-evidence-101\L0-host-and-L1-vm.json` |
| `capabilities_exposed` | `ExposeVirtualizationExtensions=True` + L1 内 VBS=2 | ✅ 同上 + `L1-guest-facts.json` |
| `inner_runtime` | L1 内起 L2 容器的命令/日志/终态 | ✅ 跑分容器 + 自检 `L2-OK` |
| `job_binding` | 12 job 的 checksum 绑定嵌套层 | ⏳ 阶段 A 完成后回填 |

字段要求（`validate_nested_virtualization`）：`virtualization_depth ≥ 2`、
`virtualization_extensions_exposed/inner_virtualization_enabled/task_runtime_in_nested_layer` 均须 `true`、
`task_hash` 为 64 位 hex、`configured_image` 与 task.toml 完全一致。

### 阶段 D：静态验收（与 A 并行可跑）

| # | 检查 | 工具 |
|---|---|---|
| D1 | 交付根目录含 `jobs/`（`inspect_delivery.TASK_ROOT_ITEMS`） | `inspect_delivery.py` |
| D2 | `task.toml` 字段：`version/knowledge_tree(三级)/task_type/authors(对象数组)/docker_image` | `static_full_check.py` |
| D3 | 无 `task.toml.bak` 等残留 | 同上 |
| D4 | `required_testcases` ≥5 且含 F2P+P2P | `run_qc.static_check` |
| D5 | `judge.toml:source_sha256` == sha256(`tests/rubric.json`) | `sync_judge_hash.py` |
| D6 | `docker_image` 非 `latest` | `windows_image_policy` |
| D7 | ZIP 内最外层目录名 == ZIP 名去 `.zip` | `check_archive_root_name` |

### 阶段 E：14 项人工质量复核

产出 `quality-review.json`，14 项 `status=PASS` 且每项 `evidence` 非空：

```
golden_nop_expected            rubric_case_correctness
testcase_contract_fairness     hack_free
windows_value                  scope_version_identity
wip94_complete                 dynamic_d01_d20_complete
independent_score_recompute    evidence_retest_integrity
image_delivery                 windows_image_policy
toolchain_in_image             nested_virtualization
```

后 4 项为结构化硬校验（字段见阶段 B/C）；任一 `BLOCKED` → 整体 `BLOCKED`，不得签发 PASS。

### 阶段 F：交付 QC

```
python run_delivery_qc.py --input <pkg> --out <qc_run> --attempts 3 \
       --quality-review <quality-review.json>
```
**通过标准**：`conclusion == PASS`（layout / 12 jobs / model gate / harbor / quality review 全过）

### 阶段 G：打包

```
python package_task_zip.py --task-dir <pkg> --out-dir <dir> --version 1.0.1 --verify
```
校验：ZIP 名与内含根目录同名、无多余顶层目录、`jobs/` 在根。

### 阶段 H：飞书上传

| 项 | 215 | 216 |
|---|---|---|
| 记录 | `reczz28KwEOO3xHy` | `reczz28KQU8reW2k` |
| 附件字段 | `fldnki9xts` | 同 |
| 分数截图 | `fldg4yePGJ` | 同 |
| Oracle/NOP | `fldZI4BCU2` | 同 |

上传后**回读校验**：附件文件名 == 最新 ZIP 名、字节数一致、不是旧版本残留。

### 阶段 I：提交推送

`git add -A` → commit → push `origin main`（HTTPS + PAT + 代理按需）。

---

## 2. 当前状态（2026-10-17 11:20）

| 阶段 | 状态 |
|---|---|
| A 跑分 | 🔄 进行中（L1 内两包并行，`harbor-2ab41b5ac24f` 已起） |
| B 镜像 | ✅ 1.0.1 tag 已在 ghcr；digest 已记录；目标档案待回填 |
| C 嵌套 | ✅ 拓扑证据齐；`job_binding` 待 A 完成 |
| D 静态 | ✅ 34 项 32 PASS（2 项为组装前的 `jobs/` 缺失，属预期） |
| E 质检 | ⏳ 待 A 完成后按真实结果填写 |
| F–I | ⏳ 待 E |

## 3. 已知风险与对策

| 风险 | 对策 |
|---|---|
| L1 重启会清空工作目录 | 跑分中断则重传包+脚本，重跑（脚本幂等） |
| 分差相等或双满 | 不筛选轮次；若出现则需按甲方口径补轮（已记录为唯一可接受的重跑理由） |
| `jobs/` 改动导致 checksum 漂移 | 打包前不再触碰包内文件；ZIP 直接从包目录生成 |
| 匿名拉取证据为 1.0.0 | 需对 1.0.1 tag 重新采集 |
| L1 时区为 UTC-7，L0 为 UTC+8 | job 时间戳以 L1 本地时间记录，交付说明中注明 |
