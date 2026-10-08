# CHANGELOG —— harbor-windows 题包目录

## [范围对齐 + 标准 Harbor 兼容] - 2026-10-08

### 变更原因

1. **目录材料与实物不符**：`README.md` 与 `_index/` 按完整仓库的 9 / 16 题范围编写，
   而本目录实物只有 2 个题包（`wfflab__wfmt-215`、`wfflab__wreparse-217`），
   且原 9 题清单中**没有**这两题。
2. **题包不满足标准 Harbor CLI 契约**：缺 `[task].name`、缺 `[environment].os/workdir`、
   缺 Windows `.bat` 入口，导致 `Task.is_valid_dir()` 为假，`harbor run --path <题包>` 报 `0 tasks`。

### 变更内容（题包侧）

两题统一：

- `task.toml`：`[task]` 增加 `name = "wfflab/<name>"`；`[environment]` 增加 `os = "windows"`、
  `workdir = "C:\\testbed"`；**不设** `[environment].docker_image`，由 Harbor 构建
  `environment/Dockerfile`。顶层 `docker_image`、`[metadata]`、`[agent]`、`[verifier]`、
  `[task] id/setup/test/golden`、`[policy]` 原样保留，本地 runner 不受影响。
- 新增 `solution/solve.bat`、`tests/test.bat`：Windows 容器只发现 `.bat` 入口，二者仅委托对应 `.ps1`。
- `solution/solve.ps1` 增加**可选**参数 `-WorkspaceRoot`：不传时行为与整改前完全一致。

215 专属：无（Dockerfile 已有 `COPY workspace/ → C:/testbed/`）。

217 专属：

- `environment/Dockerfile` 追加 `COPY ["workspace/", "C:/testbed/"]`（原仅 `FROM`/`WORKDIR`/`CMD`，依赖本地 runner 挂载）。
- 新增 `tests/prepare.ps1`（夹具构建器实现迁入）；`environment/prepare.ps1` 改为**转发**到该文件，
  以承接标准 Harbor 缺失的 prepare 阶段，同时保持本地 runner 的调用路径不变。

### 变更内容（目录材料侧）

- `README.md`：题包清单由 9 题改为实际 2 题；新增「范围声明」与「标准 Harbor 兼容」章节；
  重写单题结构树、校验说明与 `task_hash` 规则。
- `_index/tasks_index.csv`：2 题；`task_hash` 改用可复现的**题包定义树哈希**（规则见 README「校验」）。
- `_index/model_summary.csv`、`model_validation_summary.json`、`model_validation_report.md`：
  按 2 题重建；数值取自各题 `jobs/_index/qualification_summary.json` 与
  `jobs/<run_id>/verifier/checks.json`（逐条 `PASS` 计数）。
- `_index/validation_report.md`、`knowledge_tree_coverage_report.csv`：按 2 题重写（覆盖 12 方向中的 2 个）。
- `_index/EXTERNAL_IMAGES.json`：由 10 个题包改为 2 题；记录本机 Image ID 与基础镜像 ID。
- `_index/known_issues.md`：新增范围声明与 K1–K20 逐条适用性对照；题号对照改为本目录 2 题。
- `_index/checksums.sha256`：按 2 题范围重算（515 个文件，含 `jobs/`）。

### 未重算（需注意）

- `_index/validate-report.json` 仍是**旧 9 题范围**的产物（生成它的
  `skills/harbor-windows/scripts/validate_package.py` 未随本目录交付），其中 `PASS=256` 等计数
  对应旧范围；正式验收前须在当前 2 题范围重新生成。

### 已验证（真实 Windows 容器）

- `Task.is_valid_dir()` 两题均为 `True`；`harbor run --path <题包目录>` **单题直跑**成功。
- 镜像由 Harbor 从 `environment/Dockerfile` 构建；215 另经 `docker build --no-cache` 全新构建（11 步）通过。
- 默认环境（**零扩展**）`--agent oracle` → `Reward 1`。
- 控制与门禁：Oracle ×3 = `VALID/1`、NOP ×3 = `VALID/0`（两题），共 12 条 Harbor 运行记录写入 `jobs/`。
- `jobs/` 历史记录的真实原始件（`agent.log` / `checks.json` / `test.log` / `stderr.log`）已回填，
  并以 `test_log_sha256` 逐条对账：215 = 16/16、217 = 17/17 全部匹配。

### 已知遗留（工具侧，非题包侧）

甲方质检包 `windows-harbor-qc` 的静态引用扫描会把脚本/注释中的路径字面量判为「引用缺失文件」
（连注释都算），且静态失败会硬短路动态门禁；其 `markdown_report` 另存在
`task['static']` 键路径不匹配导致的 `KeyError`。详见
`deliverables/2026-10-08_harbor-windows-整改/README.md` 第八节与最小复现脚本。

## [wfflab__wsync-142 → wfflab__wproc-209 替换] - 2026-10-01

### 变更原因（区分度方向不成立）

`wfflab__wsync-142` v2.1 在四个模型上的最终 VALID 结果：

| 模型 | `model_score_sum` | `testcase_pass_sum` |
|---|---|---|
| Opus 5 | 0.0（19/20/22，共 24） | 61 |
| Qwen3.8-Max-0902 | 1.0（24/23/23，共 24） | 70 |

- 准入条件 ① `Opus > Qwen`：`0.0 > 1.0` → **不成立**（方向相反）
- 准入条件 ② 双 0 时比 testcase：Qwen 非 0，前提不成立；即便按 testcase 比，`61 < 70` 亦**不成立**

继续加大难度无法翻转符号（Qwen 在全部已测维度均 ≥ Opus），故按规范 8.2 走**替换**。

### 变更内容

- 新增替换题 `wfflab__wproc-209`：主方向**进程与执行上下文**（12 方向中第 6 个，原 9 题未覆盖）；
  难度 **L5**；语言 Python；任务类型 bugfix；required **F2P 6 + P2P 7 = 13 条**；
  `task_version` 1.0；`task_hash` `d6f13ab8…`；`image_ref` `wfflab/wproc-windows-bench:wfflab__wproc-209-v1.0`。
- 被测包 `wproc` 2.1.0 的三处缺陷：`Popen.kill()` 只杀直接子进程；`communicate(timeout)` 被后代持有的管道拖成假超时；超时分支丢弃截止前输出。
- `wfflab__wsync-142` **保留在仓库中作为过程证据**，`tasks_index.csv` 标记 `replaced`，不参与本轮交付；
  其 `EXTERNAL_IMAGES.json` 条目 `role` 改为 `replaced_archived`。
- 平台端点无需改动：`wproc-209` 与其余题共用同一套多模型端点。

### 已验证（本机 L2，真实 Windows）

- no-change：`VALID` / `score=0.0` / pytest **6 failed + 7 passed**（89.5 s）—— F2P 全失败、P2P 全通过，正是设计意图。
- Golden：`VALID` / `score=1.0` / pytest **13 passed**（69.9 s）。
- 可见测试 `tests/test_wproc_basic.py` 在 base 与 golden 下均 **10 passed**。
- 平台语义先实测后出题：`scripts/win_probe_proc.py` 6 条假设、5 命中 + 1 刻意对照（`read` 阻塞丢数据 vs `read1` 读多少算多少）。
- `validate_package.py`：**PASS=284 / FAIL=0 / FLAG=5**（FLAG 全部为本题 `extras/evidence/` 五个子目录待生成）。

### 已知未完成

- 镜像仍未构建（`image_digest` 待回填，见 `known_issues.md` K1）。
- `wproc-209` 的对照证据矩阵与多模型区分度待出（见 `known_issues.md` K2/K3/K14）。
- 细节见 `wfflab__wproc-209/extras/remediation_and_retest.md` 与 `quality_review.md`。

## [wfflab__wsync-142 2.0 → 2.1] - 2026-10-01

### 变更原因（区分度不达标）

v1.0 的多模型实测显示 16 条 required 对主流模型过于宽松：Opus 5 三次全部 1.0
（`model_score_sum = 3.0`），Qwen3.8-Max-0902 与 Kimi K3 也均为 1.0。
按规范 8.2，「Opus > Qwen」与「双 0 且 testcase 严格区分」两个准入条件均不成立，
该题区分度不满足准入要求，须整改或替换。经确认采取**整改**路线。

### 变更内容

- `task_version` 1.0 → 2.0；`task_hash` `a06c9ab7…` → `ec4941c1…`；
  `image_ref` → `wfflab/wsync-windows-bench:wfflab__wsync-142-v2.0`。
- required 由 16 条（F2P 7 + P2P 9）扩到 **24 条（F2P 15 + P2P 9）**，新增 8 条 F2P：
  - 只读空目录清理
  - 文件↔目录类型冲突（含仅大小写不同、祖先分量被文件占住）
  - 冲突清理不得误伤无关条目
  - 同尺寸同 mtime 但内容不同必须更新
  - 幂等 + 源 mtime 保真
  - 只读且被占用时必须与「可修复的只读」精确区分
- `instruction.md` 重写，新增症状与验收标准均**完整声明**；未引入题面未声明要求或冷门陷阱。
- `solution/oracle.patch` 重写（`fsops` 增加内容比对/时间戳对齐/类型冲突清障，`planner` 改为内容级变化判定，`mirror` 增加冲突消解与 KEEP 时间戳巡检）。
- `environment/workspace/` 与 `environment/Dockerfile` **未改动**。
- 难度标注 L4 → **L5**（L1–L5 为出题方自定分级，**归纳编号**，规范原文未定义）。
- 细节与实测依据见 `wfflab__wsync-142/extras/remediation_and_retest.md` 迭代 3。

### 追加修正（由真实模型运行反查，同日）→ 升级为 **2.1**

- 两条大小写用例原先写死终态的**名字大小写**（要求保留目标侧原名），超出题面声明
  「文件存在、内容正确、条目不多不少」。已改为大小写不敏感的等价断言；
  `test_patch.diff` hunk 行数 `+1,428` → `+1,440`。
- 影响：Opus 5 `run-1` 由 18/24 → **19/24**（仍不通过 F2P）；`negative_03` 由 18/24 → 20/24。
  其余对照（no_change 0 / golden 1 / negative 0 / equivalent 1）不受影响。
- 按 `task.toml` 自定约定「影响 Tests 的修改必须升级 version」，`task_version` **2.0 → 2.1**，
  身份三元组随之更新为 `478e5057…`，`image_ref` → `…-v2.1`，四处身份文件与
  `_index/checksums.sha256` 已重新落盘。题面与 oracle **未改动**。
- 细节见 `remediation_and_retest.md` 迭代 5；经验已记入 `_index/known_issues.md` K11。

### 已验证

- no-change 独立 3 次均为 0（P2P 全过、15 条 F2P 全失败）；Golden 独立 3 次均为 1；
  干净重建复验一致；3 类反例均 0 分；等价实现（结构不同的写法）得 1 分。
- **v1 解法在新 required 集上失败 7 条**，作为反例 `negative_01_readonly_only` 固化。
- 真实模型：Kimi K3 `run-1` 得 **1.0（24/24）**，证明题目可解；
  Opus 5 `run-1` 得 **0.0（19/24）**，失败集中在类型冲突的删除时序与 mtime 保真。

### 已知未完成

- 镜像仍未构建（`image_digest` 待回填）。
- 多模型区分度复验进行中，结果见 `_index/model_validation_report.md`。

## [目录结构] - 2026-10-01

### 变更
- 取消批次层（原 `delivery-wffw-0001-v1.0` / `delivery-wffw-0002-v1.0`），
  9 个题包平铺为**自包含**目录，彼此独立、互不影响。
- 每题结构：五件套（`task.toml` / `instruction.md` / `environment/` / `solution/` / `tests/`）
  + `platform_import.json`（平台导入 JSON）+ `extras/`（题级伴随材料）。
- 跨题汇总材料移至 `_index/`。
- **身份不变**：9 题的 `task_id + task_version + task_hash` 与调整前完全一致。

## [1.0] - 2026-10-01

### 新增（9 题）
- `wfflab__wpathext-204`：构建工具按名字找不到非 .exe 的可执行文件。主方向：Shell 与自动化；难度：L4；语言：Python；任务类型：bugfix；required F2P 7 条、P2P 6 条。
- `wfflab__wps-207`：PowerShell 步骤失败仍然被判定为成功。主方向：Shell 与自动化；难度：L4；语言：Python；任务类型：bugfix；required F2P 7 条、P2P 6 条。
- `wfflab__wacl-203`：共享目录发布未让只读权限覆盖整棵子树。主方向：安全与身份；难度：L4；语言：Python；任务类型：bugfix；required F2P 7 条、P2P 6 条。
- `wfflab__wsync-142`：属性 / 命名 / 共享语义。主方向：文件系统与路径；难度：L4；语言：Python；任务类型：bugfix；required F2P 7 条、P2P 9 条。
- `wfflab__wreserved-201`：上传服务把 Windows 保留设备名当成普通文件名。主方向：文件系统与路径；难度：L4；语言：Python；任务类型：bugfix；required F2P 7 条、P2P 8 条。
- `wfflab__wads-202`：下载文件归档时丢掉 NTFS 备用数据流。主方向：文件系统与路径；难度：L4；语言：Python；任务类型：bugfix；required F2P 7 条、P2P 6 条。
- `wfflab__wrotate-208`：目标序号已有残留时日志轮转失败。主方向：文件系统与路径；难度：L4；语言：Python；任务类型：bugfix；required F2P 7 条、P2P 6 条。
- `wfflab__wreg-205`：读不到 32 位程序写下的注册表配置。主方向：系统管理；难度：L4；语言：Python；任务类型：bugfix；required F2P 6 条、P2P 6 条。
- `wfflab__wencoding-206`：按平台默认编码写文本导致非 ASCII 内容损坏。主方向：编码与区域；难度：L4；语言：Python；任务类型：bugfix；required F2P 7 条、P2P 6 条。
- 标准 Harbor 五件套（schema 1.3）。
- 题级六项伴随材料（metadata / evidence / model_runs / testcase_mapping / quality_review / remediation_and_retest）。

### 已验证
- `wfflab__wsync-142`：no-change 独立 3 次均为 0；Golden 独立 3 次均为 1；干净重建复验一致；
  4 类错误反例均 0 分；等价实现得 1 分。
- 其余 8 题：完成静态结构校验（五件套 / 题面不泄漏 / 身份三元组一致），未执行运行时验证。

### 已知未完成
- 镜像未构建（`image_digest` 待回填）。
- 8 题对照验证未执行；9 题多模型区分度验证未执行。

## 2026-10-02 替换链第三棒：新增 wfflab__wstamp-211（NTFS 时间戳语义）

- `wfflab__wstamp-211`：备份工具库 wstamp 的「同步状态 = 内容 + mtime」缺陷族 +
  Win32 属性事务。主方向：文件系统与路径；难度：L4；语言：Python；bugfix；
  required F2P 8 条、P2P 8 条；task_hash 9a381fd5cce5…。
- 选题依据：多模型运行数据中 Qwen3.8-Max-0902 的唯一失手模式
  （wsync-142 上 test_sync_is_idempotent_and_preserves_source_mtime 3 轮挂 2 次，
  同步只比较内容、漏 mtime 回写分支）；其余考点位于 Opus 已验证可靠区。
- 本机验证：base 8F2P 全失败 / 8P2P 全通过；oracle 全过；
  L2 nochg 0.0 / golden 1.0；对照证据 12 项全符合预期（3 反例 0.0、等价 1.0）。
- 替换链状态：wsync-142（replaced）→ wproc-209（判死）→ winstall-210（判死）→ wstamp-211（验证中）。
