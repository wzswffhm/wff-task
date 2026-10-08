# 与生产 skill 的同步关系

本 skill 的机器门禁脚本与 `rl01-data-production` v2.0 / `weakness-data-construction` v2.0 同源。
**质检判定口径以生产 skill 的 references 为准**，本 skill 只做「怎么查、查到什么算不合格」的翻译。

## 一、口径权威顺序

1. 甲方规范原文（`20260913外发版-基于weakness和skill+的数据构造方案`、
   `RL0-1-数据生产规范GuidelineV1.1--20260920`、`外发版-评测题包交付规范（rewardkit）20260913`）；
   rewardkit 与主方案冲突时**以 rewardkit 为准**。
2. 两个生产 skill 的 `references/`（`rubrics-spec`、`rewardkit-conversion`、`task-package-format`、
   `revision-and-qc`、`acceptance-and-open-items`、`scoring-and-difficulty`、`taxonomy-and-quota`）。
3. 本 skill 的清单（把上面两层翻译成质检动作，**新增判定前先确认上游有没有对应条文**）。

本 skill 不复制上游 references 的正文。需要原文时直接读生产 skill：
`~/.codex/skills/weakness-data-construction/references/` 与
`~/.codex/skills/rl01-data-production/references/`。

## 二、脚本来源与本地增量

取自 `weakness-data-construction v2.0`（其 `check_batch_quota.py` 是 rl01 版的超集，含 weakness 覆盖统计）：

| 脚本 | 状态 |
|---|---|
| `validate_rubrics.py` | **本地增量**（上游 `354D19F8C816` → 本 skill `FB1E269DF66D`，见下第 3 条） |
| `validate_task_package.py` | verbatim（`97532D66A407`） |
| `check_complexity.py` | **本地增量**（上游 `FA82C87DA2C6` → 本 skill `12C9FF44C557`，见下第 2 条） |
| `check_package_permissions.py` | verbatim（`C66E60CBF4CF`） |
| `check_batch_quota.py` | verbatim（`8ABA6FFA65C4`） |
| `gen_rubrics_toml.py` | verbatim（`35A71219CC15`） |
| `rejudge_by_docker.py` | verbatim（`29B6027FC33C`） |
| `check_rubric_style.py` | **本地增量**（上游 `669AAB38D940` → 本 skill `DBE9A10B98FE`） |

`check_rubric_style.py` 的四处本地增量（都在文件里标注了「本地增量」）：

1. 新增 `--no-material`：跳过 `environment/input_files/` 的正文提取，供大批量质检提速
   （`qc_check.py --fast` 会带上它），代价是锚点溯源只输出待核清单、不做材料比对。
2. 数值比对增加归一化：材料里的数字常有千分位/全角/换行差异，原实现对不上会刷出大量误报；
   现在按「原文 / 去空格 / 去逗号 / 纯数字串」四种形态各比一次，并把每条判据的未命中数值**汇总成一行**。

第 3 处本地增量（2026-10-01 加入，`DUP_SCALE` / `META_PATCH`）：

3. 两条判据自身质量的机器检查——
   - `description` 里重复给出 0–1 档位段（「按…评分：」「0.75=」「0.25=」）→ 报，指向
     `validate_rubrics.py` 的 toml 层验收；
   - 判据里出现替题面歧义兜底的解释语（「不影响…判定」「不计入…判定」「本任务明确要求的组成部分」）→ 报，
    提示根因在 `instruction.md`。

第 5、6 处本地增量（2026-10-02 加入，两类误报的机器化排除）：

5. `VAGUE_LAW_TITLE`：法规正式名称里的「若干」不是无定义量词。真实误报——
   LAW-011 R03「《关于审理非法集资刑事案件具体应用法律**若干**问题的解释》」、R14
   「《关于办理洗钱刑事案件适用法律**若干**问题的解释》第二条」被判「无定义量词 ['若干']」。
6. `FORMULA_IN_CONTEXT`：法律-税务题里的「**计税公式 / 计算公式**」是分析对象本身，不是表格题
   定位语。真实误报——LAW-012（境外股票期权）R36「自行给出股份转让环节的具体**计税公式**或
   具体比例税率」被判「含表格类定位语 ['公式']」。注意：同一条里若同时出现「单元格 / 逐格复算」
   这类强信号，仍应报（LAW-002 R10 即为此情形，属真命中）。

`check_task_qc.py` 的本地增量（2026-10-02 加入，1 处）：

- **Q-T10 支持编号列表题面**：原实现只认 `^\*\*第X部分[：:（(]` 作为部分标题，题面用
  「1. **争议焦点**：…」枚举时计数为 0 并误报「实际以「**第X部分」起头 0 处」——
  真实误报：LAW-012（资产评估投诉）题面声明「五个部分」并用 1.–5. 逐条列出，数量自洽却被判重要。
  现在 `PART_HEAD` 匹配不到时改按**产出要求段内的编号条目**计数，数量相符即不报；
  `第X部分` 编号重复检测仅在该形态下执行。
- 改动后必须跑 `scripts/selftest.py <已知良好的task-dir>`：分别在**编号列表题面**
  （LAW-012 资产评估）与**第X部分题面**（LAW-002）两种基准上跑，六项注入用例需全部命中。
  `selftest.py` 的 `dup_part_head` 注入也同步支持编号列表形态（原先找不到 `**第X部分：`
  标题会直接抛 RuntimeError）。

`check_complexity.py` 的本地增量（2026-10-01 加入，1 处）：

- 上游版本只按 `environment/input_files/` 的文件数单项定档，规范原文（数据构造方案第 3 页）却是
   **文件数 / Requirement / Evidence Chain / 工具种类数四指标综合**。单项定档会把
   「4 份材料 + 35 条判据 + 3-hop 推理」的法律题判成「文件数 4 只支持 C1」→ 误报阻断
   （真实案例：LAW-002 / LAW-004 标 C3 被判 FAIL，甲方并未退回）。现状：四指标各算档位，
   声明档位高于**全部**指标支持上限才 FAIL（虚标），单项偏低只给 NOTE 交人工核 evidence-hop。

`validate_rubrics.py` 的本地增量（2026-10-01 加入，2 处）：

3. **rubrics.json 顶层三种形态**：list / `{"items": [...]}` / `{"rubrics": [...]}`。
   上游只认 `items`，遇到 `{"rubrics": ...}` 直接 `KeyError` 崩掉，整题被记成阻断
   （真实案例：FIN1-skill-DEP-003，人检判通过）。
4. **领域相关结构下限按 domain 分流**：条数下限、11 个固定维度名、负分条数与档位下限，
   目前只有**法律领域**有规范依据（简单 25 / 中等 30 / 复杂 35）。非法律领域改为 NOTE
   「下限未下发，回甲方确认」，不再判 FAIL（真实案例：FIN1-skill-DEP-003 仅 8 条判据、
   1 条负分，甲方人检判「区分度 ✅ / 完整性 ✅ 合格」；上游会报「条数 8 >= A3 下限 35」
   「负分条目 1 条 >= 2」两处误报）。

`check_rubric_style.py` 追加的第 4 处增量：表格类定位语按领域分流——只有「逐格复算 / 可逐格」
是强信号；「单元格 / 公式」在金融、投行、代码题里是正常表述（真实案例：FIN1-SKILL-DEP-001
的 EV/EBITDA 计算链写「EBITDA 公式」被判 FAIL）。同时 `load_items` 也支持 `rubrics` 顶层键。

本 skill 独有、上游没有的脚本：

| 脚本 | 作用 |
|---|---|
| `check_task_qc.py` | 题面结构、交付物六处一致、skill 必用声明、prompt.md 模板锚点、JUDGE_ 泄漏、禁字符/换行、题面部分数声明自洽（Q-T10）、编辑残留（Q-T11） |
| `qc_check.py` | 统一编排：并行跑全部门禁 + 整批配额 + zip 权限，汇总成机器报告与待人工项清单 |
| `selftest.py` | 拿一个已知良好的题包，复制到临时目录后注入 5 类缺陷，断言 `check_task_qc.py` 都能报出来 |

改过 `check_task_qc.py` 或同步过上游脚本后，跑一次 `python scripts/selftest.py <已知良好的task-dir>`；
出现 `FAIL ... 有检查未触发` 说明某个检查坏了或与题包形态脱节，必须先修再用来质检。

## 二·补、甲方退回编号与检查项的对应（2026-10-01 从 fix1 返修说明反推）

甲方的质检报告按编号给问题。目前只掌握 `zq-法律-企业法务与合规-20260923_fix1` 交付文档里
写明的部分编号，**编号↔问题**的对应关系如下（来源是乙方的返修说明，可能与甲方原报告编号有出入，
拿到原报告后回填）：

| 编号 | 甲方问题的实质 | 本 skill 的对应检查 |
|---|---|---|
| #1 | 扣分项没写 `negate = true`（负 weight 被平台剔除） | rubrics-qc 第六节坑 1；`validate_rubrics.py` 的 negate 集合/正分池一致性 |
| #2 | description 与 `levels` 重复给档位 → toml 里两套标度 | rubrics-qc 第三节三·补；`check_rubric_style.py` DUP_SCALE + `validate_rubrics.py` 旧标度残留 |
| #3 | 条数低于难度档下限；权重以 10/3 为主、缺 7 分 | rubrics-qc 第五节；`validate_rubrics.py` 条数下限；人工核权重梯次 |
| #4 | zip 内 `solve.sh` / `test.sh` 丢可执行位或 CRLF | package-and-run-qc 第四节；`check_package_permissions.py` |
| #5 | `task.toml` 缺 `domain_l3` / `domain_l4` | package-and-run-qc 第二节 |
| #6 | `tests/prompt.md` 不是 rewardkit 模板原文（缺 Fairness anchor、自写 `[Output]` 段） | rubrics-qc 第七节；`check_task_qc.py` Q-T07 |
| #10 | description 末尾残留「按下列档位评分：」引导语 | 与 #2 同源；`check_rubric_style.py` DUP_SCALE |
| #11 | `跑分产物与轨迹/` 未随包（运行文件、模型产物、模型打分结论全缺） | package-and-run-qc 第三节 |
| #12 | likert 最高档锚点含「可逐格复算（单元格、公式）」这类表格题模板用语 | rubrics-qc 第三节要求 3；`check_rubric_style.py` 表格类定位语 |
| #7 / #8 / #9 | 本轮返修说明里未出现，含义待补 | TBD |

经验：甲方退回的重心是**判据的机器可检形态**（negate、双标度、条数、权重、可执行位、模板锚点），
措辞类（提问式起头、无定义量词）在 fix1 里**仍有残留却未被退回**——说明这两项在本批甲方口径下
不是阻断项，质检时按「重要」报、不升级为不通过。

## 二·补二、甲方人检的三对象与唯一判据来源（2026-10-01 第二批）

甲方人检报告《weakness&skill-人工质检内容》写明：

> 人工质检三对象：instruction 题目真实性与业务价值、rubric 单条五准则、solution 参考答案业务正确性。
> **格式、字段、环境、打包、跑分等由供应商自检与平台机检负责，本报告不重复。**

这条分工是本 skill 的边界依据：

| 线 | 谁 | 查什么 |
|---|---|---|
| 供应商自检 + 平台机检 | 生产方 / 平台 | 格式、字段、环境、打包、跑分、五件套、zip 权限（= 本 skill 的机器门禁部分） |
| 甲方人检 | 甲方 | 只查三对象（= 本 skill 的「待人工项清单」+ 三处人检口径小节） |

五准则的甲方原文判定标准写进了 [rubrics-qc.md](rubrics-qc.md) 的「二·前」小节；
instruction 的两个维度写进 [instruction-qc.md](instruction-qc.md) 的「一·前」；
solution 的业务正确性核法写进 [answer-qc.md](answer-qc.md) 的「一·前」。

人检报告的结论用词是「返修后-机检通过」，即人检通过时也会同时声明机检线已过——
**两条线的结论不能互相替代**：人检通过 ≠ 机器门禁通过（脚本口径可能有误报），
机器门禁通过 ≠ 人检通过（真实性、业务正确性脚本查不了）。

## 三、上游更新后怎么同步

生产 skill 改了判据规则或门禁脚本后，本 skill 必须跟：

```powershell
# 逐字节覆盖 verbatim 脚本（本地增量脚本不要直接覆盖）
$src = "$env:USERPROFILE\.codex\skills\weakness-data-construction\scripts"
$dst = "$env:USERPROFILE\.codex\skills\rl01-task-qc\scripts"
foreach ($f in "validate_task_package.py",
               "check_package_permissions.py","check_batch_quota.py","gen_rubrics_toml.py",
               "rejudge_by_docker.py") { Copy-Item -LiteralPath "$src\$f" "$dst\$f" -Force }
# check_rubric_style.py 需要手工把上面的四处本地增量重新应用一遍
# validate_rubrics.py 需要手工把「三种顶层形态 + 领域相关下限分流」两处本地增量重新应用一遍
# check_complexity.py 需要手工把四指标综合定档的本地增量重新应用一遍（不要直接覆盖）
```

同步后：

1. 用 `qc_check.py` 对一个**已知结论的真实题包**回归，确认门禁结论没有变（防上游改动引入新误报）。
2. 更新本文件第二节的 SHA256 与状态表。
3. 上游新增的判定项，若属于「质检要查但本 skill 清单没写」，补进对应 reference 的清单表。

## 四、什么时候反过来更新生产 skill

拿到新的甲方退回意见时，**先在本 skill 固化**（补进对应 reference 的清单表 + 加一条机器校验），
再回头把「什么写法一定会被判不合规」写进生产 skill 的
`weakness-data-construction/references/revision-and-qc.md` 第一节表（专项数据则同步写入
`rl01-data-production/references/revision-and-qc.md`）。只在本 skill 记一次、不回流的，下一批还会犯。
