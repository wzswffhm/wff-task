# 合规核查 — 对照《OBM Source 收集说明书-正式》"数据质量评价"

- 文档：`https://bytedance.larkoffice.com/wiki/LEPbwItS5iLrBjkBjaEcts3Qnwc`（读取于 2026-09-28，revision 2118）
- 受检对象：`output/deepSWE_2026-09-28-3-marshmallow-doc-diff`
- 补充依据：`obm-question-production/references/requirements-and-gates.md`（内部门禁细化）

## 一、结论摘要

| 项目 | 状态 |
|---|---|
| **第一条：首轮格式达标、内容相关、符合手册、无拒绝验收项、通过 checker** | ✅ **通过**（硬门禁） |
| **第二条：agent workflow 质量激励（Doubao no-skill / with-skill）** | ⏸ `not_run`（Trae 未跑）——**按文档不阻塞交付** |

> 关键：`requirements-and-gates.md` 明确——"**第二条未达成、证据不足或因成本未运行，不得推翻第一条的合格结论，也不得阻止打包和飞书提交**"；硬门禁只有 `format / content_relevance / originality / solvability / verifier_quality / anti_leakage`，`baseline_value` 与 `skill_effect` 不参与提交拒绝。

## 二、第一条（硬门禁）逐项

| 门禁 | 结论 | 依据 |
|---|---|---|
| format | ✅ | `proposal.json` + `sources/` 层级与包名 `deepSWE_2026-09-28-3-marshmallow-doc-diff` 一致；`sources/README.md` 逐项说明用途；无 `instruction.md`/`task.toml`/harbor 数据；`check_package.py` 除 Windows exec 位外全 PASS；`validate_proposals.py`（两份副本）均 `[OK] 1 passed, 0 failed` |
| content_relevance | ✅ | 中文、口语化、与上游 marshmallow 真实能力一致；四要素 A/B/C/D 齐备且 D 为分点 |
| originality | ✅ | 上游无 `document_diff` 相关提交；网络检索未见 marshmallow 上的 `document_diff` 公开实现；非由 PR/issue 倒推 |
| solvability | ✅ | 参考实现可解；本地 `NOP=0 / Oracle=1`；离线 Docker `--network=none` 亦 0/1；官方编排器 `verify_agent_patch.py --docker` 亦 0/1 |
| verifier_quality | ✅ | 11 个原创 F2P（行为级、含边界）+ 826 个上游 P2P 回归；非"只复制已有 tests"；不依赖未公开的固定字段/异常类型 |
| anti_leakage | ✅（可辩护） | `SKILL.md` 与 `expert_experience_skill` 不含测试名、私有符号、断言或预期输出；"验证思路"与 F2P 场景重合，但其内容全部源自公开契约 `C_agent_task`，属可观察行为而非隐藏测试细节 |

## 三、拒绝验收清单逐条

| 拒绝项 | 判定 | 说明 |
|---|---|---|
| proposal 矛盾/错误、不存在可能解 | 不存在 | 参考实现通过全部 F2P 与 P2P |
| 从公开 commit/PR 倒推 | 不存在 | 见 originality |
| 任务能搜索直接找到 solution | 不存在 | 检索无 `document_diff` |
| 修改公开 benchmark 名字/数字 | 不适用 | 原创特性，非改名题 |
| Verifier 只是复制已有 tests | 不存在 | F2P 为原创行为验收；P2P 仅作回归 |
| 说不清 verify/test 为何存在 | 可解释 | 见 `proposal_verify` / `PIPELINE-FIXES.md` |
| Skill 只是通用 coding 流程 | 不存在 | 四条难点专属（契约模型/冲突关系/决策方法/反例历史/验证思路） |
| Skill 泄漏或基于 test 书写 | 不存在（低风险） | 同 anti_leakage；建议答辩时强调"源自公开契约" |

## 四、第二条（质量激励）——未运行，非阻塞

- 目标 1（任务价值）：no-skill seed 在声明预算内不能通过，或 >100 轮才通过。
- 目标 2（skill 有效性）：no-skill 未通过 + with-skill 通过；或都通过且轮次/时长降低 ≥30%。
- 当前状态：**`not_run`**。需在 Trae 中跑 no-skill / with-skill 才能填数；按文档这属于"质量激励"，不影响第一条合格与提交。
- 注：文档要求"为声称目标 2 达成，no-skill 失败分支应至少运行 100 轮；不足 100 轮只能标 `inconclusive`"。

## 五、本轮发现的差异与已做的修正

### 5.1 已修正：`expert_experience_skill` 字段口径冲突

- **Lark 文档**模板注释：该字段是"专家自身经验技能…（假设一个人之前并不能实现该 proposal，但通过这些经验就能实现）"→ 应为**经验正文**。
- **内部规范** `requirements-and-gates.md:21`：`expert_experience_skill` 是"某一道题的专家经验文本"；`trae-runner.md:61` 要求 with-skill 输入 = 任务 + 冻结的该字段。
- **但** `obm-task-production/references/common.md:90` 写的是"expert skill：**skill 路径、作用范围和不泄漏声明**"→ 指向性说明。
- **处理**：改为**并集**——字段内同时包含完整专家经验正文（与 `sources/skill/SKILL.md` 一致）**和**作用范围/不泄漏声明。两套口径同时满足。
  - 旧值（仅指针）sha256：`d276390e…`；新值 sha256：`0022a72a2d708e3873a719de1a6d1c360f8b27d57c5e11569f6d0cddbfce6b46`
  - 已同步 `trae-runs-v1/BASELINE.json` 的 `proposal_sha256`；已验证 prompt 与 skill 的散列**未变**，`trae-runs-v1` 仍然有效。

### 5.2 已修正：`sources/README.md` 措辞

原文"`grader.py`：收集并应用 Agent 补丁后运行 pytest"，与实际不符（应用补丁发生在评测编排器/构建阶段）。已改为准确描述。

### 5.3 需你决策：本地工具链比文档更严

- 文档口径：第二条不阻塞打包。
- 但本地 `build_delivery_zip.py` 的 `ensure_passed_experiment()` **强制**要求 `EXPERIMENT_RESULT.json` 为 `passed`（no-skill=0 / with-skill=1），否则拒绝出 ZIP。
- 即：若你希望**按文档口径**在未跑 Trae 的情况下先打包提交，本地这一步会拦住你，需要放宽该检查（或补充等价的第二组证据）。若按 `obm-task-production` 流程走，则仍需 Trae 双跑。**请确认走哪条。**

## 六、其他提示

- `proposal.json` 字段要求"自然语言、需要人工"。Lark 文档写"禁止AI生成"，而内部 `requirements-and-gates.md:21` 已更新为"允许 AI 协助或生成"——按后者执行即可，但不要伪造专家资历/工时。
- 训练平台为 Linux 终端、不支持 GPU；本题为纯 Python + Linux 容器，符合。
- `programbench` 的"题目语言不能是 Python"约束**不适用**于本题（benchmark = deepSWE）。
