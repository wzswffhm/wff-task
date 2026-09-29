# 第 2 次实验（agent-runs-2）with-skill 失败归因与题目返修记录

终态：`needs_skill_revision`（child_returncode=21）
- no-skill：53 轮，reward=0（`PATCH_PREPARE=ok`，判分真实有效）
- with-skill：71 轮，reward=0（`PATCH_PREPARE=ok`，判分真实有效）

## 失败画像（真实能力失败，非基础设施）

with-skill verifier：F2P 476/514 通过、312/312 P2P 全过，**38 个失败全部集中在
`would_change` 相关测试**；`enforce_traced` 侧（匹配记录、中断语义、decisive、
effect 取值、沙箱外行为）全部通过。

## 根因：公开契约不完整（题目缺陷，非 skill 缺陷）

逐项核对发现：
- proposal（Agent 可见契约）对 `PolicyMatch / TraceResult / PolicyMutation /
  ChangeImpact` 四个类型名**零提及**（全字段计数为 0）；
- F2P 测试硬性依赖 `from casbin import PolicyMutation`、位置参数
  `(op, sec, ptype, rule)`、非法 `op` 抛 `ValueError`、
  返回对象属性名 `changed / before / after`、以及「单个变更对象或序列均可」；
- with-skill 代理据此自创了等价命名（`Mutation / ChangeAnalysis / ChangeResult`，
  且 `would_change` 语义、沙箱隔离、角色链接副作用均实现正确——P2P 全过可佐证），
  38 个测试仅因命名不符而失败。

结论：契约未固化公开命名，导致 verifier 与题面不一致（官方质量门槛中的
返修事由）。skill 本身无需为命名问题返修。

## 返修内容

1. `proposal.json` B/C 补全公开命名契约：四个类型名、字段顺序、`op` 取值与
   `ValueError`、`ChangeImpact` 属性名、`mutations` 单条或序列均可。
   `check_proposal_language.py` 与 `validate_proposals.py` 复检通过。
2. `sources/skill/SKILL.md` 新增「把公开命名当成契约本身」一节（可迁移方法，
   不含测试名、断言或固定输入），`check_skill_language.py` 通过。
3. 题面与 skill 均有变化 → 按规范两侧重跑，新目录 `agent-runs-3`。
