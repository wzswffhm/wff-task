# 场景去重复核记录 — 2026-09-28-3 marshmallow-doc-diff

```text
候选题：marshmallow Schema.document_diff —— 为 marshmallow 增加 schema 感知的结构化 diff
候选档案：work/2026-09-28-3-marshmallow-doc-diff/scene-profile.json
候选档案散列：c8ba6ed65381d557c6c184c90e99b39f264f9d11eb3aa6c846d1b62daf996225
检查日期：2026-09-28
检查语料：benchmark 官方题 113 道；项目 proposal 3 个（2026-09-28-1 已交付、2026-09-28-2 废弃/diskcache、2026-09-28-3 本候选）
登记表活动候选数量：1（仅本候选 2026-09-28-3 为 candidate；2026-09-28-1 packaged，2026-09-28-2 abandoned）
飞书共享题面库：85 条记录（已全量读取，marshmallow 不在其中）
```

## 自动召回（check_scene_overlap.py）

- 最高文本相似度题：`etree-xml-diff-patch`（官方 113 题之一），recall 分数 0.11。
- 同仓库（marshmallow）题：0 条（官方 113 与飞书 85 均无 marshmallow 相关题）。
- 低相似度本身不能证明不同；已按 scene-dedup.md 做人工语义比较与改名测试。

## 最相近已有题对比

| 最相近已有题 | 相同点 | 实质差异 | 改名测试结果 | 判断 |
| --- | --- | --- | --- | --- |
| `etree-xml-diff-patch`（官方 113，XML 树 diff/patch） | 都是“对两份结构化数据做差异并产出变更记录”的 diff 家族任务 | ① 数据模型不同：XML 元素/属性树 vs marshmallow Schema 声明的字段图；② 驱动方式不同：etree 基于树结构通用遍历，本候选必须沿 `schema.fields` 声明顺序并按字段类型（Nested/List）决定标量比较还是递归，脱离 schema 的通用遍历会被判错；③ 输出契约不同：`{op,path,left,right}` 中 path 用 `点号 + [i]` 表达 schema 路径；④ 兼容性目标不同：必须守住 dump/load/validate 零回归 | 改名后仍是“结构化 diff”外壳，但状态模型（schema 字段图 vs 通用树）、递归规则（按字段类型分发）与验证目标（schema 感知 + 既有 API 零回归）均不相同 | 不重复 |
| `go-cmp`（Go 值比较，同能力族） | 都比较两个值并报告差异 | ① 语言/生态不同（Go vs Python）；② go-cmp 是脱离 schema 的通用深度值比较，本候选是按 schema 字段图驱动、对未知键默认忽略、可按 `include_unknown`/`ignore_fields` 调视图；③ 无“声明顺序遍历 + 按字段类型递归”的语义约束 | 改名后 go-cmp 只剩“通用深度比较”，缺 schema 字段图、Nested(many)/List 下标路径与可见性选项，验证目标不同 | 不重复 |
| Mashumaro / attrs / cattrs（Python 序列化快照/版本迁移，同能力族） | 都涉及对象↔字典的序列化周边能力 | ① 它们是“带版本/默认值的（反）序列化与迁移”，本候选是“两份已序列化文档的 schema 感知 diff”，不含任何类型注册、默认值填充或版本迁移逻辑；② 验证目标不同：cattrs 等关心正确（反）序列化，本候选关心 diff 的 op/path/left/right 与既有 API 零回归 | 改名后只剩“对象与字典互转 + diff”外壳，但状态模型（diff 变更记录 vs 迁移映射）与失败恢复（未知键忽略策略）不同 | 不重复 |

## 同仓库题复核

- marshmallow 在官方 113 题与飞书 85 条记录中均不存在；本仓库无任何历史题，无同仓库撞车。

## 同能力族题复核

- 比较/序列化能力族已覆盖 `etree-xml-diff-patch`、`go-cmp`、Mashumaro/attrs/cattrs 等。本候选的核心难点是“沿 schema.fields 声明顺序、按字段类型（Nested 单值 / Nested(many=True) / List）分发的结构化 diff，并守住既有 API 零回归”，与“脱离 schema 的通用值比较”或“版本化快照/迁移”有实质差异。

## 自动召回的局限

- 文本相似度低（最高 0.11）仅说明字面不重合，不能替代语义判断；已对前 20、同仓库、同能力族逐项做场景目标/参与者/工作流/状态模型/冲突恢复/可观察结果/verifier 行为/推理路径八维比较，并执行改名测试。

## 飞书共享题面库

- 已全量读取 85 条记录，marshmallow 不在其中。
- 已写入候选记录并读回核对：记录 ID `recpwudpy7nWdk`，`去重判断=不重复`，`标注员=wff`，读回一致。
- 该记录是创建正式题包与 Trae 工作空间的前置门槛，已满足。

## 最终结论

**distinct（不重复）**

结论依据：本候选以“schema 字段图驱动 + 按字段类型递归 + 声明顺序遍历 + 未知键默认忽略 + 既有 API 零回归”为核心因果结构，与最接近的 `etree-xml-diff-patch`（通用树 diff）、`go-cmp`（通用值比较）、Mashumaro/attrs/cattrs（序列化快照/迁移）在状态模型、递归规则、验证目标与失败恢复上均有实质差异；改名测试后剩余工作流与验证目标仍不同。官方 113 题与飞书 85 条记录均无 marshmallow 相关题，无同仓库撞车。
