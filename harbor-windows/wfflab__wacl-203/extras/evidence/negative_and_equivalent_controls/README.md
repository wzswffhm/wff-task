# negative_and_equivalent_controls —— wfflab__wacl-203

**状态：本轮未执行（按出题方要求「先不跑测试」）。**

证明只修部分缺陷拿不到分、而不同实现路径的正确解仍得 1 分。

## 本目录在平台执行阶段应包含

- negative_* 与 equivalent_* 若干变体
- 每次运行至少包含：`pytest-stdout.txt`、`pytest-results.json`、`test.log`、`grade-stdout.txt`、`summary.json`，以及 `verifier/` 下的 `report.json` / `reward.txt` / `reward.json` / `reward-details.json`。

## 为什么当前为空

本题只完成题目构造（base repo、隐藏测试、参考解、交付结构）与静态结构校验，
未在真实 Windows Runtime 中执行 `test.ps1` + `grade.py`。
补齐方式见 `_index/known_issues.md`。
