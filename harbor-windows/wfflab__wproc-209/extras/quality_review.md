# quality_review —— wfflab__wproc-209

质检日期：2026-10-01　｜　题包版本：**1.0**　｜　质检结论：**FLAG**（2 项证据待补）

> 结论含义：题包本体（结构、题面、判分、本地对照、身份一致性）已通过；
> **镜像 Digest（G1）与多模型区分度（G2）两项证据仍在补齐中**，因此暂不能申报最终验收。
> 本题是 `wfflab__wsync-142` 的替换题；替换动因见 `remediation_and_retest.md`。

## 一、选题与反事实判定

| 检查项 | 结论 | 依据 |
|---|---|---|
| 主方向未重复 | PASS | 「进程与执行上下文」为 12 方向中的第 6 个，原 9 题（文件系统与路径、安全与身份、Shell 与自动化、系统管理、编码与区域）均未覆盖 |
| 反事实判定（Windows 价值） | PASS | 五类根因均**只在 Windows 语义下成立**：`Popen.kill()` 只作用于直接子进程（Unix 有进程组/信号）；`communicate()` 依赖管道 EOF 而被后代拖住（Unix 可 `killpg`）；`taskkill /F /T` 为 Win32 专有整树终止手段。换到 Linux 后实现方式、根因与 Evaluator 三者**均改变** |
| 难度来源正当 | PASS | 难度来自 **Windows 进程/管道语义辨析 + 跨模块状态（processes ↔ runner）**，不来自歧义、信息缺失或平台冷知识 |
| 平台语义先实测后出题 | PASS | `scripts/win_probe_proc.py` 6 条假设、5 命中 + 1 刻意对照（详见 `remediation_and_retest.md` 迭代 2） |

## 二、已完成并通过的检查

| 检查项 | 结论 | 证据 |
|---|---|---|
| 标准 Harbor 五件套 | PASS | `task.toml` / `instruction.md` / `environment/` / `solution/` / `tests/` + `platform_import.json` + `extras/` |
| task.toml Schema 1.3 关键字段 | PASS | version / `[metadata]` / `[agent]` / `[verifier]` / `[environment]` / 资源 / 超时 |
| 题面不泄漏解法 | PASS | `instruction.md` 无 Golden / Oracle / 隐藏测试 / F2P-P2P / Reward 表述；只给现象、目标与验收标准 |
| 题面不新增未声明要求 | PASS | 13 条 required 全部可追溯到题面「三类故障 / 目标 3 条 / 验收标准 7 条」，逐条映射见 `testcase_mapping.csv` R1–R13 |
| environment 不泄漏答案 | PASS | `environment/workspace/` 仅含 `wproc` 源码与自带可见测试，无 `solution/`、无隐藏测试 |
| 二值判分 | PASS | `grade.py`：required F2P + P2P 全过 = 1.0，否则 0.0；无权重、无部分分、无 LLM Judge |
| INVALID ≠ 0 分 | PASS | 缺失 / SKIP / 解析失败 → 不写 reward 产物并 exit 2 |
| base 失败 / Oracle 通过（本机 L2 首轮） | PASS | no-change `score=0.0`（pytest 6 failed / 7 passed）；golden `score=1.0`（13 passed） |
| 可见测试未被破坏 | PASS | `tests/test_wproc_basic.py` 在 base 与 golden 下均 **10 passed** |
| 判活手段无竞态 | PASS | 统一用 `_alive(pid)`（`tasklist`）+ `_heartbeat_frozen(hb)`（mtime 冻结），**不用**「删文件再看是否重建」的写法（后者在 pytest 进程内会撞 `WinError 32`） |
| 测试不绑定实现细节 | PASS | 断言只针对系统终态与公共返回值（`timed_out` / `returncode` / `output` / 进程表 / 心跳 mtime），不断言私有函数名、参数个数或调用顺序 |
| 身份三元组一致 | PASS | `task.toml` / `tests/swelive_spec.json` / `platform_import.json` / `extras/metadata/manifest.json` 四处均为 `1.0` + `d6f13ab8…` |
| 官方校验器 `validate_package.py` | 见 `_index/validate-report.json` | 机器报告已生成；本题剩余 FAIL/FLAG 仅为「本文件缺失 + evidence 目录未生成」，即下方 G2 |
| 伴随材料四项 | PASS | `metadata/labels.json` / `source_and_license.json` / `lineage_and_contamination.json` / `manifest.json` + `testcase_mapping.csv`（13 行） |

## 三、证据缺口（阻塞验收）

| # | 缺口 | 影响 | 补齐方式 |
|---|---|---|---|
| G1 | **镜像未构建，`image_digest` 为空** | 无法证明「同一镜像 Digest」下运行；规范 5.5 要求标签之外另存不可变 Digest | 在 Windows 构建机执行 `docker build` 后回填 `_index/EXTERNAL_IMAGES.json` 与 `metadata/manifest.json`（本机 Docker 未启用 Windows 容器模式） |
| G2 | **对照证据矩阵 + 多模型区分度** | 规范第七章要求 no-change ×3 / Golden ×3 / clean_room / 反例 / 等价实现；第八章要求 Qwen/Opus 各 3 次 + GLM/Kimi 各 ≥1 次 | 变体源码与生成脚本已就绪（`assets/wproc-variants/`、`scripts/build_evidence.py` 已泛化为按包名自动定位变体）；**待模型运行结束后串行执行**，避免 CPU 争抢影响计时类用例（见 `_index/known_issues.md` K14） |

### 关于缺口的诚实说明

- 本地对照与 L2 判分是在**真实 Windows（Windows 11 23H2, x64）**上、以**与 `tests/test.ps1` 等价的判定流程**
  （还原 → 应用补丁 → 环境预检 → 清产物 → 运行 → `grade.py` 评分 → 产物完整性校验）执行的。
  **它不是容器内验证**，不能替代 G1 要求的镜像级复现。
- 本题的 required 大量使用时限断言（「耗时 < N 秒」「心跳 2s 内冻结」），
  因此对照证据必须在无并发负载的条件下生成 —— 这也是 G2 排在模型运行之后的直接原因。

## 四、真实模型运行结果（1.0，本机 L2 判分）

同一份题包、同一 40 步 agent 预算，在真实 Windows 上按 `test.ps1` 等价流程判分：

| 模型 | 轮次 | 状态 | 正式分 | pytest | 备注 |
|---|---|---|---|---|---|
| Opus 5 | run-1..3 | 进行中 | — | — | 2026-10-01 19:14 启动 |
| Qwen3.8-Max-0902 | run-1..3 | 进行中 | — | — | 同上 |
| Kimi K3 | run-1 | 进行中 | — | — | 同上 |
| GLM-5.3 | run-1 | 进行中 | — | — | 同上（方舟端强制深度推理，单步耗时长） |

> 本节在运行与判分完成后定稿；门槛判定按规范 8.2：
> ① `Opus5.model_score_sum > Qwen.model_score_sum`；或
> ② 两者均 0 且 `Opus5.testcase_pass_sum > Qwen.testcase_pass_sum`。

## 五、Hack 与答案泄漏审查（四层分级）

| 通道 | 分级 | 依据 |
|---|---|---|
| 联网搜索/下载上游答案 | none | `wproc` 为构造包（`origin_type = authorized_construction`），上游不存在对应答案；运行期 air-gapped |
| 读取本地 Solution / 隐藏测试 / 旧制品 | none | Agent 可见范围内无 `solution/`、无 `test_patch.diff`；工作区 git 历史仅 baseline commit |
| 篡改 Tests / Verifier / 结果文件 | none | `tests/` 位于 `C:\tests`，不在 Agent 工作区内；`grade.py` 只读 `C:\testbed` 产物 |
| 复用旧二进制 / 伪造 PASS | none | 每次运行前 `test.ps1` 删除 `reports/` 与 verifier 产物；评分要求 required 全观测到 |

> 本题最可能出现的两种取巧是：① 只杀直接子进程（`proc.kill()`）而声称「已终止」；
> ② 超时后把输出直接丢掉、只保证进程停下来。两者分别由
> `test_timeout_terminates_the_whole_process_tree` 与
> `test_timeout_preserves_output_emitted_before_the_deadline` 直接否决；
> 对应的对照变体 `negative_01_kill_only_direct_child`、`negative_02_taskkill_tree_but_drop_output`
> 已在 `assets/wproc-variants/` 中备好，将随 G2 一并实测。
> ⚠️ 规范明确「关键词未命中 ≠ 绝对无 Hack」，**模型运行阶段的动态审查在 G2 补齐时一并完成**。

## 六、题面与测试公平性复核

- 每条 F2P 都能从 `instruction.md` 的「故障现象 / 目标 / 验收标准」推出；不存在未声明要求。
- 题面显式排除不考察项（Job Object、`psutil`、WMI、桌面 `tasklist` 之外的进程枚举手段），
  避免把平台冷知识当难度；同时明确「不得改动可见测试」。
- `test_unrelated_processes_are_not_touched` 这一条同时承担**公平性**与**反 Hack** 双重作用：
  它禁止「按映像名批量杀进程」这类会误伤同机其它任务的省事做法。
- 本题已通过 v1.0 首轮 L2：base 精确失败 6 条 F2P、7 条 P2P 全通过；golden 13/13。
