# 2026-09-27 Windows 采购质检手册接入规则

本文件说明如何把 `windows-procurement-qc-manual-20260927/` 中的规则应用到当前直接 Harbor
交付流程。手册原文、WIP 94 项、历史问题库、证据模板和来源清单均随 Skill 分发；执行质检时
不得只读本摘要而跳过原文。

## 必读顺序

1. [手册阅读入口](windows-procurement-qc-manual-20260927/00-阅读入口.md)
2. [质检执行手册](windows-procurement-qc-manual-20260927/01-质检执行手册.md)
3. [WIP 94 项逐项对照](windows-procurement-qc-manual-20260927/02-WIP94项对照.md)
4. [历史问题库](windows-procurement-qc-manual-20260927/03-历史问题库与35题重点.md)
5. [逐项证据与报告模板](windows-procurement-qc-manual-20260927/04-逐项证据与报告模板.md)
6. [资料来源与核验边界](windows-procurement-qc-manual-20260927/05-资料来源与核验边界.md)

## 每题必须完成的手册审计

### 1. 冻结范围和身份

先登记题目来源、`task_id`、版本、ZIP SHA256、Task Hash、base commit、题面、环境、Solution、
测试树、required testcase、评分公式、镜像、工具链、模型和运行批次。历史结果与本次复验结果
分开保存，不能覆盖；不同版本、公式或测试树的结果不得混算。

### 2. 登记全部 WIP 94 项

为 FC-01–13、QD-SP-01–18、QD-SO-01–07、QD-IN-01–06、ENV-01–14、VV-01–36 建立完整
矩阵。每项填写 `PASS / FAIL / FLAG / BLOCKED / N/A`、证据位置、影响和处理建议。`N/A` 必须
写清适用性依据；没有证据不能记 PASS。WIP 中需要动态执行的项目不能用静态文件存在性代替。

### 3. 完成 D01–D20 动态审计

必须覆盖：同身份 Golden/no-change 对照、逐 testcase 终态、稳定性与干净重建、要求实际下发、
需求—测试—评分双向映射、每项得分与扣分、等价实现和故障反例、Mock 保真、Windows 工具与
真实终态、构建和产物身份、异常与日志完整性、Hack/泄露/绕过、独立复算、失败归因、批次分母
和交付闭环。每项均须有原始证据；未执行或证据不足写 `BLOCKED`。

### 4. 建立逐评分项证据链

每个得分项和未得分项都必须闭合：

```text
模型实际收到的要求与 SHA
  → testcase / assertion / rubric / 权重
  → 候选补丁或文件 SHA
  → Windows 实际命令、环境、退出码和原始日志
  → 精确 testcase 终态及 expected/actual
  → 对应轨迹和工具调用
  → 独立复算贡献与最终判断
```

只看总分、`reward.txt`、日志尾部、模型自评或 Golden 相似度均不能代替证据链。

### 5. 分离状态和根因

- 质检项：`PASS / FAIL / FLAG / BLOCKED / N/A`。
- 用例观察：`PASS / FAIL / SKIP / MISSING / ERROR / NOT_RUN`。
- 运行有效性：`VALID / INVALID / PENDING / CANCELLED`。

缺测、零测试、解析、权限、依赖、环境或运行链路故障不得伪装成模型能力 0；可信正式分数写
`null`，平台原始值另行保留。`timeout`、`missing`、`parse error` 只是现象，必须继续归因到
Prompt、Test、Env/平台、Rubric/聚合器、证据、稳定性、模型能力或完整性/Hack。

### 6. 等价实现、公平性和反例

核心功能必须走真实生产路径并接受独立等价实现。源码关键词、正则、Diff、固定私有函数、局部
变量、代码布局、特定调用方式、文件存在、日志文本和“能编译”只能作辅助证据。除 Golden 外，
至少用有独立依据的等价实现和删关键修复、只修一半、硬编码、死代码、吞异常、提前退出等反例
验证测试不会误杀或漏判。

### 7. Hack 和证据事实等级

逐份审查完整轨迹、工具请求与返回、网络、Git、缓存、挂载、Solution、隐藏测试、reward、旧产物
和评分目录。事件依次分为 `ATTEMPT`、`ACCESS_CONFIRMED`、`USE_CONFIRMED`、
`SCORE_IMPACT_PROVEN`，不得从搜索关键词直接跳到“抄答案得分”。轨迹缺失或截断到无法排除绕过
时判 `BLOCKED`。

### 8. 独立复算和复验

直接从 required ID、终态、rubric 条件和冻结公式复算；空清单、重复、缺项、skip、missing、
候选可写 reward 均不得产生正式分。任何题面、环境、Solution、Tests、required 清单或评分修改
都必须升级版本和 Hash，并在新干净环境重跑；旧模型轨迹作废。

## 与当前直接 Harbor 规则的关系

- 当前标准 Task 根目录和 14 个直接 Harbor jobs 仍是本项目交付硬门禁；采购手册在其上增加语义、
  公平性、有效性、Hack 和证据审计，不取消现有目录要求。
- 手册中的历史题目名称、历史分数、旧批次模型次数和历史修复结论仅用于风险检查，不能直接当作
  当前题缺陷或当前运行证明。
- WIP 与 Windows 适配口径冲突时必须双列结论。例如当前本地规则将 5–27 条 testcase 作为正常
  范围，但 WIP VV-12 的原口径为 5–20；应分别记录当前项目门禁和 WIP 合规结果，并给出版本化
  适配依据，不能删除有效测试来凑数量。
- 公开上游测试与隐藏验收分开记录；隐藏测试、Golden 和评分材料必须隔离。不能因为组织方交付包
  含 `tests/`、`solution/` 就认定模型可见，必须用运行时挂载和权限证据判断。
- 不设置手册未规定的统一最长执行时间。按题目冻结的资源预算和 timeout 判断；超时须先查环境、
  就绪、死锁、测试预算和模型行为，不能仅凭耗时直接判模型 0。

## 最小审计产物

最终质检结果目录至少应包含以下内容或可定位的等价文件：

- `scope-and-identity.md/json`
- `wip94-review.md/json`，完整 94 行
- `dynamic-d01-d20-review.md/json`，完整 20 行
- `requirement-testcase-rubric-map.md`
- `golden-nochange-matrix.md`
- `model-run-item-audit.md/json`
- `hack-events.md/json`
- `score-recompute.json`
- `remediation-retest.md`
- 原始日志和 SHA256 索引

缺少范围身份、WIP 94 项、D01–D20、逐项证据链或独立复算时，自动检查即使通过，最终结论也
只能是 `BLOCKED`。
