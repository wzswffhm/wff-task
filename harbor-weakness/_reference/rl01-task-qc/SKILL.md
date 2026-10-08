---
name: rl01-task-qc
description: 质检 RL0-1 评测题包的三件套——题面（instruction.md）、标准答案（solution/golden_output 与参考答案）、rubrics（rubrics.json ↔ tests/rubrics.toml）——并复核题包结构、跑分产物与难度门槛，产出逐条可溯源的质检报告与整改动作，给出「通过 / 有条件通过 / 不通过（打回）」结论。用于 RL0-1 题包质检、人检前 AI 质检、甲方返修复检、批量抽检与交付验收门禁；不用于出题本身（见 rl01-data-production、weakness-data-construction），也不用于普通前端 rubrics 评分、Windows 专项评测题或纯 Harbor 运行排障。
metadata:
  source-docs: "20260913外发版-基于weakness和skill+的数据构造方案；RL0-1-数据生产规范GuidelineV1.1--20260920 for外部供应商；外发版-评测题包交付规范（rewardkit）20260913"
  scope: "只做质检与开整改单；出题与返修落地回 rl01-data-production / weakness-data-construction"
  upstream: "rl01-data-production v2.0；weakness-data-construction v2.0（机器门禁脚本与本文同源，见 references/upstream-sync.md）"
  version: "1.2"
  changelog: "1.1（2026-10-01 据 LAW-002/LAW-004 返修正反例固化）：新增 Q-T10 题面部分数声明自洽、Q-T11 编辑残留；check_rubric_style 新增『description 重复给档位』与『判据替题面兜底』；check_complexity 改为四指标综合定档（修误报阻断）；硬规则『FAIL 一律阻断』增加两条例外（未下发口径、脚本映射与规范不一致）；package-and-run-qc 补『返修包必须随包补跑分产物』与『一题一 zip 不得合并解压』。1.2（2026-10-01 据金融两道题 + 甲方人检报告固化）：对齐甲方人检三对象（instruction 真实性与业务价值 / rubric 单条五准则 / solution 业务正确性）并写进三个 reference 的前置小节；validate_rubrics 支持 rubrics.json 三种顶层形态、领域相关下限按 domain 分流（修金融题误报阻断）；check_rubric_style 表格类定位语按领域分流；qc_check 补齐 check_task_qc 的『重要』级门禁（原先只看退出码会吞掉 Q-T10）"
---

# RL0-1 题包质检（题面 / 标准答案 / rubrics）

判定一套 RL0-1 题包**能不能交付**：三件套是否自洽、是否可解、是否真实、判据是否站得住，并给出可复检的整改单。
先判断当前在查哪一件，再读对应参考文件，不要一次性加载全部。

> **范围**：本 skill 只质检，不改题。质检产出的是「问题清单 + 整改动作 + 复检方式 + 结论」。
> 需要真的改判据、改答案、重出题面时，回到 `rl01-data-production`（专项数据）或
> `weakness-data-construction`（weakness 数据），改完再回来复检。

## 模式选择

| 当前工作 | 读什么 |
|---|---|
| 单题全量质检（默认） | 本文件 + 下面四张清单 |
| 只查题面 | [references/instruction-qc.md](references/instruction-qc.md) |
| 只查标准答案 / 参考答案 | [references/answer-qc.md](references/answer-qc.md) |
| 只查 rubrics（json 与 toml） | [references/rubrics-qc.md](references/rubrics-qc.md) |
| 查题包结构、跑分产物、难度门槛、批量验收、打包 | [references/package-and-run-qc.md](references/package-and-run-qc.md) |
| 写质检报告、回填结论、对齐报告格式 | [references/report-format.md](references/report-format.md) |
| 换机器、脚本与生产 skill 版本对不上 | [references/upstream-sync.md](references/upstream-sync.md) |

## 不可突破的硬规则

- **只读质检**：默认不改题包里的任何一个文件。整改动作写进报告，由生产方执行。
  用户明确要求「顺手修」时才动手，且改动判据/权重/参考答案后**必须重跑判分**（可只重跑判官）。
- **机器门禁 FAIL 一律算阻断，只有两条例外**：不许因为「我知道为什么」就放过，脚本报 FAIL 就直接进阻断清单。
  例外只在这两种情形成立，且必须在报告里单列「脚本口径与规范冲突」小节、附上脚本原始输出与人工判据，
  不许静默降级：
  ① **脚本查的口径规范还没下发**（weakness 正式词表、环境模板名、rewardkit 字段终版）→ 报 `TBD`，
     写明由谁提供，整改动作照写（拿到词表即替换）；
  ② **脚本的机械映射与规范定义不一致**（如规范规定 C1–C5 按文件数/Requirement/evidence-hop/工具种类数
     **多指标综合**定档，脚本却按「文件数单项定档」）→ 报「待人工核」，把脚本原始输出与人工判断并列写清，
     由甲方裁决；此时不得据此把题包判成不通过。
  降级只改变**结论口径**，不省掉整改动作；两条以外的任何 FAIL 都不许降级。
- **每条问题必须给齐证据三件套**：①位置（文件 + 条目号/段落）②原文引用 ③判定依据（引规范原句）。
  只写「建议优化」「可以更好」不构成质检结论，甲方人检也不认。
- **不得把未验证写成通过**：跑不了判分、缺跑分产物、拿不到规范原文、材料装不上依赖导致锚点无法核验时，
  结论标 `未验证` / `TBD` 并写明由谁提供，**不许默认通过**。
- **结论口径唯一**：任一**阻断** → 不通过（打回）；仅**重要** → 有条件通过（**可交付**：重要项是
  建议整改项，不阻断交付；甲方另有明确要求时才升级处理）；仅**提示** → 通过（可附优化建议）。
  三件套分别出结论，再给总结论。**报告开头必须先给「结论 + 是否需要重跑判分」两句话**——
  这是甲方最先看的两个信息，不要埋在正文里（真实反馈：逐条报告写得再细，没有这两句甲方
  只会读出「又要返修」，而「仅重要」其实代表可以直接交）。
- **脚本只覆盖机械项**：真实性、参考答案是否专业正确、Skill 是否真的不可省略、weakness trigger
  是否必然诱发失败、判据是否建立在材料里不存在的口径上——**这些必须人工/AI 判断**，
  报告里要显式列出「脚本未覆盖、已人工核 / 未核」。
- **锚点可溯源**：判据里的口径、条款号、门槛、数值，必须能在 `environment/input_files/` 的规则原文或
  材料记载里找到出处。材料里的可疑口径只能写成 `negate` 扣分项（「直接沿用该口径」才扣分），
  不能当成正分项的前提。
- **难度以实测为准**：参考答案得分 ≥ 0.85；三模型（gpt-5.6-sol / claude-opus-4-8 / qwen3.8-max0902，
  claude-code 框架，裁判 qwen3.7-plus，各 1 次）平均分 < 0.7 且至少一个模型非零。
  档位由实测落：A1 `0.6≤x<0.7` / A2 `0.5≤x<0.6` / A3 `x<0.5`，不是申报值。
- **判据不得 hack**：靠题面歧义、无法验证的要求、互相矛盾的约束把分数压低，人检一经发现直接打回；
  发现这种形态要按**阻断**报，不要只算「文档问题」。
- **不臆造**：规范没给的（14 种 weakness 词表、三级/四级标签知识体系、平台环境模板名、配额调整）
  标 `TBD` 并写明来源，不许凭常识补齐。

## 标准流程

1. **定范围与口径**：确认查单题还是整批、是否含跑分产物、手里是哪一版规范（rewardkit 与主方案冲突时
   以 rewardkit 为准），以及题目属于专项数据还是 weakness 数据——两者的附加检查项不同。
2. **跑机器门禁**：
   ```bash
   python scripts/qc_check.py <题目目录或批次目录> [--zip <交付zip>] [--out <报告目录>]
   ```
   拿到 `qc_machine_report.md/json`：逐题门禁结论 + 原始输出 + 待人工项清单。
3. **逐件人工核**：按顺序查题面 → 标准答案 → rubrics。每件照对应 reference 的清单走一遍，
   逐条落证据；不要只跑脚本就下结论。
   这一段的判据口径与**甲方人检三对象**对齐：题面判「场景真实 / 有业务价值」，
   rubrics 判「原子性 / 客观性 / 区分度 / 完整性 / 鲁棒性」，标准答案判「答案业务正确性」
   （三处口径分别见 instruction-qc「一·前」、rubrics-qc「二·前」、answer-qc「一·前」）。
   格式、字段、环境、打包、跑分属于机器门禁与供应商自检，人检不重复——报告里也照这个分线写。
4. **复核题包与跑分**：按 [references/package-and-run-qc.md](references/package-and-run-qc.md) 核字段、
   跑分产物完整性、难度门槛、打包与权限。
5. **汇总报告**：按 [references/report-format.md](references/report-format.md) 的模板出报告，
   每条问题带证据、整改动作、复检方式。
6. **出结论**：三件套分别给结论 + 总结论；`未验证` 项单列，不计入通过。
7. **复检**：返修后的包只复检「有问题的条目 + 受影响的条目 + 全部机器门禁」，
   并核对没有引入新问题；改过判据/答案的必须带新版逐条判分记录。

专项数据（skill / tool / workflow）与 weakness 数据在题面、判据上的附加要求不同，
两张差异表分别在 [references/instruction-qc.md](references/instruction-qc.md) 与
[references/rubrics-qc.md](references/rubrics-qc.md) 里，别混用。

## 产出与自检

```bash
python scripts/qc_check.py <题目目录|批次目录>          # 一键机器门禁 + 汇总报告
python scripts/check_task_qc.py <task-dir> [...]       # 题面/答案/判据 跨文件一致性
python scripts/validate_task_package.py <task-dir>      # 题包字段、权重、分布、skill_set 约束
python scripts/validate_rubrics.py <task-dir> [...]     # 判据门禁 + json/toml 一致性 + 锚点一致性
python scripts/check_rubric_style.py <task-dir> --strict  # 判据措辞三要求 + 锚点待人工核
python scripts/check_complexity.py <task-dir> [...]     # C1–C5 档位与文件数/产物数是否自洽
python scripts/check_batch_quota.py <批次目录>           # 批量配额、weakness 覆盖、复杂度分布
python scripts/check_package_permissions.py <zip|目录>   # zip 内权限位/换行/残留/结构
python scripts/selftest.py <已知良好的task-dir>          # 自检：注入缺陷，验证检查项没失效
```

质检报告按题目落到用户可见的 `outputs/`，不要写进题包目录（会污染交付包）：
`qc_check.py` 默认把机器报告写到 `<目标>_qc/`，再用它作为人工结论的底稿。

这些脚本只覆盖可机械判定的门禁。**题目真实性、参考答案是否专业正确、Skill 是否真的不可省略、
weakness trigger 是否必然诱发失败、判据锚点是否真有出处，一律人工判断**；
报告末尾的「待人工项清单」是给这一步用的，必须逐项勾掉或标 `未验证`。

改判据、改权重、改参考答案之后必须重跑判分，方法见
[references/package-and-run-qc.md](references/package-and-run-qc.md) 第三节。

## 缺失信息处理

规范未给出的信息（14 种 weakness 完整词表、三级/四级标签知识体系、平台环境模板名、
Judge 网关与凭据、rewardkit 字段口径的最终版、批次配额调整）一律标 `TBD` 并写明由谁提供，
不得凭常识补齐。已知冲突与默认口径见 [references/report-format.md](references/report-format.md)
末尾的待确认表；rewardkit 与主方案冲突时以 rewardkit 为准。
