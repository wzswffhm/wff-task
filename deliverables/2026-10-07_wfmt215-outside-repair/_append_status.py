import pathlib

p = pathlib.Path(
    r"C:\Users\Administrator\Desktop\wff-task\deliverables"
    r"\2026-10-07_wfmt215-outside-repair\ROUND_WFMT_STATUS.md"
)
text = """
---

## 16:40 更新 — runner 参数化修复完成，215 重新起跑

- **结论**：旧 QWEN 探针（tag `wfq`）**结构性无效，已作废**。根因是 runner 把 217 的
  `WReparse` 写白名单与 PowerShell 人设写死在代码里，agent 根本改不了 `wfmt/`。
  详见 `WFMT_RUNNER_PARAM.md`。
- **修复**：runner 现从 `task.toml` 推导模块 / 参考文档 / 语言人设 / 样本目录；
  `read_file` 支持二进制 hex dump；`run_id` 加随机后缀以支持并行分片。217 行为零变化。
- **当前**：3 个并行分片 `oh-wfq1/2/3` 于 **16:37:43** 起跑（各 `QWEN ×1`，`--keep-work`），
  容器 `oh-…-f61d` / `-17c7` / `-2d61` 均 Up。
- **已清理**：旧废轮（无 `result.json`）已删；全部遗留 `oh-r*` 计划任务已 `Disabled`。
- **下一步**：三个 `matrix-wfqN.done` 齐 → `summarize_model_runs.py --after 2026-10-07T06:12:40+00:00
  --control-runs 3` → 看 `models.QWEN.score_sum`（≤2 则接 OPUS×3 期望 3>2）。
"""
with p.open("a", encoding="utf-8") as fh:
    fh.write(text)
print("appended", len(text), "chars ->", p.name)
