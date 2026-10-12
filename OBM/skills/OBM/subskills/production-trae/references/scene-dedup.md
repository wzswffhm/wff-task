# 题目场景去重

本文件用于新题和新 proposal。目标是拦截“换了仓库、语言或名词，但核心任务仍与已有题相同”的候选题。返修现有题目时，只有场景目标、工作流、状态模型或验证目标发生实质变化才需要重做。

## 比对范围

必须覆盖：

1. 当前 benchmark 的完整本地题库，包括 manifest、全部题面和可见验证说明；
2. 当前项目已有的 proposal、工作目录、交付目录和压缩包；
3. 项目共享登记表中其他窗口的 `reserved`、`candidate` 和 `packaged` 记录；
4. 共享飞书题面库中的全部记录；
5. 与候选题同仓库、同子系统或同能力族的题目，即使文本相似度不高。

不要只比较任务 ID、标题、仓库或语言。也不要只查 `related_question`。

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

## 共享飞书题面库

deepSWE 的人工去重记录也保存在共享飞书 Base，供不同工作区和使用者查询：

```text
https://jcnyoyfbeyxi.feishu.cn/base/NqtYbxHF1aEYrNsyJSRcUFvMnbe?table=tblk47ilQNyL7Aim&view=vewF5fmGFr
```

该表补充本地 Benchmark、项目登记表和题包检查，不替代它们。开始去重时先读完表内所有记录，再把候选的 `题面`、`核心场景` 与历史记录作语义比较；不能只搜题目编号或标题。当前表只收录 deepSWE 场景，不要把其他 benchmark 的题目按 deepSWE 规则判重。

共享题面库是题包创建的前置门槛。候选完成全量读取、语义去重和改名测试后，必须把结论写回本表并读回核对；只有读回值为`不重复`时，才允许创建正式题包、生成 Trae 工作空间或启动后续 verifier。`疑似重复`、`重复`、写入失败、读回不一致、权限异常和多条候选记录都必须停止在去重阶段。不能先生成正式包或 Trae 工作空间，再用本地 review 文件补写题面表。

使用飞书 CLI 前，先确认当前用户身份已授权并验证成功；所有请求都带 `--as user`。共享表的坐标必须从上面的链接解析，不要复用题目交付 Base 的 token 或配置：

```bash
set -e
OBM_SCENE_BASE_URL='https://jcnyoyfbeyxi.feishu.cn/base/NqtYbxHF1aEYrNsyJSRcUFvMnbe?table=tblk47ilQNyL7Aim&view=vewF5fmGFr'
OBM_LARK_CLI="${OBM_LARK_CLI:-$(command -v lark-cli || true)}"
if [ -z "$OBM_LARK_CLI" ]; then
  printf '%s\n' 'lark-cli is unavailable; stop before deciding the candidate is distinct.' >&2
  exit 1
fi

OBM_SCENE_AUTH_JSON="$("$OBM_LARK_CLI" auth status --json --verify)"
printf '%s\n' "$OBM_SCENE_AUTH_JSON" | jq -e '.identity == "user" and .verified == true' >/dev/null

OBM_SCENE_RESOLVE_JSON="$("$OBM_LARK_CLI" base +url-resolve --url "$OBM_SCENE_BASE_URL" --as user)"
OBM_SCENE_BASE_TOKEN="$(printf '%s\n' "$OBM_SCENE_RESOLVE_JSON" | jq -er '.data.base_token')"
OBM_SCENE_TABLE_ID="$(printf '%s\n' "$OBM_SCENE_RESOLVE_JSON" | jq -er '.data.table_id')"
test "$OBM_SCENE_TABLE_ID" = 'tblk47ilQNyL7Aim'
test "$(printf '%s\n' "$OBM_SCENE_RESOLVE_JSON" | jq -er '.data.view_id')" = 'vewF5fmGFr'

"$OBM_LARK_CLI" base +field-list \
  --base-token "$OBM_SCENE_BASE_TOKEN" \
  --table-id "$OBM_SCENE_TABLE_ID" \
  --as user
"$OBM_LARK_CLI" base +record-list \
  --base-token "$OBM_SCENE_BASE_TOKEN" \
  --table-id "$OBM_SCENE_TABLE_ID" \
  --as user --format json --limit 200 --offset 0
```

确认真实字段仍为：`题目编号`、`题面`、`核心场景`、`对比题面`、`去重判断`、`判断依据`。`去重判断`必须是单选字段，选项为`不重复`、`疑似重复`和`重复`。读记录时不指定视图，避免视图筛选遗漏；返回 `has_more=true` 时继续增加 `--offset`，直到读完。

人工结论确定后，无论结果是 `distinct`、`high-risk` 还是 `duplicate`，都要把这次候选的公开题面和判断写回表中。字段映射如下：

- `题目编号`：已有正式或候选预留号时填写登记表中的原号，例如 `2026-09-25-12`。没有预留号的历史记录或临时候选留空，不能自行编造编号。
- `题面`：简要、完整地描述候选要解决的外部问题和成功条件。
- `核心场景`：概括参与者、工作流、状态变化与失败恢复。
- `对比题面`：列出最相近记录的题面或简明场景摘要，保留可查的正式题号。
- `去重判断`：`distinct` 写`不重复`，`high-risk` 写`疑似重复`，`duplicate` 写`重复`。
- `判断依据`：写明相同点、实质差异、改名测试结果和结论理由。

写入前先在已读记录中按正式题号查找；未编号候选则按题面查找。恰好存在一条对应记录时更新该行，避免重复创建；找不到时才新增；发现多条可能对应项时先停止并核实。候选加难或同题返修时更新同一题号的当前场景与结论，不另建一行伪装成新题。写入后读回记录，检查题号、五项判重内容和单选值。只写上述六个字段，不写参考答案、隐藏测试、私有 verifier 细节或实现路线。若 CLI、授权、Base 权限或字段校验失败，停止共享表判重并报告，不得把无法读取表格当作“没有相似题”。

写入和读回完成后，保存记录 ID、读回时间和`不重复`证据到内部 review；这些证据是后续创建题包目录和 Trae 工作空间的前置条件。返修若改变场景目标、状态模型、失败恢复或 verifier 行为，更新同一题号的记录并重新读回确认，不得另建记录绕过门槛。

新增行和更新行都使用 `--as user`，字段名以刚才读取的真实字段为准：

```bash
"$OBM_LARK_CLI" base +record-batch-create \
  --base-token "$OBM_SCENE_BASE_TOKEN" \
  --table-id "$OBM_SCENE_TABLE_ID" \
  --as user \
  --json '{"create_records":[{"题目编号":"2026-09-25-12","题面":"候选的外部需求","核心场景":"参与者、工作流和状态","对比题面":"最接近的历史题面","去重判断":"不重复","判断依据":"相同点、实质差异和结论理由"}]}'

"$OBM_LARK_CLI" base +record-batch-update \
  --base-token "$OBM_SCENE_BASE_TOKEN" \
  --table-id "$OBM_SCENE_TABLE_ID" \
  --as user \
  --json '{"update_records":{"rec_xxx":{"题目编号":"2026-09-25-12","题面":"候选的外部需求","核心场景":"参与者、工作流和状态","对比题面":"最接近的历史题面","去重判断":"疑似重复","判断依据":"相同点、实质差异和结论理由"}}}'
```

## 去重记录

把记录保存在内部工作区，例如 `work/<candidate-or-task-id>/scene-overlap-review.md`。正式包不包含该文件，除非当前 OBM 规范明确要求。记录至少包含：

```text
候选题：
候选档案散列：
检查日期：
检查语料：benchmark 题目数量、项目 proposal 数量
登记表活动候选数量：

最相近已有题 | 相同点 | 实质差异 | 改名测试结果 | 判断

同仓库题复核：
同能力族题复核：
自动召回的限制：
最终结论：distinct / high-risk / duplicate
结论依据：
```

候选题的目标、工作流、状态模型、失败恢复或 verifier 行为在复核后发生实质变化，原结论失效，必须重新生成档案并复核。
