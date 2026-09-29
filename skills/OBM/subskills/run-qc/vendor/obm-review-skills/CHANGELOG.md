# Changelog

## 6.1.2-local - 2026-09-24

- `obm_inventory.py` 新增 `--governing-document`，允许证据包显式绑定用户指定的
  最新正式需求及其 SHA-256，避免继续固定使用随包旧需求副本。
- 保留随包说明书作为未传参数时的兼容默认值，并新增外部需求绑定回归测试。
- `sha256_manifest.py` 排除 Python 运行产生的 `__pycache__` 和 `.pyc`，防止临时
  字节码进入工具完整性清单。

## 6.1.1 - 2026-09-23

- `sources/` 为空时仍允许不提供 `README.md`；目录非空时必须在根部提供
  `sources/README.md` 常规文件。
- 新增空目录、README 缺失、README 文件有效和 README 同名目录四类回归测试。
- 运行完整 40 项 unittest，全部通过；对实际非空交付目录执行 CLI 时正确报告
  `sources/README.md` 缺失。

## 6.1.0 - 2026-09-22

- 将原 `TB_Samples/proposal_validator` 的校验器和 507 项离线任务映射纳入 Skill：
  `scripts/validate_proposals.py` 与 `references/benchmark_tasks.json`。
- 新增 `references/proposal-validation.md`，并将预检命令改为 Skill 根目录相对路径；
  删除对缺失 schema、builder 和原工作区目录结构的说明。
- Proposal type A 不强制提供 Git 仓库 URL；type B 仍必须提供。
- 新增 validator 回归测试，覆盖随包映射定位和 A/B URL 规则。
- Skill 核心实现不依赖 `obm-workflow-and-skills` 的其他代码目录。Benchmark checkout
  仍是审查输入；Git、Docker、网络与 lark-cli 仅在对应可选流程中使用。
- 在原目录和仅含该 Skill 的临时目录中分别运行 36 项 unittest，全部通过；
  隔离副本中的 validator CLI 也可独立加载。

迁移前的 validator 文件已从 `TB_Samples/proposal_validator` 移除。回滚时将
`scripts/validate_proposals.py`、`references/benchmark_tasks.json` 和
`references/proposal-validation.md` 移回独立目录，并恢复 SKILL 中的旧入口。

## 6.0.1 - 2026-09-19

授权来源：用户要求先注册 Skill，并指定飞书输出使用 lark-cli。

- 将仓库维护源安装到 TRAE CN 用户级 `~/.trae-cn/skills/obm-review-skills`。
  安装包与维护源逐文件校验，保留原目录和路由名，不依赖源码目录外的 AGENT.MD。
- 新增 references/review-governance.md，随包提供父级审查约定。
- 新增 references/lark-publishing.md：批次逐题汇总、lark-cli v2 创建/追加文档、
  写入后回读、保存发布状态及防止重复新建/追加。未指定目的文档时可在个人空间创建。
- lark-cli 1.0.41 已在本机可用；创建/追加/fetch 命令通过 help 和 dry-run 检查。
  此次仅注册与配置工作流，没有实际创建飞书文档，真实发布成功不能由 dry-run 推断。
- SHA256SUMS 改为相对 Skill 根目录的自包含清单，安装后可直接核验。
  未修改审核 Python 脚本、评分标准、用户说明书或旧 runtime Profile。

回滚：原 6.0.0 快照与校验和在 `OBM-Skills/archive/register-skill-v6.0.0-20260919/`。
先保存当前版本，再从快照恢复维护源；如全局安装已存在，需同步恢复该安装副本。
不要合并覆盖目录留下新资源；不要恢复用户已删除的 checklist。

## 6.0.0 - 2026-09-18

授权来源：用户要求按本地《OBM Source 收集说明书》升级真实内容审查，
明确 C_agent_task 的领域/核心能力双评分、Source 数据复用拒收、A 的公开 commit/PR 来源审查。

变更：

- 新增真实 Benchmark instruction 定位、版本分离、ProgramBench 停止状态容器文档读取；
  缺文档为 REVIEW，不用 metadata/tests.json 猜题面。
- 双相关度独立 0–100，<20 FAIL、20–49.99 REVIEW、≥50 PASS，按最差项合并。
- 以内容比对候选替换 H01 URL 自动拒收；确认任务特有复用为 H02，立即停止该题。
  支持改名、JSON/换行规范化、部分内容、ZIP/TAR/GZIP/BZIP2/XZ，
  大文件保留整文件哈希，并显式记录未做部分比对/解包的覆盖缺口。
- 新增本地 Git 和公开 GitHub commit/PR 查询，保存 SHA、URL、正文/diff、时间和搜索限制；
  分清公共 baseline 与 A 原创增量，没搜到不能自动证明原创。
- 重写 inventory 为逐交付证据包；重写 payload 校验为本地人工结果校验与结论计算，
  验证引用和哈希绑定，输出 JSON/Markdown。旧 Base payload CLI 为不兼容接口变更。
- 新版 rubric、契约与未决模板替换旧 checklist 流程；不恢复用户已删除的 checklist。
  保留用户提供的说明书原文。旧 A/B/C Profile 保持字节不变，仅作 authoring/runtime 兼容。
- 删除旧 URL 定罪和旧字段 fixtures，使用临时真实数据构造 33 项回归测试。
  更新父级 AGENT.MD，移除旧线上 revision 和绝对路径的初验权威地位。

验证：

- Python 3.9 标准库；33 项 unittest 通过，包含阈值边界、Source 改名/压缩/部分复用、
  来源链接误判、空内容、证据失效、公开历史与 baseline 区分、缺题面、H02 提前拒收。
- 实测 jq-order-report：真实读取 risk-scorer-replay 及其迁移/回放契约，
  扫描配置的六组本地 Benchmark 目录并查询 jq 公开历史；保留预检失败与覆盖缺口，
  不修改样例来制造通过。样例报告在工作区 `.obm-review-work/sample-v6-final/`。
- ProgramBench 真镜像文档提取未在本机验证（当前没有任务镜像）；停止容器读取/清理流程
  通过隔离测试。镜像内路径须实查配置，不默认猜 `/docs`。
- 补充压缩流测试曾发现 Python 3.9 gzip 参数不兼容，修正 fileobj 后原断言通过。

迁移：

- 新命令详见 SKILL.md，输出必须在交付目录外。
- 本地报告优先；不再由初验默认更新飞书，不要求初验已有 rollout。
- 扫描不能证明任意编码/重写不存在；已列出的覆盖缺口需补查证据或保持 REVIEW。

回滚：

- 升级前工作区快照位于 `OBM-Skills/archive/content-review-v6-20260918/`，有 SHA256SUMS。
  在该目录运行 `shasum -a 256 -c SHA256SUMS` 核验原始文件。
- 先将当前 `OBM-review-skills` 移到一个未占用的备份目录，再将快照内同名目录与
  AGENT.MD 复制回 `OBM-Skills/`；不要直接覆盖合并，以免留下 v6 新增脚本。
- 快照忠实保留用户删除 checklist 和新增说明书的状态（见 state.json）。
  不要使用 git checkout aedc071 恢复整个目录，否则会覆盖这两项用户修改。
- 恢复后重新生成活动版本校验和。版本回滚不撤销已生成报告或改写外部表格。

## 5.2.1 - 2026-09-16

Approval source:

- User confirmed that upstream JSON Schema failures are blocked before entering the review
  workflow and approved removing the redundant Checklist step.

Changed:

- Removed the Checklist instruction to cite the upstream JSON Schema result.
- Renumbered the remaining execution steps from 3/4 to 2/3.
- Kept the upstream Schema gate in `SKILL.md` as a workflow prerequisite; it is not a manual
  Checklist action.

Impact:

- No review criterion, severity mapping, or A/B/C Profile requirement changed.
- The active Checklist now starts manual review after the upstream gate and H01 precheck.

Rollback:

- Restore the previous three-step wording at the top of
  `references/checklist.md`.
- Re-run SHA-256 verification.

## 5.2.0 - 2026-09-15

Approval source:

- User required three comparison passes against the original
  `/Users/bytedance/Study/OBM/checklist.md` and explicitly preferred deletion or rewriting over
  accumulating unclear checks.

Changed:

- Restored the original six-part human-review structure as the active Checklist backbone.
- Restored explicit checks for Benchmark capability alignment, expert knowledge credibility,
  simple legitimate solutions, and the seven Verify questions.
- Reduced the active Checklist from 375 to 122 lines.
- Removed workflow commands, Base operating procedure, public-contract category lists, repeated
  Profile IDs, and duplicated rollout detail from the human Checklist.
- Kept only the A/B/C differences that materially change required evidence.
- Clarified that non-formal rejection concepts from the teacher draft map to `REVISE` unless a
  revision 1160 red line is directly evidenced.

Three-pass audit:

1. Semantic fidelity: restored omitted teacher requirements.
2. Clarity and duplication: removed internal implementation detail and repeated policy.
3. Executability: made each checkbox single-purpose and evidence-addressable.

Migration impact:

- Machine-readable A/B/C profiles and workflow behavior are unchanged.
- Reviewers follow one compact Checklist; operational details remain in `SKILL.md`.

Rollback:

- Restore `checklist-before-convergence.md` from
  `OBM-Skills/archive/checklist-convergence-20260915`.
- Re-run Checklist coverage tests, payload validation, and SHA-256 verification.

## 5.1.0 - 2026-09-15

Approval source:

- User judged the uniform initial-review checks too strict and approved separate A/B/C evidence
  profiles.
- User approved `MUST / SHOULD / DEFER`, controlled public-contract projection from Verify, and
  C-class acceptance based on obtainable assets plus a reproducibility path.

Changed:

- Updated the Proposal specification source to revision 1596.
- Added canonical machine-readable profiles for A repo changes, B new objectives, and C real-work
  tasks.
- Added `ACCEPT_WITH_NOTES`; SHOULD gaps no longer force a rewrite.
- Distinguished hidden input/workload variation from hidden objectives, metrics, business rules,
  and pass/fail semantics.
- Relaxed source-shape requirements by type: A may use a fixed public repository, B need not
  provide source code, and C need not provide a complete Harbor/Docker package at initial review.
- Added profile IDs and unknown-type warnings to inventory output.

Migration impact:

- Formal red lines and H01 are unchanged.
- Existing 5.0.0 conclusions may be re-audited when they were based only on exact-path,
  exhaustive-protocol, or Verify-line parity requirements.
- `ACCEPT_WITH_NOTES` continues to use the existing Base value `通过`; risks remain mandatory in
  the explanation.

Rollback:

- Restore the complete 5.0.0 snapshot from
  `OBM-Skills/archive/abc-tiered-review-20260915`.
- Re-run profile tests, Hack fixtures, payload validation, and SHA-256 verification.

## 5.0.0 - 2026-09-15

Approval source:

- User approved separating expert-data initial acceptance from later rollout-based Skill
  effectiveness evaluation.
- User approved deterministic Proposal-to-Instruction authoring that does not promote private
  Verify requirements into the public task.

Changed:

- Split the governing sources into rejection policy revision 1160 and Proposal specification
  revision 942.
- Changed the default review phase to `initial_review`; rollout trajectories and Skill gain are no
  longer initial hard gates.
- Added Source entity, cross-case identity, five-part Proposal semantics, and best-effort static
  solvability checks.
- Updated R07 to the exact current clause `Skill 泄漏或基于test书写`.
- Added FrontierSWE and the documented `froniterSWE` spelling to the target-source registry.
- Added structured-Proposal canonicalization, `proposal.json` support, canonical seed-conflict
  reporting, source manifests, and opt-in rollout inventory.
- Replaced the rollout-heavy example payload with an initial-review record.
- Added regression tests for structured deduplication, FrontierSWE H01, source inventory,
  optional rollout discovery, current R07 evidence, and initial payload validation.

Migration impact:

- `通过` now means expert-data initial acceptance and eligibility for instruction authoring and
  later rollout. It does not prove solvability, final Benchmark acceptance, or Skill impact.
- Existing post-rollout evidence remains valid and is reviewed through `post_rollout_review`.
- Existing Base fields and enum values are unchanged; initial records may omit rollout fields.

Rollback:

- Restore the complete pre-change snapshot from
  `OBM-Skills/archive/initial-review-scope-20260915`.
- Re-run Hack fixtures, review-tool unit tests, payload validation, and SHA-256 verification before
  resuming reviews.

## 4.1.0 - 2026-09-11

Approval source:

- User required eliminating the ambiguous `OBM-Skills` / `OBM_Skills` split and moving all
  executable helpers into the canonical Skill directory.

Changed:

- Moved all four Python helpers to `OBM-review-skills/scripts/`.
- Updated Skill and Checklist commands to use the canonical directory.
- Changed `obm_hack_scan.py` to resolve `source-registry.json` relative to its owning Skill.
- Removed the standalone top-level `OBM_Skills` directory after migration validation.
- Archived the complete pre-migration Skill and script layout at
  `OBM-Skills/archive/script-layout-migration-20260911`.

Migration impact:

- Rules, references, registry, fixtures, templates, executable code, versioning, and checksums now
  have one ownership root.
- Script command paths changed; scanner behavior and review judgments are unchanged.

Rollback:

- Restore the archived `OBM_Skills/scripts` directory and Review Skill after explicit approval.
- Re-run positive/negative fixtures, full scanning, payload validation, and SHA-256 verification.

## 4.0.0 - 2026-09-11

Approval source:

- User explicitly approved merging `obm-hack-checklist-skills` into `obm-review-skills` and
  deleting the standalone Skill.

Changed:

- Made the H01 source-Hack scan an internal mandatory Step 0 of `obm-review-skills`.
- Migrated `source-registry.json` and positive/negative scanner fixtures into this Skill.
- Updated `obm_hack_scan.py` to resolve the registry from this Skill.
- Removed all runtime references to the standalone Hack Skill.
- Archived the complete standalone Skill before removal at
  `OBM-Skills/archive/skill-merge-obm-hack-into-review-20260911`.

Migration impact:

- `obm-review-skills` is the only installed OBM audit Skill and handles both precheck and review.
- H01 semantics, stop behavior, Base result mapping, scanner exit codes, and evidence requirements
  are unchanged.
- Existing Base records are unchanged.

Rollback:

- Restore the archived standalone Skill and its `.trae/skills` symlink after explicit approval.
- Restore Review Skill version 3.1.0 and the scanner's former registry path.
- Re-run positive/negative fixtures, full inventory, payload validation, and SHA-256 verification.

## 3.1.0 - 2026-09-11

Approval source:

- User required the merged Checklist to live inside Skill resources and the scattered active
  policy documents to be backed up and removed.

Changed:

- Moved the canonical Checklist to `references/checklist.md`.
- Consolidated Proposal, Hack, red-line evidence, evidence search, Base contract, maintenance,
  and script execution rules into that file.
- Removed duplicate Review reference documents after archival.
- Preserved the exact pre-migration files and SHA-256 values under
  `OBM-Skills/archive/checklist-migration-20260911`.

Migration impact:

- Reviewers read one active Checklist resource instead of multiple policy files.
- `AGENT.MD`, Skill entrypoints, scripts, source registry, versions, changelogs, and templates
  remain active resources.

Rollback:

- Restore archived reference files and prior Skill references after explicit user approval.
- Re-run Skill validation and regenerate SHA-256 manifests before resuming audits.

## 3.0.0 - 2026-09-11

Approval source:

- User prohibited human-facing internal case IDs and required real file paths instead.

Changed:

- Renamed the external Base identity field from `案例ID` to `题目路径`.
- Migrated all 21 existing review records to exact workspace-relative seed-file paths.
- Prohibited new `PB-*`, `TB3-*`, or other invented case aliases in records, reports, payloads,
  and final responses.
- Kept system `record_id` and historical aliases internal for API joins and traceability only.

Migration impact:

- Existing curated views retain the renamed field by field ID.
- Historical reports and payloads retain old aliases as backward-compatible evidence.
- New external artifacts must use `题目路径`.

Rollback:

- Rename the field back to `案例ID` and restore the preserved path-to-alias mapping only with
  explicit user approval.
- Do not delete the path values or historical evidence.

## 2.1.0 - 2026-09-11

Approval source:

- User requested merging a teacher-authored Proposal checklist with the existing Hack and review
  policies.

Changed:

- Added the shared `checklist.md` as a mandatory review input.
- Applied section B to Proposal, Verify, and Skill seed review.
- Applied section C only to generated artifacts that exist.
- Mapped `ACCEPT/REVISE/REVIEW/REJECT` to current Base result semantics.
- Distinguished `DEFER` from pass, failure, and missing current hard gates.
- Preserved the original teacher-authored checklist for rollback and comparison.

Migration impact:

- A Proposal-stage `ACCEPT` no longer risks being confused with final Benchmark acceptance.
- `REVIEW` maps to `需补证据`; `REVISE` maps to `需重做`; explicit rejection maps to
  `拒绝当前交付`.
- Existing hard gates and Base records are unchanged.

Rollback:

- Restore version 2.0.0 and remove the shared-checklist references.
- No Base rollback is required because this release does not modify records.

## 2.0.0 - 2026-09-11

Approval source:

- User required target Benchmark source reuse to become a blocking Hack precheck that runs before
  all normal review.

Changed:

- Added mandatory invocation of `obm-hack-checklist-skills` before inventory and review.
- Added `H01-目标Benchmark源码复用` short-circuit semantics.
- Required immediate `拒绝当前交付` and minimal Base evidence for H01 cases.
- Prohibited further Proposal, Verify, Skill, trajectory, implementation, and rerun analysis after
  a new H01 hit.

Migration impact:

- All existing and future deliveries must pass the Hack precheck.
- Previously reviewed H01 cases are reclassified while preserving old technical findings.
- Normal four-part review applies only to cases that pass the precheck.

Rollback:

- Restore version 1.3.0 only with explicit user approval.
- Re-evaluate each H01-rejected row before changing its Base conclusion.

## 1.3.0 - 2026-09-11

Approval source:

- User required every completed task that writes Feishu Base to return a clickable review-table
  link for direct inspection.

Changed:

- Required final responses to state whether the Base write completed.
- Required a clickable URL containing the exact review `table_id` and preferred `view_id`.
- Standardized `核心审查` as the default completion link when no other view is requested.
- Prohibited returning only tokens, IDs, or supplier raw-submission links.

Migration impact:

- Future OBM audit completions that write Base must include the resolved review link.
- Existing Base records and view configurations are unchanged.

Rollback:

- Restore version 1.2.0 to remove the completion-link requirement; no Base data rollback is needed.

## 1.2.0 - 2026-09-10

Approval source:

- User required every red-line judgment to quote the governing Lark document directly and report
  its location.

Changed:

- Added `references/redline-evidence.md` with revision 370 exact rejection clauses and block IDs.
- Prohibited red-line decisions based only on memory, summaries, or undocumented restrictions.
- Required `红线命中说明` to include document, revision, section, block ID, exact quote, and
  case-specific matching facts.
- Extended `validate_review_payload.py` to reject positive red-line judgments missing any of those
  source or case-evidence elements.
- Reclassified the Cinema 4D case because revision 370 contains no rendering/editing/continuous-
  operation rejection clause; its Proposal, Verify, and rollout defects remain.

Migration impact:

- New-trial red-line explanations are refreshed from revision 370.
- Cinema 4D changes from `拒绝当前交付` to `需重做`.
- Technical findings and missing-rollout findings remain unchanged.

Rollback:

- Restore version 1.1.0 only with explicit user approval and an identified governing source for
  the former red-line rule.

## 1.1.0 - 2026-09-10

Approval source:

- User explicitly requested adjacent judgment/explanation columns and fewer visible labels through
  grouped Base views.

Changed:

- Added a four-view layout: core review, seed-field review, rollout evidence, and technical
  diagnostics.
- Required every judgment field to be immediately followed by its explanation field.
- Limited the primary view to essential hard-gate and decision fields.
- Kept optional telemetry and technical labels in focused views instead of deleting data.

Migration impact:

- Existing records and fields remain intact.
- The original default views are renamed to `核心审查`.
- Three focused views are added to each review table.

Rollback:

- Rename `核心审查` to `表格`.
- Restore all fields as visible in the original view.
- Delete the three focused views only after explicit user approval.

## 1.0.0 - 2026-09-10

Approval source:

- User explicitly requested that the OBM audit workflow be created and continuously maintained as
  a Skill under `/Users/bytedance/Study/OBM/OBM-Skills`.

Added:

- Four-part hard gate: Proposal, Verify, Skill, and Agent rollout trajectory.
- Evidence search order covering case, supplier/batch, and all requested roots.
- Explicit found/missing/suspiciously-misplaced evidence statements.
- Paired explanation columns for every Base judgment/result field.
- Separation of model, infrastructure, benchmark, evidence-chain, and policy failures.
- Feishu Base dry-run, serial write, and readback validation contract.
- Inventory, payload validation, and SHA-256 helper scripts.

Migration impact:

- Older reviews that treated missing A/B, Agent Review, run IDs, standard directories, or source
  snapshots as independent rewrite gates must be reclassified.
- Existing technical findings remain valid.
- Missing rollout trajectory remains blocking under the current pre-workflow process.

Rollback:

- Restore the last approved predecessor policy from the reports marked as superseded.
- Regenerate Base payloads using that policy.
- Obtain explicit user approval before writing rollback results.
# 6.1.3-local - 2026-09-25

Changed:

- Required both A- and B-type proposals to include a plausible Git repository URL in `proposal_sources`.
- Kept `related_question` bound to a real task folder in the selected benchmark mapping.
- Kept `domain` at two or three slash-separated levels and enforced the mapped official prefix for every classified benchmark.
- Added forward-compatible handling for a one-level official classification: the public domain must be `<benchmark>/<classification>`.
- Added positive and negative regression coverage for all six benchmark families, domain shape, task-folder identity, and A/B source URLs.

Impact:

- A-type packages that previously used only a prose source description now fail static validation until a Git repository URL is added.
- ProgramBench remains freeform for domain content, but still requires two or three clean levels and a real mapped task folder.

Rollback:

- Restore version `6.1.2-local`, `scripts/validate_proposals.py`, and `tests/test_validate_proposals.py`, then regenerate `SHA256SUMS`.
