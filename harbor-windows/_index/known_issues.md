# known_issues —— harbor-windows 题包目录

| # | 级别 | 问题 | 影响范围 | 处置建议 |
|---|---|---|---|---|
| K1 | 阻塞验收 | 10 个镜像均未构建，`image_digest` 为空（当前 `PENDING_BUILD`） | 无法满足规范 5.5「另存不可变 Digest」 | 在 Windows 构建机对 10 题分别执行 `docker build` 后回填 `_index/EXTERNAL_IMAGES.json` 与各题 `extras/metadata/manifest.json` |
| K2 | 阻塞验收 | 8 题（wreserved-201 ~ wrotate-208）的对照验证未执行（no-change ×3 / Golden ×3 / 反例 / 等价实现）；`wproc-209` 已过本机 L2 首轮（no-change 0.0 / Golden 1.0），完整对照矩阵生成中 | 无法证明「base 失败、参考解通过」 | 平台 harness 在真实 Windows Runtime 中执行 `test.ps1` + `grade.py` 并回填各题 `extras/evidence/` |
| K3 | 阻塞验收 | 9 题的多模型运行记录为空（Qwen/Opus 各 3 次 + GLM/Kimi 各 ≥1 次未执行）；`wsync-142` 与 `wproc-209` 两题已完成/进行中 | 无法计算区分度准入 | 平台 harness 回填正式分后运行 `run_model_validation.py --score-only` |
| K4 | 提示 | `wfflab__wsync-142` 与 `wfflab__wproc-209` 的对照验证在本机物理机 Windows 11 上完成，非容器内 | 不能替代镜像级复现 | 镜像构建完成后，在容器内重跑 no-change 3 次 + Golden 3 次 |
| K5 | 提示 | 9 题均不依赖 `harbor-rewardkit`，采用自包含 `grade.py` | 与骨架「Harness = harbor-rewardkit==0.1.7」的默认声明不同 | 已在各题 manifest `frozen_baseline.harness` 如实声明；如平台要求统一 Harness，需在联调时确认 |
| K6 | 提示 | 部分题目依赖 Windows 默认语义（大小写不敏感 NTFS 目录、en-US 代码页 1252、`PATHEXT` 默认值） | 若评测环境改写这些默认值，对应 F2P 的失败路径可能不成立 | 构建镜像时不得开启按目录大小写敏感、不得改 `PATHEXT`、保持 en-US 非 Unicode 程序语言设置 |
| K7 | 提示 | 多模型端点与凭据：aliyun MaaS（Qwen）、ebondai（Opus 5）、火山方舟（GLM-5.3 / Kimi K3）凭据均已就位，存于**仓库外**的用户级目录 `~/.workbuddy/harbor-windows-endpoints.json`，**未入库**。⚠️ GLM-5.3 在方舟上**不能传 `thinking` 字段**：`enabled` 会让方舟忽略 `budget_tokens` 并强制深度推理（thinking 涨至约 9.7 万字符吃光 max_tokens，每步 `content` 恒为空、`finish_reason=length`），`disabled` 直接 400；不传该字段时模型自行判断即可正常产出 `tool_use`。 | 端点配置错误会让辅助模型误判为「模型能力失败」并记 INVALID | 端点 JSON 已按此修正并在 `_notes` 中固化说明；如需复现请勿再添加 `thinking` |
| K10 | 提示 | `wfflab__wsync-142` 于 2026-10-01 因区分度不达标由 1.0 整改为 2.0（required 16 → 24），随后因测试公平性修正升为 **2.1**（`task_hash` 最终 `478e5057…`） | 该题的 `task_version` / `task_hash` / `image_ref` 已多次改变，历史 1.0 的镜像标签与运行记录不再对应 | 引用该题时一律以 **2.1** 身份为准；v1 运行快照见 `wfflab__wsync-142/extras/_v1_model_runs_snapshot.json` |
| K11 | 重要经验 | **隐藏测试可能「超出题面」而把合法实现判错**：`wfflab__wsync-142` v2.0 的两条大小写用例原先写死 `files_under(target) == ["notes.txt"]`，等于要求终态保留**目标侧**原有名字大小写；而题面只声明「文件存在、内容正确、条目不多不少」。真实模型 Opus 5 的实现终态取源侧大小写（在 Windows 上是同一条路径），被误判失败 | 任何依赖「我方 oracle 恰好怎么写」的断言都会压低所有模型分数，并污染区分度结论；这类缺陷**静态看不出**，只有跑真实模型才会暴露 | 断言一律只针对**题面已声明的可观测量**；遇到等价但写法不同的终态（大小写、顺序、等价 API）必须做等价化处理。详见 `wfflab__wsync-142/extras/remediation_and_retest.md` 迭代 5 |
| K12 | 提示 | agent 沙箱内执行 `python -m pytest` 时会命中宿主会话的 `CODEBUDDY_SAFE_DELETE_BULK_GUARD`（清理 `Temp\pytest-of-Administrator\garbage-*` 时被批量删除守卫拦下，1937 项 > 阈值 50），表现为**用例全过但退出码为 1、且丢失汇总行**，会误导被测模型 | 只影响被测 agent 的自我验证观感；**不影响判分链路**（`l2_runner.py` 直连 pytest，实测 no_change 9/24、golden 24/24 均干净） | 如需消除噪声，可在 `agent_harness` 的 `run_command` 子进程中剔除 `CODEBUDDY_SAFE_DELETE_BULK_GUARD` 与 PATH 里的 `vendor/shim` 目录 |
| K8 | 提示 | 部分 base repo 自带的 `README.md` / 模块 docstring 描述了设计契约（例如 `wjob` 说明 PowerShell 退出码语义、`wrotate.fsutil` 说明「目标已存在时也应成功」） | 与 `instruction.md` 的验收标准同源，构成「题面已声明要求」的另一种表述；不构成 Solution / 隐藏测试泄漏 | 已按规范判定为不越界；如质检人认为需进一步弱化，可在下一版本改写这些文档并升级 `task_version` |
| K9 | 提示 | 9 题的被测包均为构造代码，缺少真实上游仓库与 Issue/PR | 与「从真实 Issue 出题」的理想形态有差距 | 已在各题 `source_and_license.json` 的 `origin_type = authorized_construction` 如实声明，属规范允许的定向构造场景 |

| K13 | 阻塞验收 | `wfflab__wsync-142` 按规范 8.2 判定为**不可交付**（Opus `model_score_sum` 0.0 / testcase 61 vs Qwen 1.0 / testcase 70，两个准入条件均不成立），已**替换**为 `wfflab__wproc-209` | 该题封存，不参与本轮交付；9 题交付集变为 8 题旧题 + `wproc-209` | `tasks_index.csv` 中该题标记 `replaced`；替换动因与论证见两题各自的 `extras/remediation_and_retest.md`（wsync-142 迭代 6/7、wproc-209 迭代 1） |
| K14 | 重要经验 | **本地并发运行会互相干扰计时类用例**：`wproc-209` 的 required 大量使用「耗时 < N 秒」「心跳 mtime 是否冻结」这类时限断言；若在模型运行仍在进行时并发跑对照证据生成，CPU 争抢可能让合法的边界用例超时 | 可能产生假失败，污染对照矩阵 | 对照证据生成必须**串行排在模型运行之后**执行（本目录已按此约定安排） |
| K15 | 重要经验 | **`nohup ... &` 启动的长任务会被回收**（2026-10-01 第二次踩坑，静默 75 分钟）：分片运行挂在 shell 后台时，随该次工具调用的 shell 一起被杀，且不写 `meta.json`；多路并行会**同时静默**，外形上像「端点挂了」 | 浪费整段等待时间；若不带 `--skip-existing` 还会把已完成的 run 重跑一遍 | 一律用 agent 工具**自带的**后台执行能力直跑前台命令，**不要 `&`、不要 `nohup`**；重启必带 `--skip-existing`；存活判据 = `tasklist` 里 python 非零 **且** `trajectory-run-N.jsonl` 的 mtime 在推进（冻结即已死）。详见 `skills/harbor-windows/references/08-model-validation.md` 7.8 |
| K17 | 阻塞验收 | `wfflab__wencoding-206` 按规范 8.2 判定为**不可交付**：Opus 与 Qwen **双双 3.0**（Opus 1.0/1.0/1.0、Qwen 1.0/1.0/1.0，各 13/13）→ 条件 1 要求严格大于、不成立；条件 2 要求双方均为 0、亦不成立。属**难度不足（薄题）**，而非质量问题 | 该题不参与本轮交付 | 按既定口径**加大难度**：在 `instruction.md` 已声明的「编码与区域」边界内加深验收标准（BOM 与 append 交互、别名归一化、BOM 读取剥离语义等），升 `task_version` 后重跑 L2 + 三模型。⚠️ 红线：**不得增加题面未声明的要求**，新增项必须同步写入 `instruction.md` 的验收标准 |
| K16 | 阻塞验收 | `wfflab__wproc-209` 按规范 8.2 判定为**不可交付**：Opus `model_score_sum` 0.0（3 轮均 12/13，稳定失手同一条 F2P）vs Qwen run-1 已 `1.0`（13/13），条件 1 与条件 2 均不成立；GLM-5.3 / Kimi K3 均为 1.0，说明链路与题目本身可用，属**真实能力差异**而非基建故障 | 该题不参与本轮交付，待 Qwen 补满 3 轮后封存 | 已启动替换：`wfflab__wencoding-206`（Opus 3/3 = 1.0，主推）与 `wfflab__winstall-210`（Opus 1.0/0.0/1.0 = 2.0，备选） |

| K18 | **阻塞验收（根因）** | **8.2 区分度在当前端点配置下无法满足，根因在 Opus 5 端点而非题目**。全仓 16 题实跑统计：Qwen3.8-Max-0902 逐检查错误率 **0.41%**（3/730），Opus 5（ebondai）**6.57%**（26/396）—— 相差约 16 倍；逐 testcase 交叉比对**不存在任何「Qwen FAIL 且 Opus 全 PASS」的用例（0/16 题）**。SKILL.md 指定的 opus 提供方 `api.blvr.top` 凭据已失效（HTTP 401 Invalid token），`api.ebondai.com` 是唯一可用端点。规律：题目易→双方 3.0 同分（严格大于不成立）；题目难→Qwen 得 1–2 而 Opus 掉 0，**不存在中间带** | 全部 16 题均无法通过 8.2，本轮无题可交付 | **换题无用**。需提供健康的 Opus 5 端点凭据后重跑；详见 `deliverables/2026-10-04_harbor-windows-区分度诊断/DIAGNOSIS.md` |
| K19 | 重要经验 | **已排除的三种「提分」假设（全部实测反效果或无效）**：① 加倍 agent 回合预算（`--agent-max-steps 80`）→ Opus 在 wfmt-215 由 12/15 降到 9/15，行为退化为命令空转（46–60 次 `run_command`、0–3 次 `write_file`）；② 在 system prompt 中显式鼓励并行工具调用 → 并行度确实从 1.2 升到 1.9 工具/回合，但 wsync-142 通过数由 19–22/24 腰斩到 9/24（改动已回滚）；③ 加大难度：Opus 失败比 Qwen 更早更猛，加大难度只会把「持平」变成「Qwen 胜」 | 避免后续重复试错 | 端点修复前不要再在出题侧找解 |
| K20 | 提示 | `wfflab__wtask-216`（本次新建，Windows 计划任务调度语义引擎）结构完整、可复现：no-change ×3 = 0.0、Golden ×3 = 1.0（均 VALID）、Qwen/Opus/GLM/Kimi 全 1.0；`validate_package.py` PASS=393 / FAIL=1（缺 delivery-extras）。**8.2 判定为 FAIL（Opus 3.0 vs Qwen 3.0，同分且非 0）**，属难度不足（薄题），同样卡在 K18 | 该题不参与本轮交付，但可在端点修复后直接复用 | 若端点恢复且需要对上「非满分」的 Qwen，可优先复用 `wfmt-215`(Qwen 2.0) / `wproc-209` / `winstall-210` |

## 题号对照

`wfflab__wproc-209`（**替换 wsync-142，本轮交付**）、
`wfflab__wreserved-201`、`wfflab__wads-202`、`wfflab__wacl-203`、
`wfflab__wpathext-204`、`wfflab__wreg-205`、`wfflab__wencoding-206`、`wfflab__wps-207`、
`wfflab__wrotate-208`；`wfflab__wsync-142`（已 replaced，封存）
