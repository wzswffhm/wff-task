# `wfflab__wtask-216` 交付就绪度

> 本题为 2026-10-04 新建的 Windows 专项 Coding Bench 题包，用于验证
> 「显式权威规格能否让 Opus 5 在对 Qwen3.8-Max-0902 的区分度上胜出」这一假设。
> 结论：**不能**（双方各 3 轮均满分），8.2 判定 FAIL，根因见 `DIAGNOSIS.md`。

## 1. 题目概要

| 项 | 值 |
|---|---|
| task_id | `wfflab__wtask-216` |
| 题目 | Windows 计划任务（Task Scheduler）调度语义引擎 |
| 一级方向 | 系统管理 |
| 二级标签 | 计划任务 XML 模式；4 类调度（日/周/月/月内某周某星期）；重复与持续期；ISO-8601 时长规范化；EndBoundary/停止条件；结构化错误分类 |
| task_type | bugfix（注入 10 个缺陷） |
| 被测包 | 纯 Python，5 个模块（`errors` / `duration` / `model` / `schedule` / `xmlio`） |
| required | F2P 10 + P2P 6 = 16 |
| task_version | 1.0.0 |
| task_hash | `1df288d74ff9377dbe510b691672b8b60ef9f6e762c52566a206041c5fa24a4f` |
| base_commit | `6ffc84b998d0e0fac0ed0d3c23e6454c32183d58` |

**设计要点**：`docs/TASKSCHEMA.md` 是**权威显式规格**（9 章，覆盖结构 / 触发器 / 4 类调度 /
出现时刻 / 重复 / 时长 / 规范化序列化 / 查询 API / 错误模型）。项目刻意不设「发现税」——
被测模型无需逆向格式，可把预算全部用于实现与验证，从而把区分度交给**实现正确性**而非预算。

## 2. 五件套

| 组件 | 路径 | 状态 |
|---|---|---|
| instruction.md | `instruction.md` | ✅ 1977 字符，10 条症状式描述 + 验收标准指针，不泄解法 |
| task.toml | `task.toml` | ✅ schema 1.3，含身份三元组与 verification_evidence |
| environment/ | `environment/`（Dockerfile + workspace） | ✅ 工作区含 `wtask/` 参考实现、可见冒烟测试、`docs/TASKSCHEMA.md` |
| solution/ | `solution/oracle.patch` | ✅ 3 文件补丁，独立可施加 |
| tests/ | `tests/`（grade.py + test.ps1 + test_patch.diff + swelive_spec.json） | ✅ 二值判分，F2P/P2P 分组 |
| 平台配置 | `platform_import.json` | ✅ |
| 伴随材料 | `extras/metadata/manifest.json` | ✅（批次级 delivery-extras 在 `../_index/`） |

## 3. 证据

| 检查 | 结果 |
|---|---|
| no-change ×3 | **0.0 / 0.0 / 0.0**（全部 VALID，P2P 全过、核心 F2P 全失败） |
| Golden ×3 | **1.0 / 1.0 / 1.0**（全部 VALID，16/16，无 SKIP/MISSING/ERROR） |
| Qwen3.8-Max-0902 ×3 | 1.0 / 1.0 / 1.0（各 16/16） |
| Opus 5 ×3 | 1.0 / 1.0 / 1.0（各 16/16） |
| GLM-5.3 ×1 | 1.0（16/16） |
| Kimi K3 ×1 | 1.0（16/16） |
| `validate_package.py` | PASS=393 / FAIL=1（仅缺 delivery-extras，规范 5.1 的伴随材料在本仓位于 `_index/`）/ FLAG=1 |

## 4. 唯一未过项

**规范 8.2 区分度：FAIL（Opus 3.0 vs Qwen 3.0 → 同分且非 0）。**

两个准入条件均不成立：

```
条件 1：Opus5.model_score_sum > Qwen.model_score_sum   → 3.0 > 3.0  ✗
条件 2：两者 == 0 且 Opus pass_sum > Qwen pass_sum      → 双方 48 == 48 ✗
```

按 K17 口径属**难度不足（薄题）**；但本次已定量证明「加大难度」在本端点配置下方向相反
（见 `DIAGNOSIS.md` §1.3、§2.2）。故本题与全批其余 15 题一样，**卡在 Opus 5 端点**。
端点修复后可直接复用，无需重新出题。
