# 题包、跑分链路与打包质检

三件套没问题，题包照样可能被退回：字段缺、跑分产物没随包、难度没实测、zip 权限位丢了。

## 一、题包结构

### 先分清三条线（谁查什么）

| 线 | 谁 | 查什么 | 本 skill 对应 |
|---|---|---|---|
| 供应商自检 | 生产方 | 格式、字段、环境、打包、跑分、五件套齐全 | `qc_check.py` 的机器门禁可复现 |
| 平台机检 | 平台 | 同上，自动跑 | 甲方人检报告写「返修后-机检通过」指的就是这一线 |
| 甲方人检 | 甲方 | **只查三件**：instruction 真实性与业务价值、rubric 单条五准则、solution 业务正确性 | 本 skill 的待人工项清单 + 三个「人检口径」小节 |

写报告时把三条线分开表述。**人检通过不能替代机器门禁，机器门禁通过也不能替代人检**：
本 skill 实测到人检已判通过的两道金融题（FIN1-skill-DEP-003 / FIN1-SKILL-DEP-001）
在旧版脚本下被判阻断，原因是脚本把法律领域的口径套到了金融题上（见
[upstream-sync.md](upstream-sync.md) 的本地增量清单）。

```text
<题目编号，如 FIN-127-W>/
├── instruction.md  task.toml  rubrics.json      ← 三件套
├── environment/{Dockerfile, input_files/, skills/}
├── tests/{test.sh, prompt.md, rubrics.toml, __golden_output/}
└── solution/{solve.sh, golden_output/}
```

批次目录（供应商+领域+一级分类+时间，返修加 `_fix<N>`）下还有 `跑分产物与轨迹/` 与 `交付文档.md`。
层级固定「批次目录 → 题目目录 → 五件套」，不得多一层、不得平铺。

## 二、task.toml 字段（`validate_task_package.py` 覆盖一部分，其余人工核）

| 字段 | 合格标准 | 等级 |
|---|---|---|
| `schema_version` | `"1.4"` | 不符 → 重要 |
| `artifacts` | `/app/output/{交付物名}`，并固定包含 `/logs/artifacts/output` | 缺 → 阻断 |
| `[task].name` / `version` | 任务名规范；返修递增补丁号（1.0.0 → 1.0.1） | 不符 → 重要 |
| `metadata.task_id` | 题目编号，与目录名一致 | 不一致 → 重要 |
| `category` | 专项数据写五类之一；weakness 数据写 `weakness`，**不要自造**（如 `compliance`） | 自造 → 阻断（配额统计会被标成未知 category）；**若整批都用某个自造值且甲方未退回**，标 TBD 并回问口径，不要单方面判阻断 |
| `domain` / `domain_l2` / `domain_l3` / `domain_l4` | 必填，知识体系未下发时三级/四级先按细分场景填、批次内去重并标来源 | 缺 `domain_l3`/`domain_l4` → 重要 |
| `task_complexity` | C1–C5，按**文件数 / Requirement / evidence-hop / 工具种类数四个指标综合**定档，不是单项定档 | 声明档位高于全部指标的支持上限（虚标，如文件数 2 却标 C4）→ 阻断；只有单项指标偏低、其余指标够 → 人工核 evidence-hop 后放行（`check_complexity.py`） |
| `weakness_tag` | weakness 数据必须有，≥1 个，取自正式词表两位编号 | 缺失 → 阻断；照抄规范正文占位示例 `W07-流程跳步` → 阻断；**正式词表未随规范下发时**填含义等价的描述式 → 记 **TBD**（不是 FAIL），写明由算法侧提供词表、拿到后一键替换 |
| `difficulty` | A1/A2/A3，由**实测**落档 | 按申报值写 → 重要 |
| `skill_set` | 与 `environment/skills/<name>/` 逐一对应 | 不对应 → 阻断 |
| `expected_skill_dependencies` | `skill_set` 的子集；Discovery 场景严格小于 | 违反 → 阻断 |
| `[verifier.env]` | `JUDGE_` 前缀变量只写在这里 | 出现在 `[environment.env]` → 阻断 |
| `[environment]` | `network_mode` 在 claude-code 框架下不要写 `no-network`；`storage_mb = 30720` 照抄 | 不符 → 重要 |

## 三、跑分链路与难度门槛

**判定链路**：claude-code 框架下跑 gpt-5.6-sol、claude-opus-4-8、qwen3.8-max0902，各 1 次，
产物由裁判模型 qwen3.7-plus 按打分项打分，满分归一化为 1.0 后取平均。

| 门槛 | 要求 | 不达标 |
|---|---|---|
| 参考答案 | 得分 ≥ 0.85（目标 > 0.85） | 阻断 |
| 三模型平均分 | < 0.7 | 阻断 |
| 死题检查 | 至少一个模型非零 | 全 0 → 阻断 |
| 难度档 | A1 `0.6≤x<0.7` / A2 `0.5≤x<0.6` / A3 `x<0.5`，且档位绑条数下限 | 回填不一致 → 重要 |

**跑分产物完整性**（`跑分产物与轨迹/` 必须随包）：

```text
跑分产物与轨迹/
├── README.md                      ← 判分口径说明
└── <题目编号>/
    ├── oracle/{output, reward.json, reward-details.json}
    └── <模型名>/{output, 轨迹, reward.json, reward-details.json}
```

注意：`reward.json` **不能**用「文件存在」判断完成——`test.sh` 开头会写一份 fail-closed 占位
（`criteria_counted = 0`、`verifier_error = 1`）。完成判据是 `criteria_counted > 0` /
`verifier_error = 0`，或 `reward-details.json` 已生成。

**返修包必须随包补跑分产物**。真实退回原话：「运行文件缺失、模型产物缺失、无模型打分结论」——
首轮包经常只有五件套而把 `跑分产物与轨迹/` 放在同级目录、不入 zip。核这一条时同时确认：
每个执行体都有 `output/`、`reward.json`、`reward-details.json`，模型轮次含 `轨迹/`，
批次根有 `交付文档.md` 与 `跑分产物与轨迹/README.md`。

**一题一 zip 时不要合并解压**。甲方常按单题出 zip（`…_fix1-LAW-002.zip` 与
`…_fix1-LAW-004.zip`），每个 zip 内的批次目录同名，都带各自的 `交付文档.md` 与
`跑分产物与轨迹/`。解压到同一目录会让同名文件互相覆盖（`交付文档.md` 只剩后一个、
`跑分产物与轨迹/` 按题目子目录合并），比对前**先分目录解压**，否则会得出
「交付文档只写了 1 题」「某题跑分产物缺失」这类假结论。

### 需要重跑判分的情况

改了判据、权重或参考答案之后**必须重跑判分**，否则逐条判分记录与判据对不上。
模型产物可沿用（题面没变，agent 那轮产物仍有效），只重跑判官：

```bash
python scripts/rejudge_by_docker.py <task-dir> <镜像> <执行体>=<交付物目录> [...]
```

- 镜像复用题包 env 镜像（`docker images` 里形如 `<题号小写>__<hash>__env-main:latest`）。
- 先清掉 `HTTP_PROXY / HTTPS_PROXY / ALL_PROXY`，并规避中文路径（先复制到纯 ASCII 目录）。
- 一个容器逐条串行判分：35 条约 1 小时、47 条约 2 小时；并发 6–8 个容器安全。
- 判分完会在挂载的 `tests/` 里写 `__pycache__`，**打包前清掉**。
- 卡死/崩溃看 `/logs/verifier/reward_exit_message.json` 的 `exit_code`
  （`judge:timeout / judge:api_error / judge:parse_error`），重跑该执行体即可。
- 凭据（`JUDGE_API_KEY` / `JUDGE_BASE_URL`）由平台提供，写成本地 `key=value` 文件传入，
  **不要写进 skill、题包或交付文档**。

## 四、打包与交付

```bash
python scripts/check_package_permissions.py <zip|目录>
```

| 检查项 | 合格标准 | 等级 |
|---|---|---|
| zip 内权限位 | `solve.sh` / `test.sh` 以 **0755** 存储 | 丢可执行位 → 阻断（甲方解包后直接判 F08） |
| 换行 | 全部 `.sh` 为 LF | CRLF → 阻断 |
| 残留文件 | 无 `__pycache__/`、`*.pyc`、`.git/`、`.DS_Store`、本地跑测残留的 `reward.json` | 有残留 → 重要 |
| 目录层级 | 批次目录 → 题目目录 → 五件套，多一层或平铺都不行 | 不符 → 阻断 |
| `交付文档.md` | 含批次内容表（条数/参考分/三模型分/均值/难度档）、环境变量表、本次返修逐条说明、跑分产物位置 | 缺项 → 重要 |

⚠ **Windows 上重新压缩（资源管理器、`Compress-Archive`、部分库）会把条目 `external_attr` 写成 0**，
本机看文件属性一切正常，甲方解包后却没有可执行位。只看本机属性不算验过，必须用脚本验 zip 内条目。
注意区分：`跑分产物与轨迹/` 里的 `reward.json` **是要留的**，清理的是本机跑测残留。

## 五、批量验收

```bash
python scripts/check_batch_quota.py <批次目录或任务表>
```

| 检查项 | 合格标准 |
|---|---|
| 专项数据配额 | 1000 条按五类各 200：Skill Discovery / Skill Generation·Editing / Skill Dependency / Dependency-aware Workflow / Subagent Workflow；MCP Scaling 低优不单独占配额 |
| weakness 覆盖 | 14 种全覆盖，每种 ≥50 且 ≤250 条 |
| 复杂度分布 | C1–C5 占比 12% / 25% / 35% / 18% / 10% |
| 条数 | 未达目标总量时只做进度提示，不判失败 |
| 难度分布 | 回填值与实测一致 |

## 六、派生新批次的继承核对（返修环节最贵的错误）

从上一轮包派生新批次（基础版 → weakness/专项版，或 `_fix1` → 新一轮）时，
**派生是「继承上一轮最终态 + 叠加本轮改造」，不是另起一包重写**。跳过继承，上一轮已整改的问题会原样复发。

逐文件比对同一路径，至少覆盖：

| 比对项 | 判定 |
|---|---|
| `tests/rubrics.toml` / `rubrics.json` | 判据集合、条数、正分池、`negate` 集合、权重分布是否继承 |
| `solution/golden_output/` 与 `tests/__golden_output/` | 两份逐字节一致，且满足全部正分项、不命中任何 `negate` 项 |
| `tests/prompt.md` | 是否仍为 rewardkit 模板原文（Fairness anchor 未丢） |
| `instruction.md` | 与本轮题面要求是否一致（一致则可沿用上一轮 agent 产物，只重跑判官） |
| `solve.sh` / `test.sh` | 内容与 zip 内权限（0755、LF）照搬上一轮已整改版本 |
| `task.toml` | 本轮形态必填字段（`category`、`weakness_tag`、`skill_set`）齐全 |

一句话口径：**元数据用新的，判据/答案/模板用上一轮已整改的**。
最小实现：逐文件 SHA256 对比新旧包，把「上一轮已整改但新包不同」的文件单独列出，逐个判断是本轮有意改动还是漏继承。

## 七、高频退回实例

- 跑分产物、逐条判分记录、轨迹没随包。
- 返修包只改了题面/判据，仍没把 `跑分产物与轨迹/` 收进 zip（甲方原话：「运行文件缺失、
  模型产物缺失、无模型打分结论」）。
- zip 内 `solve.sh` / `test.sh` 丢了可执行位。
- 批次目录名用了题目编号而不是「供应商+领域+一级分类+时间」。
- 关键轮次用了跨环境/人工重判，三模型均值可比性受影响（所有执行体都应在统一流程内、
  用最终版题面与最终版判据重跑，并在交付文档写明）。
- `[environment.env]` 里出现 `JUDGE_` 变量。
