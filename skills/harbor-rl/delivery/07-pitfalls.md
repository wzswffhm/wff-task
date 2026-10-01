# 高频故障与踩坑录

## A. 判分崩溃 / 静默 0 分类（最致命）

| # | 症状 | 根因 | 正确做法 |
|---|---|---|---|
| A1 | Reward Kit 解析崩溃，整题判分不可用 | criterion **未写 `name`**，纯中文 `description` slugify 成空串，条目键全部塌缩 | 每条 criterion 显式写 `name = "<id>"`，与 `id` 相同 |
| A2 | 整题无分（连 `reward.json` 都没写） | `[judge].timeout` 用了缺省值 **300**，agent judge 调用 Bash 读文件超时 | **显式写 `timeout = 7200`**，且 `< [verifier].timeout_sec`（18000） |
| A3 | 扣分静默失效、整次评分作废重评（`verifier_error = 1`） | 写了**负数 weight** | 扣分只用 `negate = true` + **正** weight |
| A4 | judge 中间档位给分不可复现、不可审计 | likert 条目**未给 5/4/3/2/1 档位锚点** | 每档写到"可独立核验的具体情形" |
| A5 | judge 输出被 schema 拒掉 | likert 锚点写成 **0–1 小数** | 锚点按 **1–5 整数** 写（配合 `points = 5`） |
| A6 | judge 找不到交付物、照 criteria 判"没写" | criterion description **只写目录不给文件名** | `Deliverables to inspect:` 逐个写完整路径 `output/<文件名>` |
| A7 | judge 起不来（E2BIG） | `prompt.md` + 全部 description **≥100 KB** | 总量控制在 **<100 KB** |
| A8 | TOML 解析失败、整题判分不可用 | 从编辑器粘贴中文时带入 **U+00A0 / U+3000** 等不可见空白 | 提交前扫 `grep -rlP "[\x{00A0}\x{3000}]"` |
| A9 | 判分器中途被杀却留下"有效 0 分" | fail-closed 兜底被破坏 | 不得改动 `test.sh` 的 fail-closed 段；`verifier_error=1` 是"不可信"，**必须重评而非记零分** |
| A10 | 空产物得分 | judge 因**参考答案满足**而给分 | 保留 `Reference-solution policy` 段："不得因参考答案满足就给分，一切以候选交付物为准" |

## B. 结构与一致性类

| # | 症状 | 根因 | 正确做法 |
|---|---|---|---|
| B1 | criteria 永远对不上交付物名 | `required = true` 写了 **glob / 通配 / "或等价命名"** | `required = true` 必须写精确文件名；glob 只用于 `required = false` |
| B2 | 同上 | 文件名含**日期 / 时间戳 / 版本号**动态成分 | 去掉动态成分；业务需含日期的把字符串**写死** |
| B3 | 跨平台判断不一 | 大小写不一致（`Report.docx` vs `report.docx`） | **六处逐字节一致**（instruction.md / deliverables.path / artifacts / 两份 golden_output / criterion description） |
| B4 | 平台读不到题目 | `task_id` 在目录名、`[metadata].task_id`、`[task].name` 三处不一致 | 按小写连字符规则归一化后比对，org 段与批次前缀一致 |
| B5 | 题目跑不起来（AgentSetupTimeoutError） | `network_mode = "no-network"` | **固定 `public`**；claude-code 框架下 agent setup 要联网装 CLI |
| B6 | 工作目录错乱 | `[environment]` 写了 `workdir` | `[environment]` 只允许白名单键；工作目录由 Dockerfile 的 `WORKDIR /app` 决定 |
| B7 | 评分通道泄漏给被测模型 | `JUDGE_*` 写进了 `[environment].env` | `JUDGE_*` **只写 `[verifier.env]`**；`[environment].env` 遵循最小必要原则 |
| B8 | 平台不替换 `${VAR}`、本地判官全失败 | 本地自测没导 KEY | 本地自测自行 `export`；toml 里保持 `${VAR:-}` 占位符**原样** |
| B9 | 整题无分 / 内容丢失 | `solve.sh` / `test.sh` 是 CRLF 或无执行位 | **LF + `chmod +x`** |

## C. 环境与镜像类

| # | 症状 | 根因 | 正确做法 |
|---|---|---|---|
| C1 | 构建慢/失败 | Dockerfile 用了**国内镜像源** | **全部走官方源**（Debian / registry.npmjs.org / pypi.org） |
| C2 | judge 读不了交付物、大面积判负 | 镜像**缺装文档解析库** | 预装 markitdown / openpyxl / python-docx / python-pptx / pypdf 等 |
| C3 | judge 起不来 | verifier 容器内**没有 claude** | 镜像**预装 `@anthropic-ai/claude-code@2.1.114`**（平台不代装） |
| C4 | 评分跨批次不可比 | claude CLI 版本漂移 | **钉死 2.1.114**；版本变更后统一回刷 |
| C5 | Agent 无法写交付物 | `/app/output` 属主错误 | `chown -R agent:agent /app/output`；用 `su agent` 实测可写 |
| C6 | 源文件被模型改动 | 未设只读 | `chmod -R a-w /app/input_files` |
| C7 | 技能不可用 | skill 目录、任务书入口、Dockerfile 复制路径不一致 | 三处一致；以**实际 Agent 用户**验证可读可执行 |

## D. 难度与验收类

| # | 症状 | 根因 | 正确做法 |
|---|---|---|---|
| D1 | 参考答案也拿不到 0.85 | Rubric 写歪（要求过高/锚点错/golden 不完整） | 整题退回重写 Rubric；**不得改题意凑分** |
| D2 | 三模型全 0（死题） | 门槛过高，无任何可得分项 | 降低门槛或补充可得分项，避免全 0 |
| D3 | 题目太简单，均分 ≥0.7 | 无足够专业深度要求 | 提高任务复杂度或按 A1/A2/A3 重新定级 |
| D4 | 把 `verifier_error=1` 当 0 分纳入统计 | 未区分"评分不可信"与"确实得 0 分" | `verifier_error=1` 必须**重跑**，不得纳入难度统计 |
| D5 | 无法验证难度 | 未提交模型产物与跑分轨迹 | 提交时**同步提供模型产物和跑分轨迹** |

## E. 打包与合规类

| # | 症状 | 根因 | 正确做法 |
|---|---|---|---|
| E1 | zip 被拒 | 含 `.git/`、`__pycache__/`、`.venv/`、`__MACOSX/`、`.DS_Store`、`reward.json`、`logs/`、`jobs/`、嵌套 zip、符号链接 | 提交前逐项扫描清理 |
| E2 | 层级不对 | 题目目录平铺在 zip 根 / 多套一层 | 固定「批次 → 题目 → 五件套」 |
| E3 | 泄漏凭据 | 题包内含真实密钥/token | 用占位符（如 `<API_KEY>`）并在任务书说明 |
| E4 | 领域混装 | 一个 zip 装多个领域 | **按领域分别打包** |
| E5 | 返修后平台认不出 | 未递增 `[task].version` 或改了供应商代号 | 补丁号递增；批次目录名加 `_fix<N>`；代号不变 |
| E6 | 缺交付文档 | 未在批次根放 `交付文档.md` | 必交，且环境变量表覆盖全部实际使用的变量 |

## F. 口径混用（最容易犯的"低级但严重"错误）

| # | 症状 | 正确做法 |
|---|---|---|
| F1 | 同一批次混用 `harbor-sota`（`tests/graded/judge.toml` + `tests/gating/gating.toml`）与本规范（`tests/rubrics.toml` + `tests/prompt.md`） | **一套规范贯穿全批**；两者评分体系与文件结构不同，**不得混用** |
| F2 | 沿用 `tests/golden_output/` 命名 | 本规范是 `tests/__golden_output/`（双下划线） |
| F3 | 沿用 gating 一票否决思路写 rubric | 本规范无 gating 文件；致命问题用 `negate = true` + `weight = 10.0` 表达 |

## G. 提交前 30 秒快速自检

```bash
# 1) 结构
ls instruction.md task.toml rubrics.json environment solution tests

# 2) 模板未改动 + 语法
bash -n tests/test.sh && python3 -m py_compile tests/finalize.py

# 3) 关键字段
grep -E '^judge|^model|^timeout|^mode' tests/rubrics.toml
grep -c 'criteria}' tests/prompt.md                        # 应为 1
grep -E 'weight *= *(-|[0-9.]+)' tests/rubrics.toml | grep -v '\-'

# 4) 一致性 / 洁净
grep -n "Deliverables to inspect" tests/rubrics.toml | wc -l
find . -type l | wc -l                                     # 应为 0
grep -rlP "[\x{00A0}\x{3000}]" --include="*.toml" --include="*.md" . | wc -l   # 应为 0
```
