# CHANGELOG —— harbor-windows 题包目录

## [wreparse-217 再次加深：1.2.0 → 1.3.0（D1–D6 激进档）] - 2026-10-09

### 变更原因

1.2.0 按 215 的 L4 设计加深后，四模型 8 场验证**全部满分**（Qwen 3×36/36、Opus 3×36/36、
Kimi 1×36/36、GLM 1×36/36），`run_model_validation.py --score-only` 判定 **False**
（`各模型最终积分相同且不全为 0（Opus 3 vs Qwen 3）`）→ 区分度失败。
根因是加深**只增加了"要检查什么"，没有改变"答案可从文档直接抄出"**这一本质。

### 变更内容（D1–D6）

1. **D1 契约黑盒化**：`docs/REPARSE-CONTRACT.md` 删除 §2/§3/§4/§5/§6/§7 的规则文本，
   改为 **15+ 个实测样例**（8 条 reparse Record 对照、空树完整 JSON、`-MaxDepth` 0/-1/1 三组、
   `-Follow` 的 stats 与 errors、`link-in\readme.txt` 前缀、canonical/within_root 对照、
   `Z/Ä/ö` 实测次序、7 个错误码的实测 Message），并明示"唯一允许照抄的只有 API 签名表"。
2. **D1 题面**：`instruction.md` 的「必须满足的行为」12 条规则复述与「用户可见验收」17 条
   答案式断言全部去答案，改为"只给要覆盖的情形、不给期望值"；新增**验收 18 可复现自证脚本**。
3. **D2 矛盾源**：新增 `docs/REPARSE-CONTRACT.draft.md`（含 9 处与正式契约/实测相反的陷阱，
   如"报告含 GeneratedAt 时间戳"、"`-Follow` 默认开启"、"`LinkType` 非空即重解析点"、
   "直接用 `Sort-Object`"）；`assets/observed-provider-facts.json` 6 → **16 条纯观测**
   （三种文化下的 `Sort-Object` 实测、reparse tag、相对目标解析探测、depth/maxdepth 探测等），
   只给数据不给结论。
4. **D4 夹具**：`tests/prepare.ps1` 新增 8 层深链（`level1..level8` + 两个文件）。
5. **D3 判据**：`tests/run_tests.ps1` +24 条检查 → **60 条**；
   `required_testcases.json` 36 → **60**（45 F2P / 15 P2P）；
   `rubric.json` 9 项权重保持合计 1.0、60/60 全覆盖，`task_version` → 1.3.0。
6. **D5 冒烟测试**：`tests/test_wreparse_basic.ps1` 不再检查 `Records/Errors/Stats` 字段名
   与 JSON 结构，通过它完全无法推断报告形态。
7. **版本与元数据**：`task.toml` / `source.json` / `tests/run_tests.ps1` → **1.3.0**；
   `difficulty` 保持 **L4**、step 上限保持 **40**（与其它题包口径一致）。

### 复验证据

- **本机控制组 3+3**（`_qc_runs/controls_217_v130.json`）：
  Oracle 3 次全部 `VALID` / `formal_score=1` / **60 of 60**；
  NOP 3 次全部 `VALID` / `formal_score=0` / 22 of 60（15 个 P2P 全过 + 7 个 F2P 过）。
- `task_hash` 由 `tree_hash()` 重算（排除 `jobs/` 与 `platform_import.json`）。
- 已砍掉三条不可行判据：`access_denied`（判分进程为管理员会绕过 ACL）、UNC（容器
  bind filter 语义不同）、同名不同大小写决胜（NTFS 不允许同名文件）。

### 待办

- 三模型区分度必须重跑；若仍全满分，需进一步加深（候选方向：删除契约文档、只留 assets）。
- 甲方 QC 动态门禁需 Windows 容器，待环境恢复后重跑。


## [wreparse-217 难度加深 L3 → L4] - 2026-10-09

### 变更原因

`wfflab__wreparse-217` 与 `wfflab__wfmt-215` 同为交付题包，但难度不对等：215 是 **L4**，
217 只有 **L3**。根因在**行为依据的完备程度**——215 的 `docs/FORMAT.md` 是早期草稿、
与真实布局脱节，`assets/` 下的样本才是唯一权威，模型必须逆向；而 217 的
`docs/REPARSE-CONTRACT.md` 把规则逐条写全，模型照抄即可。

甲方 QC 门禁两题都已通过（215：15 项；217：30 项），所以差距不在 QC 是否达标，
而在难度等级本身。

### 变更内容（215 → 217 的 L4 设计复刻）

1. **权威依据分流**：新增 `environment/workspace/assets/observed-provider-facts.json`
   （真机 Windows 11 + NTFS + Windows PowerShell 5.1 实测的 6 条 provider 事实）；
   契约文档新增 §10，声明它只规定**语义**、不规定 provider 层返回值形状，
   两者在实现细节上冲突时以实测事实为准。
2. **自我一致性陷阱**：新增可见冒烟测试 `environment/workspace/tests/test_wreparse_basic.ps1`，
   只验证「模块能导入、报告结构存在、能序列化」。**当前带 23 处契约偏差的实现同样全部通过**，
   与 215「pack 能读回自己的输出、所以可见冒烟测试掩盖问题」同构。
   `instruction.md` 明确声明通过它不代表符合契约。
3. **新增 6 条契约一致性检查**（required 30 → **36**：23 F2P + 13 P2P）：
   模块导出面恰好六个函数（§2）、报告字段集合恰为五项（§3）、排序与宿主 culture 无关
   （§6.1/§6.2）、未给 `-Follow` 时不得报 `cycle`/`broken_target`（§7）、
   普通条目 `InScope` 恒为 `false`（§3.1）、`Target` 类型稳定（§3.1）。
   另把 `target-is-serialised-as-string` 登记为 P2P（合法解修复前后都必须通过）。
4. **夹具增强**：`scanroot` 下新增 `Z.txt` / `Ä.txt` / `ö.txt`。三者的**序数顺序**与
   **区域设置敏感顺序**相反（实测：`Sort-Object` 在 zh-CN 下给出 `Ä, ö, …, Z`，
   序数规则要求 `Z, Ä, ö`），因此把排序委托给 `Sort-Object` 的实现必然失败。
   文件名以字符码构造，避免脚本编码影响。
5. **候选实现新增 5 处可观测偏差**并同步 Golden：导出面放宽为 `*`（psm1 + manifest 两处）、
   用 `Sort-Object` 排序记录、错误列表只按 `Code` 排序、默认扫描也解析目标并报
   `broken_target`、普通条目写入 `InScope`。
6. **版本与元数据**：`task.toml` `difficulty` L3 → **L4**、`[task].version` → **1.2.0**；
   `rubric.json` 新增 `public-surface` 项并把 9 项权重重新配平到合计 1.0；
   `instruction.md` 增补第 9~12 条行为要求与第 12~17 条验收项。

### 复验证据

- **本机控制组**（`_qc_runs/controls_217_v120.json`）：
  Oracle 3 次全部 `VALID` / `formal_score=1` / 36 of 36；
  NOP 3 次全部 `VALID` / `formal_score=0` / 13 of 36（13 个 P2P 全过、23 个 F2P 全挂）。
- **包哈希**：`task_hash = 90354fb76e46943681d514c8f3358a4439d00ec9c1dc8f21d50167bb379eecda`。

### 待办

- 三模型区分度（Qwen ×3 / Opus ×3 / GLM ≥1 / Kimi ≥1）必须重跑，原 `qualified: true`
  （`task_versions: ["1.0.0"]`）不再适用。
- 甲方 QC 工具的动态门禁需要 **Windows 容器**（本机 Docker 当前为 WSL2/Linux 引擎、
  `Containers` 可选功能为 `Disabled`），待环境恢复后重跑。

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
