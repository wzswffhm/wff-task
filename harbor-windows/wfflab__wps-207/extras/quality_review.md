# quality_review —— wfflab__wps-207

质检日期：2026-10-01　｜　题包版本：1.0　｜　质检结论：**FLAG**

> 结论含义：题包本体（结构、题面、判分逻辑、身份一致性）已通过静态检查；
> 但**对照验证与多模型运行本轮均未执行**（出题方明确要求），因此暂不能申报最终验收。

## 一、已完成并通过的检查

| 检查项 | 结论 | 依据 |
|---|---|---|
| Windows 价值反事实判定 | PASS | `metadata/labels.json` windows_mechanism；根因只在 Windows 语义下成立 |
| 标准 Harbor 五件套 | PASS | `task.toml` / `instruction.md` / `environment/` / `solution/` / `tests/` |
| task.toml Schema 1.3 关键字段 | PASS | version / [metadata] / [agent] / [verifier] / [environment] / 资源 / 超时 ≤12h |
| 题面不泄漏解法 | PASS | `instruction.md` 无 Golden/Oracle/隐藏测试/F2P-P2P/Reward 表述 |
| environment 不泄漏答案 | PASS | `environment/workspace/` 仅含被测包源码与自带测试，无 solution/、无隐藏测试 |
| 题面 ↔ testcase 双向映射 | PASS | `testcase_mapping.csv`，7 条 F2P + 6 条 P2P 全部可追溯 |
| 二值判分 | PASS | `grade.py`：`score = 1.0 if resolved else 0.0`，无权重、无部分分、无 LLM Judge |
| INVALID ≠ 0 分 | PASS | 缺失/SKIP/解析失败 → 不写 reward 产物并 exit 2 |
| 身份三元组一致 | PASS | task.toml / swelive_spec.json / platform_import.json / manifest.json 同一 task_hash |
| 官方校验器 `validate_package.py` | 见 `_index/validate-report.json` | 退出码 0（FAIL=0） |

## 二、证据缺口（阻塞验收）

| # | 缺口 | 影响 | 补齐方式 |
|---|---|---|---|
| G1 | **镜像未构建，`image_digest` 为空** | 无法证明「同一镜像 Digest」下运行 | 在 Windows 构建机执行 `docker build` 后回填 `_index/EXTERNAL_IMAGES.json` 与 `metadata/manifest.json` |
| G2 | **对照验证未执行**（no-change ×3 / Golden ×3 / 反例 / 等价实现） | 无法证明 base 上 F2P 确实失败、参考解确实通过 | 平台 harness 在真实 Windows Runtime 中执行 `test.ps1` + `grade.py` 并回填 `evidence/` |
| G3 | **多模型运行未执行** | 区分度准入未完成 | 平台 harness 回填正式分后运行 `run_model_validation.py --score-only` |

### 诚实说明

本轮按出题方要求「先不跑测试」，只完成题目构造与静态结构校验。
`evidence/` 与 `model_runs/` 目录下的说明文件均如实标注为「未执行」，
**未以任何本地结果冒充平台结果**。

## 三、Hack 与答案泄漏审查（四层分级）

| 通道 | 分级 | 依据 |
|---|---|---|
| 联网搜索/下载上游答案 | none | 被测包为构造代码，上游不存在对应答案；运行期 air-gapped |
| 读取本地 Solution / 隐藏测试 / 旧制品 | none | Agent 可见范围内无 `solution/`、无 `test_patch.diff`；工作区 git 历史仅 baseline commit |
| 篡改 Tests / Verifier / 结果文件 | none | `tests/` 位于 `C:\tests`，不在 Agent 工作区内 |
| 复用旧二进制 / 伪造 PASS | none | 每次运行前 `test.ps1` 删除 `reports/` 与 verifier 产物 |

> 本轮无模型运行轨迹，上述判定为**静态审查**结论。规范明确「关键词未命中 ≠ 绝对无 Hack」，
> 模型运行阶段的动态审查须在 G2/G3 补齐时一并完成。

## 四、题面与测试公平性复核

- 每条 F2P 都能从 `instruction.md` 的「目标 / 验收标准」推出；不存在未声明要求。
- 测试只断言**系统终态与公共返回值**，不断言私有函数名、调用顺序或代码文本。
- 难度来自跨模块状态与失败路径辨析，不来自歧义或信息缺失。

## 五、已知风险提示

- 无。
