# cleanup_and_restore —— wfflab__wacl-203

**状态：本轮未执行（按出题方要求「先不跑测试」）。**

证明题目不残留系统级副作用。

## 本目录在平台执行阶段应包含

- 清理记录与恢复方式说明
- 每次运行至少包含：`pytest-stdout.txt`、`pytest-results.json`、`test.log`、`grade-stdout.txt`、`summary.json`，以及 `verifier/` 下的 `report.json` / `reward.txt` / `reward.json` / `reward-details.json`。

## 为什么当前为空

本题只完成题目构造（base repo、隐藏测试、参考解、交付结构）与静态结构校验，
未在真实 Windows Runtime 中执行 `test.ps1` + `grade.py`。
补齐方式见 `_index/known_issues.md`。
