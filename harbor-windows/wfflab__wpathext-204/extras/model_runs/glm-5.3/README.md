# GLM-5.3 —— 待平台 harness 执行

本目录用于存放 **GLM-5.3** 在题目 `wfflab__wpathext-204` 上的运行记录。当前状态：**未执行**。

## 为什么这里还是空的

按规范第七、八章的分工边界，模型调用层（`scripts/run_model_validation.py`）
只负责发起调用、保存轨迹与补丁、区分 VALID/INVALID；
**正式分数必须由平台 harness（`test.ps1` + `grade.py`）在真实 Windows Runtime 中执行后回填**。
按出题方要求「先不跑模型校验」，因此尚未产生运行记录。

## 应执行的次数

| 模型 | 计划次数 | 角色 |
|---|---|---|
| Qwen3.8-Max-0902 | 3 | primary（难度区分度） |
| Opus 5 | 3 | primary（难度区分度） |
| GLM-5.3 | 1 | auxiliary（可运行性） |
| Kimi K3 | 1 | auxiliary（可运行性） |

本题为 **GLM-5.3**：计划 1 次，角色 auxiliary。

## 运行后每目录应包含

`meta.json` / `response.md` / `patch.diff` / `per_testcase.json` / `report.json` / `badcase_attribution.md`。

## 区分度准入

```
条件 1: Opus5.model_score_sum > Qwen3.8-Max-0902.model_score_sum
条件 2: 两者 model_score_sum == 0 且 Opus5.testcase_pass_sum > Qwen3.8-Max-0902.testcase_pass_sum
```
