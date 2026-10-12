# 题目场景去重

本文件用于新题和新 proposal。目标是拦截“换了仓库、语言或名词，但核心任务仍与已有题相同”的候选题。返修现有题目时，只有场景目标、工作流、状态模型或验证目标发生实质变化才需要重做。

## 比对范围

必须覆盖：

1. 当前 benchmark 的完整本地题库，包括 manifest、全部题面和可见验证说明；
2. 当前项目已有的 proposal、工作目录、交付目录和压缩包；
3. 项目共享登记表中其他窗口的 `reserved`、`candidate` 和 `packaged` 记录；
4. 与候选题同仓库、同子系统或同能力族的题目，即使文本相似度不高。
5. 项目飞书配置 `feishu-gsb.toml`（项目根目录或 `--config` 指定路径）中 `scene_dedup` 表的共享记录。至少读取`题目编号`、`核心场景`、`题面`、`对比题面`和`去重判断`；它用于发现其他机器或窗口已经登记、但尚未同步到当前项目文件系统的候选。

不要只比较任务 ID、标题、仓库或语言。也不要只查 `related_question`。

读取飞书共享记录时只使用已验证 user 身份和配置中的 Base/table/view；使用 `base +record-list` 或 `base +record-search` 的只读调用。共享表无法访问或返回不完整时，去重材料不完整，停止形成最终结论，不得把“本地没搜到”写成 `distinct`。

## 候选场景档案

正式建题前，在工作目录外或候选目录中创建内部 `scene-profile.json`。它不属于正式提交包。DeepSWE 档案使用简洁英文，字段如下：

```json
{
  "benchmark": "deepSWE",
  "candidate_title": "Short working title",
  "upstream_repo": "owner/repository",
  "scenario_goal": "The concrete problem and success condition.",
  "actors": ["Who or what initiates and observes operations."],
  "domain_objects": ["The objects whose state or behavior changes."],
  "workflow": ["Ordered operations and important branches."],
  "state_and_lifecycle": ["States, ownership, ordering and transitions."],
  "conflicts_failures_recovery": ["Conflicts, crash points and recovery semantics."],
  "observable_outcomes": ["Publicly visible behavior and compatibility requirements."],
  "verifier_behaviors": ["Behavioral distinctions the verifier will test."],
  "task_difficulties": ["Reasoning difficulties, not a feature list."]
}
```

内容应描述行为，不写预定文件名、私有函数或参考实现路线。候选场景尚未明确到能填完这些字段时，不适合进入题包生产。

## 自动召回

运行：

```bash
"$OBM_PYTHON" "$OBM_SKILL_DIR/scripts/check_scene_overlap.py" \
  --candidate ./work/candidates/example/scene-profile.json \
  --benchmark-root ./Benchmark/deep-swe-main/tasks \
  --project-root . \
  --top 20
```

脚本会读取 benchmark manifest、全部 `instruction.md`、项目内现有 `proposal.json`，以及共享登记表中的活动候选，输出文本上最接近的题目；同仓库题目即使未进入前 20 名也会保留。`--top 0` 可输出全部结果，`--json` 可生成机器可读结果。

该脚本是候选召回器，不是判重器。低相似度不能证明场景不同。跨语言描述、不同领域术语和抽象层级变化都可能掩盖同构场景。

## 人工语义判断

对召回的前 20 道题、同仓库题和同能力族题逐项比较：

| 维度 | 要回答的问题 |
| --- | --- |
| 场景目标 | 两题最终解决的问题和成功条件是否相同？ |
| 参与者与对象 | 谁对什么对象操作？对象只是换名，还是承担不同职责？ |
| 工作流 | 操作序列、分支、组合行为和外部交互是否相同？ |
| 状态模型 | 状态、所有权、排序、生命周期和持久化关系是否相同？ |
| 冲突与恢复 | 并发冲突、失效条件、崩溃切点和恢复语义是否相同？ |
| 可观察结果 | 用户能看到的 API、输出、错误和兼容性目标是否相同？ |
| verifier 行为 | 两个 verifier 实际区分的正确与错误实现是否相同？ |
| 推理路径 | Agent 去掉专有名词后是否会采用基本相同的设计和验证方法？ |

执行改名测试：把仓库名、类型名、协议名、字段名和接口名替换成通用名，再比较两题。如果剩下的工作流、状态转移、失败恢复和验证目标仍基本相同，应判为重复。

## 结论

只允许以下三种结论：

- `distinct`：核心目标或因果结构有实质差异，正确实现需要不同的状态模型、冲突处理或验证设计。共享语言、库类型或通用技术不影响结论。
- `high-risk`：存在较多结构重合，当前证据不足以证明新场景有独立价值。不得继续生产，应重新设计后再检查。
- `duplicate`：主要差异只是仓库、语言、API、数据格式、参数或测试值；改名测试后仍是同一任务。停止生产并更换选题。

不要用相似度百分比直接决定结论。判断依据必须写成事实。

## 去重记录

把记录保存在内部工作区，例如 `work/<candidate-or-task-id>/scene-overlap-review.md`。正式包不包含该文件，除非当前 OBM 规范明确要求。记录至少包含：

```text
候选题：
候选档案散列：
检查日期：
检查语料：benchmark 题目数量、项目 proposal 数量
登记表活动候选数量：
飞书共享去重记录数量：

最相近已有题 | 相同点 | 实质差异 | 改名测试结果 | 判断

同仓库题复核：
同能力族题复核：
自动召回的限制：
最终结论：distinct / high-risk / duplicate
结论依据：
```

候选题的目标、工作流、状态模型、失败恢复或 verifier 行为在复核后发生实质变化，原结论失效，必须重新生成档案并复核。

## 本地与飞书双写登记

每次形成 `distinct`、`high-risk` 或 `duplicate` 结论后，都必须运行 `scripts/register_scene_dedup.py`。它使用项目飞书配置 `feishu-gsb.toml`（项目根目录或 `--config` 指定路径）中唯一的 `scene_dedup` 目标和已验证用户身份，不使用最终交付表的 `submission` 坐标。

飞书表的已核对字段为：

| 本地含义 | 飞书字段 | 写入规则 |
| --- | --- | --- |
| 核心场景 | `核心场景` | 候选题真正要解决的问题、工作流和关键状态变化 |
| 对比对象 | `对比题面` | 最相近已有题的编号、标题或记录链接；多个对象用分号分隔 |
| 结论 | `去重判断` | `distinct`→`不重复`，`high-risk`→`疑似重复`，`duplicate`→`重复` |
| 事实依据 | `判断依据` | 说明相同点、实质差异、改名测试和 verifier 差异 |
| 标注身份 | `标注员` | 写入配置中已验证用户的 `open_id`，不能写显示名或 bot 身份 |
| 唯一键 | `题目编号` | 使用登记表分配的 `YYYY-MM-DD-N`，按此字段 upsert |
| 候选题面 | `题面` | 尚无正式 proposal 时写候选场景摘要；已有公开契约时可写公开题面，不写隐藏测试或参考答案 |

示例：

```bash
"$OBM_PYTHON" "$OBM_SKILL_DIR/scripts/register_scene_dedup.py" \
  --root . \
  --reservation-id UUID-FROM-RESERVE \
  --conclusion distinct \
  --review-file ./work/YYYY-MM-DD-N-description/scene-overlap-review.md \
  --comparison "最相近题编号及标题" \
  --core-scene "候选题核心场景的中文摘要" \
  --question-text "候选题面或公开需求摘要"
```

`--rationale` 未提供时，脚本读取 review 中的`结论依据：`；`--comparison` 未提供时，脚本读取 review 表格第一列。核心场景和题面未显式提供时回退到共享登记表中的 `scene_summary`。这些回退内容仍须足以让另一位标注员理解场景，不能只写 slug、仓库名或 API 名。

脚本执行顺序是：

1. 核对 `auth status` 的 `appId`、用户 `openId` 和 verified 状态；
2. 解析并核对 Base、表、视图、字段 ID、字段类型和`去重判断`选项；
3. 按`题目编号`精确查询。没有记录则创建，一条记录则更新，多条同名记录则停止；
4. 写入后读回并核对全部字段及`标注员`；
5. 保存 `work/<proposal-name>/scene-dedup-record.json`；
6. 更新 `work/task-registry.json` 的 `dedup` 元数据和状态：`distinct`→`candidate`，其余结论→`rejected`。

脚本可安全重跑；它续写同一飞书记录，不重复建行。飞书写入、读回或本地持久化任一步失败时，不得手工把状态改为 `candidate`。如果飞书写入已成功但本地步骤失败，修复问题后重跑同一命令完成续传。

调试字段映射或预览载荷时使用 `--dry-run`。该模式允许身份、目标、字段和已有记录的只读核对，但不写飞书、不生成本地记录、也不更新共享登记表。
