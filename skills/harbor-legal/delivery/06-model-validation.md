# 三模型难度验证（G5）

## 1. 口径（冻结，不得自行替换）

| 项 | 值 |
|---|---|
| 运行框架 | **Claude code** |
| 待测模型 | `gpt-5.6-sol`、`claude-opus-4-8`、`qwen3.8-max0902` |
| 裁判模型 | **`qwen3.7-plus`** |
| 分数归一化 | 所有题目满分归一化为 **1.0** |
| 次数 | **每种模型跑 1 次**，取三模型平均分 |
| 通过标准 | 三模型平均分 **< 0.7**，**且至少有一个模型有得分**（避免全 0 的"死题"） |
| 交附件 | **模型产物 + 跑分轨迹须随题提交**，用于验证难度要求 |

## 2. 难度等级区间（达标后归档）

| 等级 | 平均分区间 | 产量占比 |
|---|---|---|
| A1 基础/易 | 0.6 ≤ 得分 < 0.7 | 20% |
| A2 进阶/中 | 0.5 ≤ 得分 < 0.6 | 60% |
| A3 高难/难 | 得分 < 0.5 | 20% |

> 参考答案得分 **> 0.85** **且** 三模型平均分 **< 0.7**。

## 3. 执行流程

```
1) 冻结口径（模型标识、框架版本、judge 版本、采样参数、timeout）
2) 逐题执行：三模型 × 1 次，各自产出交付物
3) 对每份产物跑判分：rewardkit（claude-code agent judge，裁判 qwen3.7-plus）
4) 逐题计算三模型平均分；同时记录每模型是否 >0
5) 与目标等级区间比对；核对"至少一个模型得分"
6) 归档跑分产物与轨迹
```

### 执行要点

- **评分行为随 claude-code CLI 版本漂移** → 必须锁 `2.1.114`；版本或平台变更后**不得与旧结果直接比较**，需要用于准入时应**统一回刷**。
- **`verifier_error = 1` 的运行不是"0 分"**，而是"评分不可信"，必须重跑；不得纳入难度统计。
- 难度未达标 → **重做题目或调整定级后重跑**，**不得伪装跑分**。

## 4. 归档要求

每题留存：

```
<题包>/model_runs/
├── gpt-5.6-sol/     { deliverables/, trace/, reward.json, reward-details.json }
├── claude-opus-4-8/ { … }
└── qwen3.8-max0902/ { … }

<题包>/model_runs/summary.json
```

`summary.json` 建议结构：

```json
{
  "task_id": "FIN1-SKL-DEP-001",
  "frozen": {
    "framework": "claude-code",
    "framework_version": "2.1.114",
    "rewardkit_version": "0.1.7",
    "judge_model": "qwen3.7-plus",
    "sample_params": {"temperature": null, "note": "以平台冻结值为准"}
  },
  "runs": [
    {"model": "gpt-5.6-sol",        "reward": 0.42, "verifier_error": 0, "scored": true},
    {"model": "claude-opus-4-8",    "reward": 0.61, "verifier_error": 0, "scored": true},
    {"model": "qwen3.8-max0902",    "reward": 0.33, "verifier_error": 0, "scored": true}
  ],
  "mean": 0.453,
  "any_model_scored": true,
  "declared_difficulty": "A3",
  "gate_pass": true
}
```

## 5. 结果自查脚本

用于跑分完成后机械核验门槛（不代跑模型，只校验汇总结果）：

```python
# check_model_gates.py — 用法: python3 check_model_gates.py summary.json
import json, sys

BANDS = {"A1": (0.60, 0.70), "A2": (0.50, 0.60), "A3": (0.0, 0.50)}

def main(path):
    s = json.load(open(path, encoding="utf-8"))
    runs = [r for r in s["runs"] if r.get("verifier_error", 1) == 0]
    bad = [r["model"] for r in s["runs"] if r.get("verifier_error", 1) != 0]
    if bad:
        print(f"[FAIL] 存在评分不可信(verifier_error=1)的运行，必须重跑: {bad}")
    if not runs:
        print("[FAIL] 无有效运行");  return 1
    mean = sum(r["reward"] for r in runs) / len(runs)
    any_scored = any(r["reward"] > 0 for r in runs)
    lo, hi = BANDS[s["declared_difficulty"]]
    ok_mean = mean < 0.70
    ok_band = lo <= mean < hi
    print(f"三模型均分 = {mean:.3f}  (有效运行 {len(runs)} 次)")
    print(f"至少一个模型有得分: {any_scored}")
    print(f"难度门槛(<0.7): {'PASS' if ok_mean else 'FAIL'}")
    print(f"等级区间 {s['declared_difficulty']} ∈ [{lo},{hi}): {'PASS' if ok_band else 'FAIL'}")
    return 0 if (ok_mean and ok_band and any_scored and not bad) else 1

if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
```

## 6. 与参考答案预检的关系（两道独立的门）

| 门 | 对象 | 标准 | 失败含义 |
|---|---|---|---|
| **golden 预检（G4）** | 参考答案产物 | 主分 **> 0.85** 且 `verifier_error = 0` | **Rubric 写歪**（要求过高/锚点错误/golden 不完整）→ 整题退回重写 |
| **三模型验证（G5）** | 三模型产物 | 均分 **< 0.7** 且至少一个模型有得分 | **难度不达标或过难成死题** → 重做题目或调级重跑 |

两者必须**都过**才可提交。golden 过高而模型也高 → 题目太简单；golden 达标而三模型全 0 → 死题，需降低门槛或补充可得分项。
