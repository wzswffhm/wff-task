# 独立安装的审查约定

本文件将仓库 `OBM-Skills/AGENT.MD` 的审查约定纳入 Skill 包内，
供全局安装使用。资源路径均以本 Skill 根目录为基准，不依赖安装目录之外的文件。
维护时同步仓库约定与本文件；具体评分标准仍由 review-rubric.md 定义。

当前专家数据初验以 `references/OBM Source 收集说明书.md`、
用户明确的相关度阈值和 `references/review-rubric.md` 为准。
证据包记录说明书 SHA-256。旧线上 revision、已删除的 checklist、
旧机器路径和 `proposal-type-profiles.json` 不再作为初验权威。

1. 运行随包 `scripts/validate_proposals.py`，或消费该脚本生成的当前报告或明确通过声明。
2. 比对真实 Source 与 Benchmark 任务内容；只有官方链接不能证明 Hack。
   确认任务特有数据/代码/tests/答案复用为 H02，拒收并停止该题。
3. C_agent_task 对真实 related_question 题面，分别给领域与核心能力 0–100 分。
   每项 <20 FAIL、20–49.99 REVIEW、≥50 PASS；不平均。缺题面则 null/REVIEW。
4. 检索所有声明的 Git 仓库公开历史，区分 baseline 与 A 新增部分。
   使用不可变变更证据，搜索无结果不证明原创。
5. 审查资产、可行性、原创任务、Verify、D-Skill 对应与泄漏。

结论按 REJECT > FAIL > REVIEW > ACCEPT 合并。跳过或缺证据不算 PASS。
初验通过不表示已实证可解或 Skill 有效；后续 rollout 保持模型/输入/verifier 一致，
隔离容器、工作区、会话和缓存。Seed 无 Skill 失败或 >100 轮；
Skill 使失败转成功，或轮次和时长均降低至少 30%。

每题以真实路径标识，保留供应商/批次/文件名层级，哈希只作关联。
先保存本地可复核结果。用户要求飞书输出时，通过 `lark-cli` 创建或更新文档并回读；
缺省目的文档可按该请求新建，步骤见 `references/lark-publishing.md`。
既有发布授权无需逐题重复确认。不自动通知他人或扩大文档权限。

已授权任务范围内完成实现、验证和记录，不逐文件重复申请。
维护版本与校验和，回滚保留用户原有文件增删状态。
