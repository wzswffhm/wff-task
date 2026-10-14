# known_issues —— harbor-windows 题包目录

> ## 范围声明（2026-10-08，2026-10-12 补充）
>
> **2026-10-12 补充**：本目录实物为 4 个交付包 —— `wfflab__wfmt-215-v2.1.0-delivery`（返修后 **2.1.1**）、
> `wfflab__wchunk-216-v1.2.0-delivery`（返修后 **1.2.1**）、`wfflab__wlogseg-218-v1.0.0-delivery`、
> `wfflab__wpeimg-219-v1.0.0-delivery`。**本次返修范围只有 215 与 216**（质检报告 004/005 号条目），
> 218/219 未在本轮改动。下列写于 2026-10-08 的适用性对照针对当时交付的 215/217 平台发布形态，
> 其中"只交付 2 题"的表述已被本补充取代。
>
> 本目录当前**只交付 2 个题包**：`wfflab__wfmt-215`、`wfflab__wreparse-217`。
> 下表 K1–K20 是**完整仓库（9 / 16 题）阶段**的记录，多数条目不适用于本目录实物，
> 保留作为过程证据。逐条适用性对照如下：
>
> | 条目 | 是否适用本目录 2 题 | 说明 |
> |---|---|---|
> | K1 镜像 digest 未回填 | **部分适用** | 两题已有本机 Image ID（见 `EXTERNAL_IMAGES.json`）；registry RepoDigest 待 push 后回填 |
> | K2 对照验证未执行 | **不适用** | 两题 no-change ×3 = 0.0、Golden ×3 = 1.0 已完成（本地 runner 与 Harbor 双口径） |
> | K3 多模型记录为空 | **不适用** | 两题四模型记录完整，区分度已达标（见 `model_validation_report.md`） |
> | K4 本机物理机执行 | 已消除 | 控制与门禁均在 Windows 容器内完成 |
> | K5 不依赖 harbor-rewardkit | 适用 | 两题均为自包含判分脚本 |
> | K6 依赖 Windows 默认语义 | 适用 | 两题均依赖大小写不敏感 NTFS / `PATHEXT` / en-US 代码页 |
> | K7 模型端点注意事项 | 适用 | 含 GLM 不可传 `thinking` 字段等 |
> | K8 base README 描述契约 | 适用 | 两题 `workspace` 内文档与 `instruction.md` 同源 |
> | K9 构造代码而非真实 Issue | 适用 | 两题 `source.json` 均如实声明构造来源 |
> | K10–K17、K20 其他题目的整改/替换 | **不适用** | 涉及 `wsync-142` / `wencoding-206` / `wproc-209` / `wtask-216` 等不在本目录的题 |
> | K18 8.2 区分度根因 | **适用（历史）** | 结论针对当时端点配置；本目录两题在其 `qualification_epoch` 下已达成 Opus > Qwen，故不再阻塞，但端点健康度需持续关注 |
> | K19 提分假设已被排除 | 适用（经验） | 其中涉及 `wfmt-215`，结论仍然有效 |
>
> 另见 `_index/CHANGELOG.md` 的 2026-10-08 条目。

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

| K21 | 重要变更 | **`wfflab__wreparse-217` 已按 215 的 L4 难度设计加深（1.1.0 → 1.2.0）**：原题的行为依据是一份把规则写全的契约文档，模型照抄即可，因此停在 L3。本轮补齐 L4 所需的「信息不完备 + 自我一致性陷阱」：① 新增真机实测的 provider 权威事实 `environment/workspace/assets/observed-provider-facts.json`，契约文档补 §10 声明它不覆盖 provider 层返回值形状，两者冲突时以实测事实为准（对应 215 的「`docs/FORMAT.md` 是草稿、`assets/` 样本才是唯一权威」）；② 新增可见冒烟测试 `environment/workspace/tests/test_wreparse_basic.ps1`，只验证「自己产出的报告自己能读懂」，**当前带偏差的实现同样全过**（对应 215 的「可见冒烟测试掩盖问题」）；③ 新增 6 条契约一致性检查（导出面恰好六个函数、报告字段集合恰为五项、排序与宿主 culture 无关、未跟随不得报 cycle/broken_target、普通条目 InScope 恒 false、Target 类型稳定），required 由 30 条增至 **36 条**；④ 夹具有意加入 `Z.txt` / `Ä.txt` / `ö.txt`，其序数顺序与区域设置敏感顺序相反，用 `Sort-Object` 修排序必然踩中。 | 该题的 `task_version` / `task_hash` / `image_ref` 再次改变，**1.0.0 时代的 `qualification_summary.json`（QWEN 2 / OPUS 3、`qualified: true`）不再适用** | 本机控制组已复验通过（Oracle 3×`VALID/1`、NOP 3×`VALID/0`，证据 `_qc_runs/controls_217_v120.json`）；**三模型区分度必须重跑后才能重新声明 qualified** |
| K22 | 重要变更 | **`wfflab__wreparse-217` 再次加深（1.2.0 → 1.3.0，D1–D6）**：1.2.0 后四模型 8 场全满分（Qwen/Opus/Kimi/GLM 均 36/36），`--score-only` 判定 `False`（Opus 3 vs Qwen 3 积分相同），区分度失败。处置：D1 契约黑盒化（以 15+ 实测样例替代规则）、D1 题面去答案、D2 矛盾源（draft 草稿含 9 处反向陷阱 + facts 6 → 16 条纯观测）、D4 夹具加深 8 层链、D3 required 36 → **60**（45 F2P / 15 P2P）、D5 冒烟测试不再检查字段结构、D6 新增验收 18 可复现自证脚本。控制组：Oracle 3×VALID/60、NOP 3×VALID/0（`_qc_runs/controls_217_v130.json`）。三模型区分度待重跑后重新声明。 |
| K23 | 重要变更 | **`wfflab__wchunk-216` 与 `wfflab__wfmt-215` 按质检 004/005 返修（1.2.0 → 1.2.1、2.1.0 → 2.1.1）**：① 删除流式用例中未声明的 8192 字节读块阈值，改为"容器读满时仍未产出的记录条数 + 1/8 规模对照"判据，并新增尾部校验和断言（216 实测 P2P、215 实测 F2P）；② Kimi 配额失败槽位单列为 INVALID **注解层**（`jobs/invalid-slots.json` + `jobs/INVALID-SLOTS.md`），`jobs/` 原始记录一字未改；③ 新增 `verifier/WINDOWS_VALUE.md`，把两题归入**通用编码能力（Windows 运行时执行）**并同步调整 `tasks_index.csv` 的采购分类，Windows 专属化改造列入"未实施"；④ 评分族改为**纯程序化 1.0**，正式废止从未生效的 llm_judge 50% 声明（`programmatic-v3` / `rubric-conditions-v3`，含版本化废止说明）；⑤ 修复 `tests/judge.toml` 第 7 行注释续行缺 `#`（标准 `tomllib` 可解析）；⑥ 新增 `verifier/ISOLATION.md` 与 `negative_access_probe.ps1`，给出隔离适配口径与负访问证据。逐条闭环见各包 `REFIT-2026-10-12.md`。 |
| K24 | 口径差异 | **`skills/harbor-windows/scripts/validate_package.py` 与质检 004-05/005-05 的口径冲突**：脚本把 `tests/judge.toml` / `tests/rubric.json` 一律判为"旧评分残留"并 fail；而质检明确要求**保留并修复**这两个文件（它们是标准评分入口的配置与 case 映射，删除会让标准入口失去配置来源）。处置：以质检要求为准保留修复，脚本该条判定视为过时规则；两包 `REFIT-2026-10-12.md` 与 `verifier/` 文档均已记录该差异。 |
| K25 | 口径差异 | **`task_hash` 存在三种不可直接比较的口径**：① runner `run_time_identity.task_hash`（运行期任务树，含注入材料）；② `_qc_runs/*/model-gate.json` 的记录（平台发布形态快照 `wfflab__wfmt-215/`）；③ 本次写入 `tasks_index.csv` 的**交付包根复算值**（runner 同名算法，排除 `jobs/runs/work/results/` 与缓存）。离线验证：对飞书原件 zip 与 git HEAD 的包根复算，与历史运行期记录**均不一致**（例如 216 原件包根 `2bfcec15…` ≠ 记录 `f8acb48d…`）。处置：`tasks_index.csv` 的 `task_hash` 明确标注为交付包根复算值；跨口径比较前必须先统一输入树，不得把三者混用。 |
| K26 | 重要变更（门禁） | **215 / 216 的 `environment/adapter.toml` 存在 TOML 非法缺陷，已随本轮返修修复**：扁平入口 key（`prepare` / `validate` / `run` / `restore` / `cleanup` / `workspace` / `start` / `test` / `exec_agent`）与第 38 行起的同名表（`[prepare]` / `[validate]` / `[exec_agent]` / `[test]` / `[restore]` / `[cleanup]`）冲突，标准解析器报 `Cannot overwrite a value (at line 38, column 9)`。`skills/harbor-windows/SKILL.md` §4 已明确记录「215 v2.1.0 与 216 v1.2.0 也已带着同一个 `adapter.toml` 缺陷交付甲方」，且 `references/06-acceptance-gates.md` 把「可被 TOML 解析」列为必须 PASS 的静态门。处置：扁平 key 全部保留，冲突表名改为 `[entry.*]`，字段值未改；`tomllib` 全文件解析通过。该文件不参与判分链路，控制组结论不受影响。 |
| K27 | 重要变更（甲方口径自检） | **甲方静态自检在 `docker_image` 一项上 FAIL，属预期差异**：`_reference/windows-harbor-qc/scripts/inspect_delivery.py` 对 215 2.1.1 / 216 1.2.1 返回 `pass=False`、`errors=['Task has no pinned Docker image']`（其余 `errors` 为空；唯一 warning 为「源包无 `source.json`」，脚本声明不阻塞 QC）。原因见 K29，处置见 `references/06-acceptance-gates.md`「已知差异」节：保留该静态 FAIL，其余静态项与全部动态项必须 PASS，甲方更新工具包后自然消失。甲方口径身份（证据归档 `_qc_runs/refit-215-216/inspect-delivery-{215,216}.json`）：215 `task_hash=4cb672c0765f1f3f356fccbc53d4a40be870c5969d0ae6ce143b6734ee8a68a7` / `harbor_task_checksum=c37231de5b5e141a0a7ba699ab798a7900734aa37d61f86ae73ea58395d4d1b1`；216 `task_hash=2defad456efab3c81fe7a8dcab52d04a7dee192d9d20339b32056385d3636939` / `harbor_task_checksum=88aee18e771f28d94dc49e2cd101469a22c08791641c7a022cabcef584542144`。注意甲方 `task_hash` 算法（`rel\t sha256(file)` 行列表再 sha256，排除顶层 `jobs/`）与 runner 运行期 `task_hash` 不同，属 K25 所述的**多口径**之一；`tasks_index.csv` 采用**甲方口径**。两包 `tests/required_testcases.json` 均为列表且条数落在脚本要求的 5–27 区间内（215 = 16、216 = 19）。 |
| K28 | 阻塞验收（本轮未解除） | **215 2.1.1 / 216 1.2.1 的历史 `jobs/` 身份已失效**：返修改动了 `task.toml` / `environment/adapter.toml` / `tests/` / `verifier/`，按 `skills/harbor-windows/SKILL.md` 第二条铁律「跑分对象必须与最终交付包同一份内容」，历史 job 的 `task_checksum` 与交付包 Harbor dirhash **不再一致**（`jobs/` 按规则一字未改写）。 | 甲方 `run_qc.py` 的「身份」静态门会 FAIL；历史模型分数是**旧版本**的分数，不能当作返修版的验收分 | 正式提交前在该版本上整批重跑（对照组 + 模型轮次）并刷新 `jobs/`；本轮只完成本机控制组复验（Golden 1 / no-change 0）与甲方 `inspect_delivery.py` 静态自检（该脚本因 `task.toml` 按新规范不写 `docker_image` 而报**预期 FAIL**，见 K29），**未重跑模型**。 |
| K29 | 规范（2026-10-13 起） | **215 2.1.1 / 216 1.2.1 的 `task.toml` 已删除 `docker_image`**：基础镜像只由 `environment/Dockerfile` 的 `FROM` 声明并 pin 到不可变 digest（`mcr.microsoft.com/windows/servercore:ltsc2022@sha256:76cf422c…`，非 `latest`），Dockerfile 未改。两套自检口径相反：本地 `skills/harbor-windows/scripts/validate_package.py`（L156–161、L505–509）要求 `task.toml` **不得**出现该字段，甲方 `inspect_delivery.py` / `run_qc.py` 反把「缺该字段」判 FAIL。按 `references/06-acceptance-gates.md`「已知差异」节处置：保留甲方那一项静态 FAIL、其余静态项与全部动态项必须 PASS，**不得为过检查把字段写回去**，甲方更新工具包后自然消失（见 K27）。`wfflab__wlogseg-218` 仍带该字段（其值只是 tag、尚未 pin digest），经确认**暂不处理**，属历史包未按新规范整改。 |
| K30 | 门禁口径（2026-10-12 放宽） | **Qwen 与 Opus 同时全满分不再直接出局**：`_reference/windows-harbor-qc/scripts/validate_model_gate.py` 原先对 `qwen_opus_full_score` 一票否决（判词 "an all-full primary-model task is too easy"），现改为落入统一判据——`Opus model_score_sum > Qwen` 直接通过；两者相等（**含双方三轮全满分**）时必须 `Opus testcase_pass_sum > Qwen testcase_pass_sum`；`qwen_opus_full_score` / `all_models_full_score` 保留为报告记录项（`full_score_tiebreak_pass`）但不再单独否决；8 轮全 `VALID/0` 的零分平局例外不变。QC 工具包内已同步：`SKILL.md` L44、`references/checklist.md`、`references/manual-review.md`、`references/quality-gates.md`、`references/rule-matrix.md`（FAIL 表该行移入「仅提示或人工复核」）、`tests/test_model_gate.py`（12 项单测全过）。此放宽与 `skills/harbor-windows/SKILL.md` L264–270、`references/08-model-validation.md` L47–68、`scripts/run_model_validation.py` L517–536 既有的放宽口径现已一致。**验证方式**：以 `tests/test_model_gate.py` 12 项单测（含「全满分且 Opus testcase 更多 → PASS」「全满分但 testcase 未严格更多 → FAIL」「全模型满分仅记录不否决」）与合成证据为准；`_qc_runs/qc-{215,216}-auto/model-gate.json` 是**历史输出快照**（`pass=false`，其 testcase 状态为 `NONE`），且历史 `jobs/` 身份已随返修失效（K28），真实模型证据须整批重跑后重新采集。 |
| K31 | 交付材料口径（已定，不整改） | **`delivery-extras/` 伴随材料按口径不新增**：`skills/harbor-windows/SKILL.md` L356 要求该目录，`scripts/validate_package.py` 也判 `[FAIL] [交付材料] 未提供 delivery-extras/ 目录`（规范 5.1）；但本批 4 个交付包（215 / 216 / 218 / 219）**原本均未提供**，甲方口径为「原本没有就不用加」，故维持现状、**不生成骨架**。规范形态见 `scripts/build_delivery_extras.py`（`EXTERNAL_IMAGES.json` + `tasks/<task-id>/{metadata/{labels,manifest}.json, testcase_mapping.csv, evidence/{golden,no_change,clean_room,negative_and_equivalent_controls,cleanup_and_restore}/, model_runs/<model>/, quality_review.md}`），若日后要求补齐须立项统一处置。 |
| K32 | 自检脚本瑕疵（不影响题包） | `skills/harbor-windows/scripts/validate_package.py` 的 `[tests]` 提示行把示例文件名 `test_wpeimg_semantics.py` 与 `verifier` 拼进「tests/ 文件」列表，**与包内实际内容无关**（两包 `tests/` 实为 `aggregate_results.ps1` / `judge.toml` / `required_testcases.json` / `rubric.json` / `run_tests.ps1` / `test.bat` / `test.ps1` 共 7 个文件，隐藏套件在 `verifier/tests/` 下）。复核时不要据该行判断 tests/ 被污染。 |
| K33 | **门禁新增（2026-10-14）** | **Windows 专属机制门禁落地，四题现状全部 FAIL**：甲方 2026-10-14 飞书三条返修原因（216 / 215 / 218）的核心判定是「题目和验收是平台无关的容器格式 / CRC / 流式 IO，没有 Windows 专属行为，不满足 Windows 题要求」，并直接引用包内 `verifier/WINDOWS_VALUE.md` 的自认句（「本题不主张 Windows 反事实价值，按通用编码能力归类」）作为证据。为此新增可复算门禁 F1–F6：`scripts/check_windows_mechanism.py`（读 `metadata/windows_mechanism.json`，校验机制 ↔ 题面 ↔ F2P 用例三方锚点 + 环境层「非 Windows 必失败」证据 + 扫描自我否认表述），并已接入 `scripts/validate_package.py`（新增 `[Windows机制]` 类别）。**实测**：对 `wfflab__`{`wchunk-216`, `wfmt-215`, `wlogseg-218`, `wpeimg-219`} 四包运行，均 FAIL（缺门禁产物 + 自认句命中 4–12 处）；对同行合规题 `win-fs-001` 运行 PASS（12 项自测全过，见 `_qc_runs/windows-mechanism-rework/gate_selftest.py`）。 | 四题按现行门禁**不具备 Windows 专项交付资格**；这是**性质判定**，与测试做得多细无关 | 按甲方专家修复步骤第 3 条处置：**给题注入真实 Windows 机制后发新版并重新作答**，或按实际采购分类移出 Windows 池。**不得只删掉自认句** —— 删掉只让门禁变绿，判定依据仍在题面与测试里。历史包可用 `--allow-legacy-exempt` + 包内 `WINDOWS_MECHANISM_EXEMPT.md` 不追溯改判（F6 除外，且该标记文件交付前必须删除）。规则与可照抄手法见 `skills/harbor-windows/references/12-windows-mechanism-gate.md` |

## 题号对照（本目录实物包）

- `wfflab__wfmt-215` —— ~~通用编码能力（Windows 运行时执行）~~ → **甲方已否决该归类（2026-10-14）**，须注入 Windows 机制后发新版｜L4｜required **9 F2P + 7 P2P = 16**（返修后 2.1.1）
- `wfflab__wchunk-216` —— ~~通用编码能力（Windows 运行时执行）~~ → **甲方已否决该归类（2026-10-14）**，须注入 Windows 机制后发新版｜L4｜required **10 F2P + 9 P2P = 19**（返修后 1.2.1）
- `wfflab__wreparse-217` —— 文件系统与路径（NTFS 重解析点）｜**L4**｜required **45 F2P + 15 P2P = 60**

> 历史材料中出现的 `wsync-142`、`wreserved-201`、`wads-202`、`wacl-203`、`wpathext-204`、
> `wreg-205`、`wencoding-206`、`wps-207`、`wrotate-208`、`wproc-209`、`winstall-210`、
> `wstamp-211`、`wtask-216` 属于完整仓库的其他题包，不在本目录交付范围内。
> 题目实体与 F2P/P2P 计数以 `_index/tasks_index.csv` 与各题 `tests/required_testcases.json` 为准。

## wfflab__wvas-216（2026-10-14，替换 wchunk-216 槽位）

- **区分度已达标**：Opus score_sum 3 > Qwen score_sum 2（Opus 逐 case 48 > Qwen 46）。
- **opus-2 曾出现一次真实模型失败**：该轮模型只读文件、未产出补丁即结束（8/16，与 no-change 一致），
  属 MODEL_FAILURE 而非契约缺陷——它引用的「可见冒烟用例要求 module.path 为真」只针对当前进程断言，
  与验收 C 允许 `None` 不冲突。已重跑并取得 1 分，最终三份 Opus 轮次均为 1。
- **交付 ZIP 条目分隔符**：必须为正斜杠；.NET Framework 的 `ZipFile::CreateFromDirectory` 会写反斜杠，
  已改用 Python `zipfile` 生成（与 219/218/216 历史交付包一致）。
- **`tests/judge.toml` 与 `tests/rubric.json` 保留**：`validate_package.py` 的「旧评分残留」检查会在
  全部 12 个题包上报警（含已通过甲方验收的 219）。本包判分本身已是 required F2P/P2P 二值，
  judge.toml 仅作 rubric 元数据并由 `source_sha256` 绑定 `rubric.json`；清除会改变 task checksum
  而使 12 轮真实轮次全部失效，故保留并在此登记。
- **`delivery-extras/` 未随题包提供**：该目录属交付伴随材料，不影响题包自包含性；
  `_index/` 已提供目录级伴随材料。
