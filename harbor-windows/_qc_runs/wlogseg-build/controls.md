# wfflab__wlogseg-218 本地对照记录

构建期材料，不属于交付物。
题包：`harbor-windows/wfflab__wlogseg-218-v1.0.0-delivery/`（66 文件 / 51.96 MiB，不含 `jobs/`）。
`218` 与 `wlogseg` 为占位名，待甲方确认后批量改名。

环境：Windows PowerShell 5.1 + 本地 bundled Python 3.12；隐藏套件经
`WLOGSEG_VERIFIER_ROOT` 注入；pytest 8.3.5 + pytest-json-report 1.5.0 离线装在 `pylibs/`。
本记录不涉及 Docker 与真实 Harbor 容器。

## 一、评分链六组对照

| # | 对照 | 载荷 | 期望 | 实测 |
|---|---|---|---|---|
| A | 可见冒烟测试 | 缺陷版工作区 | 全绿 | 6 passed |
| A' | 可见冒烟测试 | 参考解 | 全绿 | 6 passed |
| B | no-change（本地分支） | 缺陷版 | score=0 / exit 1 | 8 passed / 17 failed，score=0，exit 1 |
| C | Golden（本地分支） | 参考解 | score=1 / exit 0 | 25 passed / 0 failed，score=1，exit 0 |
| H1 | Golden（Harbor 分支，`C:\logs` 存在） | 参考解 | `===SWELIVE_GRADE score=1===` / exit 0 | 一致；`C:\logs\verifier\` 恰好 1 个 `report.json` + reward 三件套 |
| H2 | no-change（Harbor 分支） | 缺陷版 | `===SWELIVE_GRADE score=0===` / exit 1 | 一致 |

B/C 的 `run_validity` 均为 `VALID`；`rubric_split` = 0.5 programmatic + 0.5 llm_judge。
Harbor 分支的 report 数约束（恰好一个）已实测满足。

## 二、针对性反例（关键证据）

把参考解**只退化两处**，其余全部保留：

1. 全局把 `"truncated"` 改回 `"structure"`（等价于「不会区分数据不足与结构矛盾」）；
2. `iter_segments` 改回 `handle.read()` 整体读取。

结果：

```
checks: 20 passed, 5 failed, 25 total
aggregate: score=0 weighted=0.34 (Unsatisfied rubric items: error-classification, streaming)
```

失败的 5 条恰好全是 qwen 的恒定弱项：

- `f2p-truncated-header-reports-truncated`
- `f2p-missing-index-reports-truncated`
- `f2p-truncated-segment-body-reports-truncated`
- `f2p-truncated-stream-reports-truncated`
- `f2p-iter-segments-is-streaming`

即：对齐、索引布局、CRC、样本往返、**以及全部 4 条结构矛盾检查**都已修好（其余 19 条 PASS），
加权分只有 0.34，`formal_score` 仍为 **0**。这证明本题的正负分界确实压在这条弱项线上，
不是由容易修复的部分决定。

对照证据：`wchunk-216` 的 qwen 在 3/3 轮全部栽在 `truncated-container-*-truncated`，
`wfmt-215` 的 qwen 在 3/3 轮同样包含该项；两个题包的 opus 各 3/3 通过。

## 三、题包静态校验

`skills/harbor-windows/scripts/validate_package.py --package <题包>`：

| 项 | 结果 |
|---|---|
| 题面泄漏 | PASS（未命中已知泄漏信号） |
| 环境泄漏 | PASS（`environment/` 无 Solution/答案/隐藏用例） |
| INVALID 判定 | PASS（具备 INVALID 判定能力） |
| 分值拆分 | PASS（存在二值 / 部分分拆分） |
| 结构、task.toml 必需段 | PASS |
| `[FAIL] 判分分离 tests/ 内含 judge.toml` | 与 216、215 **完全同源**（两包同为该 FAIL） |
| `[FAIL] 判分分离 tests/ 内含 rubric.json` | 同上 |
| `[FLAG] task.toml 缺少 storage`、`[FLAG] 未找到 swelive_spec.json` | 与 216、215 同源 |

新增题包未引入任何 216 / 215 之外的校验问题。

## 四、构建脚本

| 脚本 | 用途 |
|---|---|
| `build_samples.py` | 用参考解生成两个样本并自检全部参考分支 |
| `verify_candidate.py` | 把任一候选实现放进隐藏套件逐项跑 |
| `counterexample-partial/` | 第二节那条反例的实现（`truncated` 已折叠为 `structure`、流式已退化为整体读取） |

## 五、执行进度

**已完成（2026-10-12）**：

- 8 轮模型验证 —— Qwen3.8-Max-0902 ×3、**Opus 5 ×3（`4router.net`）**、GLM-5.3 ×1、Kimi K3 ×1，
  全部 VALID；补丁经本机真实 Windows Runtime 判分回填，区分度**准入 PASS（条件 2：双 0 分
  场景下 Opus `testcase_pass_sum=70` > Qwen `33`）**。
- 六轮控制对照（golden ×3 = 1、no-change ×3 = 0）重跑通过：`_qc_runs/wlogseg-build/controls-218/`。
- `jobs/` 已按 `harbor-independent-jobs-archive-v1`（archive-only）落盘 14 轮
  （8 模型 + 6 控制），并如实声明无容器产物。
- 交付包已打出并自检 PASS：`deliverables/2026-10-12_wlogseg218-交付/package/wfflab__wlogseg-218-v1.0.0-delivery.zip`
  （sha256 `9a3970d8…5e4c`）。
- 飞书已回写：新建记录 `reczz28MRVnWkD2v`（标注员 `wff`，三附件读回校验通过，**状态字段未写入、
  未改动**，保持飞书新建行默认的「待提交」）。

**尚未执行**：

- Docker 内构建与真实 Windows Harbor 容器的动态门禁（218 全部证据来自宿主 Windows Runtime）；
- `harbor-windows/_index` 登记；
- git 提交（按约定只在用户明确要求时执行）。
