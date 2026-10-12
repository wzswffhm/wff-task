# 裁定说明：opus-5 / run-1 —— INVALID 补判为 0.0

- 日期：2026-10-03
- 任务：`wfflab__wfmt-215`（task_hash `9417c1df37a03efaa4d8314648bc4efbe47eb39bc0a2fe71fbe2f78e2fad2f95`）
- 原始判分：`INVALID — prepared_environment_missing`
- 补判结论：**score = 0.0**（真实模型失败，非基础设施故障）

## 1 现象

判分链路在执行 `python -c "import pytest, wfmt"` 时崩溃（0.39s），
`report.json` 记为 `INVALID`，`score_note` 写明「不得记为 0 分」。

## 2 根因（模型自身产物所致）

该 run 的 `patch.diff` 在**仓库根目录**新增了 9 个探查脚本：

```
analyze.py  check_lengths.py  debug_test.py  decode_all.py  inspect.py
parse_records.py  test_alignment.py  test_mixed.py  test_u8.py
```

其中 `inspect.py` **遮蔽了标准库 `inspect`**：判分沙箱把工作区根目录放进
`sys.path`（`PYTHONPATH=<testbed>`），因此 `import inspect` 解析到该脚本而非
标准库，`pytest` 的导入链随即失败。

实测证据：

```
$ PYTHONPATH=<judge_sandbox> python -c "import inspect; print(inspect.__file__)"
Byte-by-byte inspection around position 15-35:   # ← 这是该脚本自己的输出
 14: 0x68 = 104  'h'
 ...
```

## 3 为什么这不是「不得记 0」的范畴

规范中「INVALID 不得伪装 0 分」针对的是**判分基础设施自身故障**（环境缺失、
产物缺失、限流等），此时分数不可信，必须修因重判。本 run 的基础设施完好，
故障由**被测模型自己的提交**引入——它在工作区根目录创建了遮蔽标准库的文件。
该提交在被测环境里同样无法通过 `test.ps1` 的 pytest 阶段。

## 4 补判依据（可复现）

1. `patch.diff` 只含根目录脚本，**不含任何 `wfmt/` 条目**；
2. `diff -rq <judge_sandbox>/wfmt <base_workspace>/wfmt` → **完全一致**，
   即被测包 = base，未做任何修改；
3. 剔除根目录遮蔽脚本后重跑隐藏测试：
   `8 failed, 7 passed` —— 与 base 的失败集**完全相同**（F2P 8 条全红）。

因此该提交在任何解释下都得 0：F2P 无一通过。

## 5 记录

`opus-5/run-1` 计 **0.0**；本轮 Opus 必须在其后两轮取得 3/3 中的满分，
使 `sum(Opus)=3 > sum(Qwen)=2` 方能满足 8.2。
