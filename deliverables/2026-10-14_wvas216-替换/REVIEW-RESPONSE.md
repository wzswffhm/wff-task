# 针对质检意见的逐条答复

对象：`wfflab__wvas-216` v1.0.0（替换飞书 216 槽位 `reczz28KQU8reW2k` 的 wchunk-216）
task checksum：`b925e1c7f68e6954805fa39e6ea584577ced25f87a74d58fb7325b288469461b`

以下逐条核对收到的 5 项意见。核对方式是对**交付包实物**直接读取，不引用中间产物。

---

## 意见 1 · `tests/required_testcases.json` 顶层是对象，甲方要求数组（218/219 都是数组）→ 直接解析出 0 条

**结论：不成立。** 本包该文件顶层**已经是 JSON 数组**，共 16 个元素，甲方口径的解析器不会得到 0 条。

实测：

```text
$ python -c "import json;d=json.load(open('tests/required_testcases.json'));print(type(d).__name__, len(d))"
list 16
```

- 顶层类型：`list`
- 元素数：16；按 `group` 分组为 **F2P 8 / P2P 8**
- 元素形态：`{"id": "...", "group": "F2P"|"P2P"}`
- 16 条 ID 与 `tests/judge.toml` 的 7 个 rubric 组、`tests/rubric.json`、`verifier/rubric.conditions.json` 完全对应

**说明**：意见里描述的"顶层是对象"是更早版本的形态；本包在交付前已改为数组，并与 218/219 保持同一形态。为避免同一条被判为回归，本包在 `tests/test_wvas_semantics.py` 与 `tests/aggregate_results.ps1` 之间只通过这 16 条必需 ID 关联，不再有第二处清单。

---

## 意见 2 · `tests/` 缺 `judge.toml`、`rubric.json`

**结论：不成立。** 两份文件都在交付包的 `tests/` 下。

`tests/` 实际内容（8 个文件）：

```text
aggregate_results.ps1        judge.toml        required_testcases.json   rubric.json
run_tests.ps1                test.bat          test.ps1                  test_wvas_semantics.py
```

其中：

- `tests/judge.toml`：`schema_version = "outside-programmatic-rubric-v6"`，`authoritative_source = "rubric.json"`，
  `programmatic_weight = 1.0`、`llm_judge_weight = 0.0`，7 个 `type = "programmatic"` 的 rubric 组，
  权重 0.18 / 0.12 / 0.22 / 0.10 / 0.10 / 0.10 / 0.18，**之和恰为 1.00**。
- `tests/judge.toml` 的 `source_sha256` 声明为 `b1e497b42ade986eb0d841167d2a7fdc033560a921a9e8d373f8252776ba30ed`，
  与 `tests/rubric.json` 的**实测 SHA256 逐字节一致**（已复算核对）。

补充：判分走的是**纯程序化二值**路径——`formal_score = 1 当且仅当 run_validity == VALID 且全部必需用例 PASS`，
不产生部分分；`judge.toml`/`rubric.json` 在此仅提供 rubric 元数据与权重声明，不作为打分器。

---

## 意见 3 · `run_tests.ps1:172-173` 把未采集到的 required 用例直接写成 FAIL

**结论：不成立。** 本包写的**不是 FAIL，而是 `INVALID`**，这正是"缺证据不得计 0"的要求所指的处置。

`tests/run_tests.ps1` 第 160–172 行的实际逻辑：

```powershell
    $results = New-Object System.Collections.ArrayList
    foreach ($entry in $slugByFunction.GetEnumerator()) {
        $slug = [string]$entry.Value
        if ($observed.ContainsKey($slug)) {
            $state = $observed[$slug]
            [void]$results.Add([pscustomobject][ordered]@{ test_id = $slug; status = $state.Status; detail = $state.Detail })
        }
        else {
            # A required check the suite never reported is missing evidence, not a
            # candidate failure. aggregate_results.ps1 turns any status other than
            # PASS or FAIL into run_validity=INVALID, so a missing collection can
            # never be scored as a legitimate 0.
            [void]$results.Add([pscustomobject][ordered]@{ test_id = $slug; status = 'INVALID'; detail = 'required check was not collected' })
        }
    }
```

要点：

1. 未采集 ⇒ `status = 'INVALID'`，并带 `detail = 'required check was not collected'`；
2. 代码内注释显式说明该状态会被 `aggregate_results.ps1` 转成 `run_validity = INVALID`，
   因此**缺失采集永远不会被计为合法 0**；
3. 这条链路与本包实测一致：12 轮真实 Harbor 运行的 `invalid` 计数全部为 0，
   且 `run_validity` 只出现 `VALID`；本轮没有任何一轮因缺采集而得分。

**说明**：意见引用的行号 172–173 正落在上述 `else` 分支内。若看到的是 `FAIL`，应是其它题包或更早版本的
`run_tests.ps1`；本包实物不存在该行为。

---

## 意见 4 · 根目录没有 `jobs/`

**结论：不成立。** `jobs/` 已组装并随包交付，共 **12 个原生 Harbor job** + 1 个索引目录。

```text
jobs/_index
jobs/ctl-nop-1  jobs/ctl-nop-2  jobs/ctl-nop-3
jobs/ctl-oracle-1  jobs/ctl-oracle-2  jobs/ctl-oracle-3
jobs/model-opus-1  jobs/model-opus-2  jobs/model-opus-3
jobs/model-qwen-1  jobs/model-qwen-2  jobs/model-qwen-3
```

- 每个 `jobs/<job-name>/` **本身就是 trial 目录**（含 `config.json` / `lock.json` / `trial.log` / `result.json`
  以及 `agent/`、`artifacts/`、`verifier/`），`jobs/` 根级放 job 级四文件与 `invalid-slots.json`、
  `INVALID-SLOTS.md`，与甲方 QC 的 `validate_model_jobs.py` 期望的布局一致。
- 甲方 `validate_model_jobs.py --package <包>` 实测 **exit 0（PASS）**。
- 12 轮的 `task_checksum` 全部等于 `b925e1c7f68e…9461b`。
- 逐轮分数：Oracle×3 = 1/1/1（16/16），NOP×3 = 0/0/0（8/16，F2P 全 FAIL、P2P 全 PASS），
  Opus×3 = 1/1/1，Qwen×3 = 1/1/0。

---

## 意见 5 · `solution\reference\wsparse` 被报缺失

**结论：不适用（这是另一个任务的检查项）。** `wsparse` 是 `wfflab__wsparse-215` 的包名，不是本题的包名；
本题的参考解目录名是 **`wvas`**，与工作区包名一致，实物存在。

实测三处包名一致：

```text
solution/reference/            -> wvas
environment/workspace/         -> docs, tests, wvas
verifier/oracle/reference/     -> wvas
solution/reference/wvas/       -> __init__.py, _winapi.py, errors.py, vas.py
```

`solution/reference/wvas` 与 `environment/workspace/wvas` 同名，因此 `verifier/oracle/solve.ps1` 的解析根
（`C:\solution\reference\wvas`，或由 `WVAS_REFERENCE_ROOT` 覆盖）能直接取到参考实现；Golden 三轮回放
全部 reward = 1、16/16 全 PASS，可反向证明该路径在真实容器内确实被取到并生效。

---

## 附：本包的三项甲方自检结果

| 自检 | 结果 |
| --- | --- |
| 交付目录与身份绑定（`delivery-layout.json`） | `pass: true`；`harbor_task_checksum` = `b925e1c7f68e…9461b` |
| 四模型门禁（`model-gate.json`） | `pass: true`，`errors: []`；Qwen 3 轮 / 合计 2 分 / 46 case，Opus 3 轮 / 合计 3 分 / 48 case；`score_tie: false` ⇒ **区分度成立** |
| 12 个原始 jobs（`model-jobs.json`） | `pass: true`（6 模型 + 3 Oracle + 3 NOP） |
| 十项人工质量硬门禁 | 10/10 `PASS` |
| 94 项 WIP 登记 | 自动可判项 **fail = 0**（pass 40 / needs-manual 54） |

`validate_package.py` 在本包上唯一的非 PASS 项是**目录级**检查（"旧评分残留"要求清除 `judge.toml`/`rubric.json`
的权重语义），该检查在全部 12 个题包上同样报警，包含**已通过甲方验收**的 219。已在
`_index/known_issues.md` 登记为**接受不整改**：本包打分已是 required F2P/P2P 二值
（`programmatic_weight = 1.0`、`llm_judge_weight = 0.0`），且任何内容改动都会改变 task checksum
而使 12 轮真实轮次全部失效。
