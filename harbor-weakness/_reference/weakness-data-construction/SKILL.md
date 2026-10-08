---
name: weakness-data-construction
description: 构造、迭代与质检 RL0-1 的 **weakness-driven** 办公/Cowork 标注题包——从已观测到的 Bad Pattern / Trigger 出发，设计能稳定诱发该弱点的场景，产出 instruction.md、真实参考文件、参考答案、rubrics.json 与 Harbor 题包（task.toml/metadata/artifacts），把 rubrics.json 落成 tests/rubrics.toml，跑分定难度档，并做 14 种 weakness 覆盖计数与验收门禁检查。用于 weakness 数据构造的埋点（trigger）设计、打分项（rubrics）设计、题包交付验收与甲方返修；不用于 skill / tool / workflow 专项数据（见 rl01-data-production）、普通前端 rubrics 评分、Windows 专项评测题或纯 Harbor 运行排障。
metadata:
  source-docs: "20260913外发版-基于weakness和skill+的数据构造方案；RL0-1-数据生产规范GuidelineV1.1--20260920 for外部供应商；外发版-评测题包交付规范（rewardkit）20260913"
  scope: "仅 weakness-driven 数据；专项数据（skill / tool / workflow）在 rl01-data-production"
  version: "2.4"
---

# Weakness 数据构造

把已观测到的模型缺陷，转成能稳定复现、可复现打分、难度可控的评测题包。
先判断当前在做哪一步，再读对应的参考文件，不要一次性加载全部。

> **范围**：本 skill 只负责 **weakness-driven 数据 1000 条**。
> 专项数据（Skill Discovery、Skill Generation/Editing、Skill Dependency、
> Dependency-aware Workflow、Subagent Workflow、MCP Scaling）在 `rl01-data-production`。

## 模式选择

| 当前工作 | 读什么 |
|---|---|
| 出单题：选 weakness、设计 trigger、题面、真实参考文件、参考答案 | 本文件 + [references/design-patterns.md](references/design-patterns.md) |
| 规划批次：领域/复杂度/难度配额、14 种 weakness 覆盖计数 | [references/taxonomy-and-quota.md](references/taxonomy-and-quota.md) |
| 写或修订打分项 | [references/rubrics-spec.md](references/rubrics-spec.md) |
| 把 rubrics.json 落成 Harbor 能读的 tests/rubrics.toml | [references/rewardkit-conversion.md](references/rewardkit-conversion.md) |
| 估分、定难度档、按门槛补条或调权重 | [references/scoring-and-difficulty.md](references/scoring-and-difficulty.md) |
| 拼题包：task.toml、environment、tests、solution | [references/task-package-format.md](references/task-package-format.md) |
| 甲方返修、重跑判分、打包提交 | [references/revision-and-qc.md](references/revision-and-qc.md) |
| 质检、验收、待确认项 | [references/acceptance-and-open-items.md](references/acceptance-and-open-items.md) |
| 换电脑、换环境继续生产 | [references/portability.md](references/portability.md) |

## 不可突破的硬约束

- **weakness 编号以原始规范为准（不是 references，也不是示例）**：正式词表共 14 种，
  编号写两位——`W01 长文档下的硬约束遵循`、`W02 关键冲突下自行选边`、
  `W03 阻塞状态的识别与恢复`、`W04 多要求多交付物下缺少 Requirement Coverage Accounting`、
  `W05 关键信息缺失时"该问不问"`、`W06 用户补充信息后只局部更新没有 Global Re-planning`、
  `W07 长表格/多 Sheet 下的数据覆盖与抗干扰能力弱`、`W08 启动 Subagent 后把"已派发"当成"已完成"`、
  `W09 Skill 被形式化调用但没有真正改变关键判断`、`W10 大 Workspace 下缺少 Coverage Accounting`、
  `W11 无据自造数据与口径`、`W12 跨源交叉核对缺失`、`W13 规划与策略调整失当`、
  `W14 脱敏与合规疏漏`。规范正文里的 `["W07-流程跳步","W12-约束遵循"]` **是占位示例**，
  名称与词表不符，照抄等于全部标错。完整行为描述见
  [references/taxonomy-and-quota.md](references/taxonomy-and-quota.md)。
- **C1–C5 必须逐项核**：`task_complexity` 拿分级表数出来（文件数 C1=2/C2=5/C3=10/C4=25/C5=50+，
  输出产物数 C1=1-2/C2=2-3/C3=3-4/C4=4-6/C5=4-8），跑 `scripts/check_complexity.py` 验证；
  不一致要改题（补材料或补交付物），**不许改标注**。
  - **产物区间重叠，落档按"区间包含"取并集**：C4=4–6 与 C5=4–8 重叠，6 个产物**同时**支持 C4 与
    C5；4 个产物同时支持 C3/C4/C5。据此判"6 个产物只对应 C4、申报 C5 就是标错"是**错的**——
    v2.3 及更早的 `check_complexity.py` 曾把映射压窄成「5–6 只认 C4」，造成把合规申报误判为 FAIL，
    v2.4 已按分级表修正并加 `--self-test` 防漂移。
  - **申诉优先级：分级表原文 > 门禁脚本**。脚本取值与分级表不一致时**以分级表为准**，
    并在交付说明中记录脚本冲突；先跑 `python scripts/check_complexity.py --self-test` 确认脚本未漂移，
    再判断题包本身是否真的不合规。**不要因为脚本报 FAIL 就直接判"档位标错"。**
  - **申报档高于文件数档是常见且合法的**（多产物/大项目例外）：只要产物数支持该档即可通过。
    补材料到 25/50 个文件属**改题**，会连带作废已跑的 agent 产物——代价远高于改元数据（零重跑），
    因此不要为了迁就脚本去硬凑文件数。
- **weakness 是本 skill 的存在理由**：每条数据 `weakness_tag` ≥ 1 个，且必须与题面、environment
  中真实埋入的 trigger 一一对应；标了就要埋，没有埋 trigger 就不要标。
- **判定标准是"必然失败"而不是"少拿几分"**：不按预期方式做时，模型必须一定会进入错误分支，
  或状态必然失败。埋点要能稳定复现，只靠题面歧义不算。
- **覆盖配额**：1000 条须覆盖全部 14 种 weakness；每条按标注的每种各计 1 次；
  每种至少 50 条、不超过 250 条。
- **复杂度覆盖**：1000 条的数据复杂性须覆盖 C1–C5（占比 12% / 25% / 35% / 18% / 10%），
  不是只出高复杂度题。
- **`category` 取值**：写 `weakness`，不要自造（如 `compliance`）。
  `check_batch_quota.py` 按 `category` 统计专项五类配额，非约定命名会被标成"未知 category"。
- 难度：单题满分归一化 1.0。参考解得分须 > 0.85；三个模型（gpt-5.6-sol / claude-opus-4-8 / qwen3.8-max0902，claude-code 框架，裁判 qwen3.7-plus，各跑 1 次）平均分须 < 0.7，且至少一个模型非零——禁止全 0 的"死题"。
- 难度档由实测均值决定，不是申报值：A1 `0.6≤x<0.7` / A2 `0.5≤x<0.6` / A3 `x<0.5`，且**档位绑条数下限**（法律领域 简单≥25 / 中等≥30 / 复杂≥35）。落档后回填 `task.toml` 的 `difficulty`、`keywords`、`tags`。
- 打分项：`weight` 只能取 `{+10, +7, +3, -3, -7, -10}`；每题至少 2 条 `+10`；内容质量维度的正分合计 ≥ 全部正分的 30%；不要用 `+3` 堆叠——关键结论/指令/规范给 10，重要补充依据/专业规范/论证理由给 7。`-10` 只用于重大专业错误、幻觉、业务安全或合规风险。
- 扣分项落地：`tests/rubrics.toml` 里**只能**写 `negate = true` + 正 weight，绝不写负 weight，也不要把扣分条改写成"未违规得分"的正向条。
- likert 标度唯一：只保留 `评分为 1–5 整数：5=… 1=…`，锚点唯一来源是 `rubrics.json` 的 `levels`；`levels` 必须与条目设计意图一致（历史上出现过整体错位一档）。
- 交付完整性：`跑分产物与轨迹/`（每个执行体的交付物 + agent 轨迹 + `reward.json` + `reward-details.json`）必须随包；`solve.sh`/`test.sh` 必须 LF + 0755。
- 真实性：参考文件必须是真实数据；不得要求模型凭猜测写法规条款、政策口径、职责分工或统计数据。参考答案须与题面规定的交付物类型、文件名、数量严格一致。
- 判据锚点必须可溯源：判据里的口径、标准、门槛、数值，必须能在 `environment/input_files/` 的规则原文或材料记载中找到出处；内部邮件的口头说法、行业传闻、自造框架都不能写成**得分前提**（实例：把规则原文并不存在的「合并计算口径」写成算力门槛判据的得分前提，被人检判为"判据建立在规则原文不存在的法律标准之上"）。材料里出现的不靠谱口径应转成**扣分项**（"直接沿用该口径"才扣分），不要当正分项的前提。
- 判据措辞三要求：① 陈述式——先写应达到的结论与要求，不以「XX 是否 XX」提问式起头（提问式只点话题、不给判定锚点）；② 档位量化——不用「若干 / 个别 / 普遍 / 多数」等无定义量词，改「至少两项 / 三分之二以上 / 半数以上」；③ 定位语贴合交付物形态——法律题写「规则条款编号 / 协议条款序号 / 材料记载位置」，不要出现「可逐格复算（单元格、公式）」这类表格题模板用语。另：交付物本身即可核验的条目，`criterion_type` 写 `Objective`，不要随手写 `Subjective`。交付前跑 `scripts/check_rubric_style.py` 扫一遍。
- 题面：任务说明、产出要求、硬约束（禁止项、文件名要求）各用独立段落显式写出，不得藏在括号里。
- 配置：`JUDGE_` 前缀变量只写在 `[verifier.env]`，严禁出现在 `[environment.env]`。
- 派生新批次必须继承上一轮返修成果：从基础版改出 weakness/专项版，或从上一轮包改出新包时，先做**返修成果继承核对**（[references/revision-and-qc.md](references/revision-and-qc.md) 一之三），把上一轮已整改的判据、参考答案、`prompt.md`、权重与条数结构整体带过来，再做本轮形态改造。跳过这一步，上一轮被退过的问题会原样复发——这是返修环节最贵的错误。
- 打包必须验 zip 内的真实权限位：Windows 上重新压缩（资源管理器、`Compress-Archive`、部分库）会把条目 `external_attr` 写成 `0`，本机看文件属性一切正常，甲方解包后 `solve.sh`/`test.sh` 却没有可执行位，直接判 F08。打包后一律用 `scripts/check_package_permissions.py` 验 zip 内权限。
- 不得 hack：靠题面歧义、无法验证的要求或互相矛盾的约束刷低分，人工质检一经发现直接打回。

## 标准流程

1. **选 weakness**：从算法侧词表里挑本批要覆盖的 weakness（先把正式词表取到手，不要自造 W 编号）。
2. **设计 trigger**：写清"模型在什么条件下必然走错"——错在哪个分支、哪一步状态失败、靠什么证据可复现。
3. **出题**：题面 + 真实参考文件 + 参考答案（对照 design-patterns 的套路与确认清单）。
4. **写判据**：`rubrics.json`（含负 weight、含 `levels`），按 rubrics-spec 自检。
5. **落成 Harbor 格式**：`python scripts/gen_rubrics_toml.py <task-dir>`；`tests/prompt.md` 用 rewardkit 模板原文。
6. **本地自测**：`harbor run -p <task-dir> -a oracle` 验参考解 > 0.85。
7. **跑三模型**：claude-code 框架下 gpt / opus / qwen 各 1 次，逐条判分明细留档。
8. **定档回填**：按实测均值落 A1/A2/A3，补足该档条数下限，同步 `task.toml` 的 `difficulty` / `keywords` / `tags`。零成本回算只作中间估计，**以实测为准**（实例：回算估 A1，实测落到 A2）。
9. **打包提交**：`<批次目录>/<题目目录>/五件套 + 跑分产物与轨迹/`，附 `交付文档.md`。

改动判据、权重或参考答案后必须重跑判分（可只重跑判官，见
[references/revision-and-qc.md](references/revision-and-qc.md) 第二节）。

## 跑分迭代流程（固定顺序，不得跳步）

出完题包后按下面顺序跑，每一步不达标都**回到 rubrics 层修改**，改完重跑受影响的环节，
直到全部达标才能交付：

| 步 | 动作 | 达标线 | 不达标怎么办 |
|---|---|---|---|
| 1 | 跑 oracle（参考解） | 主分 **> 0.85** 且 `verifier_error = 0` | 说明判据写歪或参考答案缺内容 → 先改 rubrics（权重/档位/措辞/条数），必要时补参考答案；**不达标不得往下走** |
| 2 | oracle 达标后跑 qwen3.8-max-0902 | **< 0.7** | 题对 qwen 太易 → 改 rubrics 加严（提高档位门槛、加「多要素齐全」「必须给出审慎判断」型条目），必要时才动题面；改完回到第 1 步 |
| 3 | qwen 达标后跑 claude-opus-4-8 | 记录得分 | 若均值或档位不理想 → 同样回到 rubrics |
| 4 | opus 评分高于 qwen 时，继续跑 gpt-5.6-sol | 记录得分 | 同上 |
| 5 | 三模型齐后算均值定档 | 均值 **< 0.7**（A1 0.6–0.7 / A2 0.5–0.6 / A3 <0.5），且至少一个模型非零 | 均值 ≥0.7 → 回到 rubrics 继续加压；**申报档位不是想定哪个就写哪个** |

**修改优先级**：`rubrics` 优先 → 其次参考答案 → 最后才动题面。
动题面会改变 agent 产物与判分的对应关系，动完必须重跑模型（不只重跑判官）；
动 rubrics / 参考答案只需重跑判官。这条差异直接决定返修成本，务必守住顺序。

### 每次改完 rubrics 必做：判据来源自查（硬要求）

**不允许存在「题面里没有要求、也无材料依据」的判据（伪需求）。** 每次改完 rubrics 都要过一遍：

```bash
python scripts/check_rubric_style.py <task-dir> --strict   # 措辞三要求 + 锚点待人工核
python scripts/list_rubric_sources.py <task-dir>            # 列出全部 Implicit 判据供逐条核
```

逐条确认判据的要求来自三处之一：①题面显式要求 ②参考文件明确要求 ③由任务目标与场景可合理推导。
数值型锚点来自 `environment/input_files/` 不算「题面没有」——题面本就不该写具体数值。
若某条要求比题面字面更细（如题面说「做财务分析」、判据要求「必须给六项衍生比率」），
两种处理都可：在题面补一句**概括性要求**（不动判据与判分口径，可不重跑），或按 Implicit 保留并在交付文档说明。
报告口径见 [references/acceptance-and-open-items.md](references/acceptance-and-open-items.md)。

## 产出与自检

```bash
python scripts/gen_rubrics_toml.py <task-dir>          # rubrics.json → tests/rubrics.toml
python scripts/validate_rubrics.py <task-dir> [...]    # 判据门禁 + json/toml 一致性 + 锚点一致性
python scripts/validate_task_package.py <task-dir>     # 题包字段、权重、分布
python scripts/check_complexity.py <task-dir> [...]    # C1–C5 档位与文件数/产物数是否自洽
python scripts/check_complexity.py --self-test         # 断言脚本取值与分级表一致（改脚本后必跑）
python scripts/check_cross_model_concentration.py <task-dir>   # 难度是否被单一口径歧义撑着
python scripts/check_batch_quota.py <批次表或 task.toml 目录>
python scripts/rejudge_by_docker.py <task-dir> <镜像> <执行体>=<交付物目录> [...]
python scripts/check_rubric_style.py <task-dir> [...]           # 提问式/模糊量词/表格类措辞/锚点待人工核
python scripts/check_package_permissions.py <zip 或目录> [...]   # 打包后验权限位/换行/残留/结构
```

这些脚本只覆盖可机械判定的门禁（字段、权重、分布、配额、锚点、格式）。题目真实性、
trigger 是否真能稳定诱发目标 weakness、参考答案是否专业正确，仍须人工判断。

### 三道易漏的自查（都真实导致过返工）

1. **C 档必须逐项核，不能凭感觉**：`task_complexity` 要拿分级表的**文件数与输出产物数**
   去数（C1=2/1-2、C2=5/2-3、C3=10/3-4、C4=25/4-6、C5=50+/4-8），
   Requirement / evidence-hop / 工具种类数人工确认。跑 `scripts/check_complexity.py`，
   不一致必须改题（补材料或补交付物），不能改标注。
   **判定前先跑 `check_complexity.py --self-test`**：产物区间是**重叠**的（6 个产物同时支持 C4 与
   C5），脚本取值若被改窄会把合规申报误判——冲突时以分级表原文为准，别把"脚本 FAIL"直接写成
   "题包标错档"（v2.3 批次真实发生过，已作为返修误判记入 CHANGELOG v2.4）。
2. **词表以原始规范为准**：references 里的 W01–W14 表已从金融版方案抄录；
   若手上有新的原始规范 PDF，**以 PDF 为准并回来更新 references**，
   不要把 references 当唯一权威（历史上 references 曾写"词表未提供"，导致元数据
   照抄示例占位文本 `W07-流程跳步 / W12-约束遵循` 而全部标错）。
3. **难度不能被"口径歧义"撑着**：跑完分后跑
   `python scripts/check_cross_model_concentration.py <task-dir>`——它列出「三个执行体同时未满分」
   的判据及其权重占比。若"全体 0 分"判据的正分占比 ≥ 25%，先按**口径歧义**排查，别急着当成真实难度：
   - 逐条追问：这条的换算/口径能不能从 `environment/input_files/` 原文**唯一**推出？
   - 材料自相矛盾即歧义。实例：某题附件4 写"登记持股 12.00% 系按 C 轮融资前已发行股份计算"，
     附件3 又只提"未考虑期权池"，两个读法分别推出 9.09% 与 10.80%，判据只认后者，三个模型
     一致按前者作答 → 15 条判据全 0、占总正分 39.9%，**这道题的难度实际由歧义撑着**。
   - 锁口径＝改材料（必须重跑 agent）／放宽判据＝改判据（只重跑判官）；
   - **注意副作用**：口径唯一化后模型很可能就算对了。动手前先按「该组权重 ÷ 正分池」预估分数变化
     （同实例：锁口径后均值预计由 0.5431 升到约 0.94，A2 档当场失效，需同步补难度）；
   - 若选择保留现状，必须在交付说明中写明该口径的推导依据，把风险显性化，别留给下一个人检发现。

换机器继续生产（依赖、凭据、镜像怎么带过去）见
[references/portability.md](references/portability.md)。

## 缺失信息处理

文档未给出的信息（**14 种 weakness 完整词表**、三级/四级标签知识体系、平台环境模板名）
一律标 `TBD` 并写明来源，不要臆造。已知冲突与默认口径见
[references/acceptance-and-open-items.md](references/acceptance-and-open-items.md)；
rewardkit 与本文档的口径差异（rubrics.json 位置、`/logs/artifacts/output`、负 weight 表达）
以 rewardkit 为准，详见 [references/rewardkit-conversion.md](references/rewardkit-conversion.md)。
