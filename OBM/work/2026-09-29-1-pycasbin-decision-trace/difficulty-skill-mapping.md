# 难点 — skill — verifier 逐项映射（内部复核表）

题目：`2026-09-29-1-pycasbin-decision-trace`
复核对象：`proposal.json` 的 `D_task_difficulties`（8 条）× `sources/skill/SKILL.md` × `sources/verifier/config.json` 白名单节点。

| # | 难点原文（摘要） | skill 对应章节 | 给出的具体经验 | verifier 对应行为 | 是否泄漏答案 |
|---|---|---|---|---|---|
| 1 | 四种策略效果族的中断条件并不相同；允许覆盖要等到第一条匹配且效果为 `allow` 的规则才停 | 【先读求值循环，把「什么时候停」搞清楚】 | 逐族写出停下条件；指出「首条匹配的 `deny` 只被记录、不中断」；点明最常见的错是把「停下来」当成「第一条匹配」 | 5 种 effector × 8 个场景（`SCENARIOS`×`EXPECTED`）的参数化断言，逐项核对 `decisive` 落在哪条规则；`test_decisive_holds_at_most_one_rule` 全 40 个组合 | 否（只讲语义，不给用例数据） |
| 2 | `matched` 的边界是「被求值且匹配式为真」，三个集合互不相同 | 【该记哪些规则：三个集合别混】 | 列出三条边界：中断点规则计入、其后未求值不计入、求值但未匹配不计入 | `test_matched_records_only_evaluated_and_matching_rules`、`test_matched_stops_at_interrupt`、`test_matched_ordering_follows_policy_order` | 否 |
| 3 | `decisive` 在拒绝覆盖/允许且拒绝放行时必须为空，优先级族永不为空 | 【决定结论的那条规则要分效果族定】 | 分两族写断言：前两族放行时为空，后两族非空 | `test_decisive_holds_at_most_one_rule`（含 `deny-override`/`allow-and-deny` 的 allow 分支为空、`priority`/`subject-priority` 非空） | 否 |
| 4 | 效果取值的两条退化分支（无 eft token → allow；非法值 → indeterminate 且不中断） | 【效果取值有两条退化路径，别漏】 | 说明两条分支各自取值与「不触发中断、不影响结论」；提醒只被特意构造的策略踩到 | `test_effect_indeterminate_does_not_interrupt`、`test_effect_defaults_to_allow_without_eft_token`、`test_invalid_eft_value_is_indeterminate` | 否 |
| 5 | 沙箱隔离陷阱：`Assertion` 深拷贝按引用共享角色管理器 | 【试算的沙箱隔离：最容易翻车的地方】 | 说明深拷贝不隔离角色图、污染只在角色用例暴露；给出「自造独立角色管理器」的做法与四项逐字比对清单 | `test_would_change_does_not_mutate_enforcer_*`（结论/策略/角色/域内角色）、`test_would_change_role_isolation` | 否（方法论，不给符号名） |
| 6 | 条件角色管理器上的链接条件必须在沙箱里存活 | 【条件角色管理器上注册的函数要活下来】 | 说明这类模型靠注册函数判定；明确禁止文本往返序列化复制模型 | `test_would_change_conditional_role_manager_preserved`、`test_would_change_grouping_policy_conditional` | 否 |
| 7 | 角色区段增删必须同时维护角色链接（等价既有接口的全部副作用） | 【角色区段增删要连着角色链接一起做】 | 说明只改策略列表会导致试算漏报；给出「删掉一层角色链接后结论翻转」的用例构造方向 | `test_would_change_add_grouping_policy_rebuilds_links`、`test_would_change_remove_grouping_policy_drops_links`、`test_would_change_consistency_with_real_mutation` | 否 |
| 8 | 空策略路径不归属任何规则；结论仍按上游效果语义给出 | 【空策略是单独的路径】 | 说明该效果来自引擎而非规则，禁止凭空造规则；结论仍按上游给 | `test_empty_policy_produces_no_match_records`、`test_empty_policy_with_eval_matcher_raises` | 否 |

补充说明（同类方法，单列不计入难点）：变更影响分析的三条底线（不改真实引擎、按元素比较、空序列前后一致）写在【变更影响分析要回答什么】；一致性不变量 `allowed == enforce(...)` 的自查方式写在【我会怎么自查】。这两节属共同方法，不作为某一难点的唯一对应。

结论：8 条难点均有题目专属章节，且都能对应到 verifier 的实际断言行为；无泄漏参考实现、测试文件名、固定输入或文件级答案。
