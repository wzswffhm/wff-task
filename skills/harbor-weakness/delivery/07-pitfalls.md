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
| A11 | **单条判据 1 小时不跳条**，最终烧到 `[judge].timeout` 才被杀、该判据给错分 | judge（`claude-code` + `mode=individual`）陷**死循环**：模型在单条判据会话内**反复 emit `StructuredOutput`**（实测 397+ 次仍增长），claude-code 不终止 | **偶发**，重跑即可。识别：容器内取最新 `/root/.claude/projects/-app/*.jsonl`，统计 `tool_use.name=="StructuredOutput"`；**>15 且仍增长 = 死循环**（正常 1–2 次）。分母口径：`sessions` 数 = 已判条数（每条判据一个会话），**会话数长期不变 = 卡住**；正常慢时每 1–2 min 新建会话。伴随特征：`claude -p` etime 涨而 pcpu≈3%、会话文件 size 持续增长。处置：`systemctl stop <unit>` + `docker rm -f <container>` + 删 run 目录 + **原样重跑**（勿改 rubrics/模型） |

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
| B10 | **oracle 也拿不到该分**（如 "交付物齐全" 必得分项恒判 FAIL） | criterion description 里交付物用了**非全名简写**（去掉 task-id 前缀 / 缺扩展名，如写 "chart01 材料覆盖与数据缺口"，实际文件是 `FIN3-WKN-150_chart01_材料覆盖与数据缺口.png`），同条判据又要求"文件名须逐字一致" → judge 按字面比对判 FAIL | 判据引用交付物**必须写全名**（含 task-id 前缀 + 扩展名，并加反引号），与 instruction.md / task.toml 的 artifacts **逐字节一致**；提交前跑 `check_package.py`，其 **#3b** 会对"非全名写法"告警 |
| B11 | **质检判"`rubrics.json` 与 `tests/rubrics.toml` 评分定义不一致"（SCORING 必修、"必须以同一判据版本同步两份文件并重跑"）** | 设计态 `rubrics.json` 的负向项**只用负 `weight` 表示、缺 `"negate": true`**，而运行态 `tests/rubrics.toml` 用 `negate = true` + 正 weight；两套表示法不对应（`validate_rubrics`/preflight 会以"negate 集合差、正分池不符"报错，即便两侧实际正分池相等） | `rubrics.json` 的负向项**必须同时写** 负 `weight` **与** `"negate": true`（**双标记**），并与 `tests/rubrics.toml` 的判据 id 集合、负向集合、正分池 `S_max` 逐一对齐（以 149 的 JSON 写法为准）；提交前跑 `check_package.py`，其 **#4b** 校验设计态/运行态判分定义一致 |
| B12 | **甲方 `validate_rubrics` 文本正则误伤**：报 "toml negate 集合 3 条 / 正分池比 JSON 少 3"，但 tomllib 实际解析 negate={N01,N02}、正分池双侧一致 | `tests/rubrics.toml` 的**节注释行**含字面子串 `negate = true`（如「落到本文件为 negate = true + 正 weight」），甲方脚本按 `'negate = true' in 块` 子串判定、把注释吞进前一条判据块 | TOML 注释/描述**避免出现 `negate = true` 等甲方解析器敏感字面串**（改写为「negate 形式」等等价表述）；纯注释改动不影响判分（tomllib 忽略注释），无需重跑；定位方法：用 `re.findall(r'\[\[criterion\]\](.*?)(?=\n\[\[criterion\]\]|\Z)', toml, re.S)` 复现甲方分块 |
| B13 | 甲方 `check_instruction_anchors.py` 对自有批次报「锚点缺失 N 个」 | 脚本**硬编码甲方自有批次** FIN-127/128/129-W 的锚点清单，对本 skill 产出的题包**不可复用** | 忽略其输出；判据锚点在题面/材料的命中性**人工逐条核**（对照 instruction.md 与 `environment/input_files/`），并在质检报告注明该脚本不适用 |
| B14 | 甲方 `check_package_permissions.py` 对 `FIN3-WKN-xxx_task.zip` / `_answer.zip` 报「缺 交付文档/跑分产物与轨迹 等」FAIL | 该脚本按**批次包**结构校验（批次根须有 交付文档.md 与 跑分产物与轨迹/）；task/answer 是**拆分包**（task=设计态五件套、answer=仅 golden），本来就不含这些 | 批次包必须 PASS；task/answer 拆分包的 FAIL 属**口径不符、非缺陷**，在质检报告注明即可 |

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

# 5) 静态门禁（含 #3b 交付物全名、#4b 设计态/运行态判分定义一致）
python3 ../scripts/check_package.py .                      # 期望 [PASS]，无 #3/#3b/#4b 告警
python3 ../scripts/check_rubrics.py tests/rubrics.toml     # 期望 G3 门禁全通过

# 6) 甲方机器门禁（04 §0b，以此为准）
python3 ../scripts/client_gates.py . --zip <批次zip> \
    --runs-dir <正式批次的跑分产物与轨迹> --waive check_rubric_style.py   # 期望 0 必须整改
```
