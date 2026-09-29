# 第 1 次实验（agent-runs）终态诊断：基础设施错误，非能力缺口

终态：`needs_skill_revision`（child_returncode=21）
- no-skill：47 轮，verifier reward=0
- with-skill：72 轮，verifier reward=0

## 判定：两侧 reward 均为「假 0」，无效证据

两个 `VERIFIER_RUN.log` 都出现：
```
PATCH_PREPARE=failed: error: patch failed: casbin/__init__.py:26
ERROR: Agent model.patch could not be applied
```
补丁未应用 → 全部 F2P 记 missing → reward=0。verifier 从未真正评测过两侧的实现。

## 根因（已实证）

`run_seed_agent.py::write_patch()` 用 `Path.write_text(result.stdout, encoding="utf-8")` 落盘补丁。
Windows 文本模式默认把 `\n` 翻译成 `\r\n`，导致两侧 `model.patch` 全部行尾为 CRLF
（no-skill 493/493 行、with-skill 528/528 行）。容器内 `/app` 为 LF 树且无
autocrlf，`git apply` 在第一个 hunk 即失败。Linux（官方训练平台）无此翻译，
故该缺陷在原环境不可见，属 Windows 运行时的基础设施错误。

## 修复（已验证）

1. `run_seed_agent.py::write_patch`：`write_text(..., newline="")`，保留 git 原始字节。
2. `grader.py::prepare_app`：应用前对补丁做 CRLF→LF 归一（内容不变，双保险）。
3. E2E 回归：CRLF 版 `solution-crlf.patch` 挂载后 `PATCH_PREPARE=ok`、`REWARD=1`。

## 处置

按规范「基础设施错误修复后使用新目录重试」：题目、题面、upstream、verifier（grader 变更）
均有改动 → 两侧全部重跑，第 1 次运行目录保留作证据。无 skill 返修依据（失败与 skill 无关）。
