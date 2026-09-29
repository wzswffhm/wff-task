# 证据与结果契约

## evidence.json

`schema_version=2`，一个真实 proposal 路径对应一个包。
`packet_id` 是去掉 packet_id 后的整个对象的稳定 JSON SHA-256，键排序、UTF-8、不允许 NaN。
包含 proposal 原文件快照和解析内容、真实 Benchmark 题面、Source 比对范围与候选、
Git 检索、前置检查、当前说明书。输出不是自动评分结果。

原始文本在 proposal.text / benchmark.documents[].text；`sha256` 针对原文件字节。
source_comparison 中给 Source 和 Benchmark 的全部已读取清单及问题。
default 8 MiB 单文件内容、2 GiB 每目录集合、50000 条目、5000 个候选，压缩包最多两层；
支持 ZIP/TAR/GZIP/BZIP2/XZ 和内容标识识别。大文件保留流式整文件哈希，
部分比对/解包明确列缺口，不能当作完整扫描。比对文本片段不是百分数评分依据。

Git 报告绑定 proposal 的稳定 JSON 哈希，不能把别题 history.json 填过来。
本地 Git 只读已存在 refs；public GitHub 为显式联网查询。程序不执行 Source 脚本、
不启动 Docker 镜像，不自动 fetch/pull Git 历史。

## review.json

从 inventory 输出的 review.draft.json 填写。静态 templates 只展示字段，不是可提交结果。
必须填 reviewer、summary、scope_read（人工实际读过哪些路径/内容）、next_actions。
脚本校验结构与证据绑定，不能验证 Agent 理由的语义真实性；审查者负责逐条实读。

引用形式：

```json
{
  "document": "proposal.C_agent_task",
  "quote": "必须与该字段中的连续原文完全一致"
}
```

document 可为：

- `proposal.C_agent_task` / `proposal.A_modification_idea` / `proposal.B_modification_details`
  / `proposal.D_task_difficulties`（列表按换行拼接）。
- `proposal_sources`、`proposal_verify`、`expert_experience_skill` 等顶层文本字段。
- `benchmark:<文档sha256>`：benchmark.documents 中实际题面。
- `source:<文件sha256>`：Source 文本。压缩成员仅预装前 700 字；要引用其他内容先独立导出
  到审查工作目录并以 extra-evidence 纳入，不向交付目录写文件。
- `git:<candidate_id>`：已采集公开变更/本地提交的正文与 diff。
- `extra:<文件sha256>`：inventory --extra-evidence 读取的补查文本。

relevance 两轴分别填 score、confidence、reason、proposal_quotes、benchmark_quotes。
score 为数值 0–100 或 null；布尔、NaN、Infinity 均无效。
不得自行填写最终结论；finalizer 根据有效字段计算。

source_reuse.candidate_reviews：每个 candidate_id 必须有唯一处置，分类为
task_specific_reuse/common_upstream/boilerplate/provenance_only/unrelated/unresolved。
确认 task_specific_reuse 必须额外填 task_specific_evidence，具体解释任务特有性。
H02 提前拒收只需 packet_id、reviewer 和 source_reuse，不必填后续未做判断。

public_history：

- status 为 PASS/REVIEW/REJECT/NOT_APPLICABLE，reason 总是必需。
- PASS/REJECT 需 new_delta（区分新增部分与 baseline）、evidence 引用 A/B，
  repository_reviews 每个 repository 与 reason。
- 每个 history candidate 需 candidate_reviews，包含 candidate_id/classification/reason。
- classification 为 base_functionality/unrelated/unresolved/derived_from_public_change。
- 确认倒推需对应 publicly verified SHA、evidence 引用 git 候选原文，
  time_basis 为 public_at_review 或 known_before_submission；后者还需 timing_evidence。
- 搜不到不自动 PASS；PASS 必须由 Agent 判断覆盖是否足够，并解释限制。

content_checks 六项均 status=PASS/FAIL/REVIEW、reason、evidence。
skill_alignment=PASS 需要 difficulty_skill_map 覆盖 D 的每个零基索引：

```json
{
  "difficulty_index": 0,
  "skill_quotes": [{"document": "expert_experience_skill", "quote": "对应的真实经验"}]
}
```

redlines 为 code/clause/reason/evidence，引用当前说明书逐字条款；
可用 R01/R03/R04/R05/R07/R08；H02/R02 由对应证据处置自动产生。
不允许只填标签、没有命中事实。

## 覆盖缺口补证

issues 不允许删除或直接覆写。实际补查后将证据文件通过 inventory 的 --extra-evidence
重新收集，并填 coverage_resolutions：

```json
{
  "scope": "source",
  "issue_id": "对原 issue 对象作稳定 JSON SHA-256",
  "reason": "说明采用什么补查、看到什么、如何覆盖此前缺失部分",
  "evidence": [{"document": "extra:<sha256>", "quote": "补查结果的原文"}]
}
```

scope 为 source/history。issue_id 计算方式为
`review_common.digest(review_common.canonical(issue))`。
需要可信的实查输出，不能用“已检查无问题”代替内容证据。
未解决缺口保持 REVIEW；空 Source 不能拿空扫描结果证明无 Hack。
更新 Source 或 Benchmark 后重新采集，finalizer 检查已登记文件哈希、Source 文件增删；
复用旧评审前仍需重新 inventory，以发现新的 Benchmark 文件/检索范围变化。

## 输出

result.json 给 valid、validation_errors、conclusion、label、codes、blockers、warnings、
early_stop 和原始审查判断。无效的 review 不产生结论。result.md 含可读分数、理由、
问题与完整引用，方便沿着路径复核。`scope_read`/理由/引用不会被脚本代写。
确认 H02 时结果只保留最小拒收证据，不输出未做的后续判断。

退出码：0 ACCEPT、1 无效结果、2 REVIEW、3 FAIL、4 REJECT。
批处理应收集这些状态，而不是把非零都当程序崩溃。
生成校验和：

```bash
python3 scripts/sha256_manifest.py /绝对路径/obm-review-output \
  --base /绝对路径/obm-review-output --output /绝对路径/obm-review-output/SHA256SUMS
```
