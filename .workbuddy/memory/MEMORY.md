# MEMORY.md — wff-task 项目长期记忆

> 2026-10-01 整理。`Desktop\wff-task` 即仓库根：`git@github.com:wzswffhm/wff-task.git`（PRIVATE / `main`）。

## 1 目录与铁律（skill `wff-workspace-discipline`）

| 目录 | 内容 |
|---|---|
| `OBM/` `harbor-16/` `harbor-sota/` `harbor-windows/` `harbor-weakness/` `harbor-rl/` | 题包类型目录，名同 skill |
| `deliverables/` | 解析产出 `<date>_<材料名>/` |
| `skills/` `.workbuddy/` | 唯一 skill 目录 / 会话记忆 |

铁律：① 根级仅 `README.md`/`.gitignore`/`deliverables/`/`skills/` + 已登记题包类型目录；② 题包类型目录根**只放公用配置**，题目专属内容**一题一目录**禁止上浮；③ 产出放 `deliverables/<date>_<材料名>/`（`date +%F` 真值）。原 `Harbor/` 已删（2026-09-29）→ `skills/harbor-16/workspace/`。

## 2 skills/ 与注册机制

| skill | 说明 |
|---|---|
| `OBM` | subskills: production-trae / review / run-qc |
| `harbor-16` | 内部 RL（`zq*`，pytest 程序化评分） |
| `harbor-sota` | 外发供应商题包（**旧版 v4**：`judge.toml`+`gating.toml`） |
| `harbor-windows` | Windows 专项 Coding Bench（**二值判分**，无 LLM Judge） |
| `harbor-rl` | 法律（Law1–Law6）+ 内联 `delivery/` |
| `harbor-weakness` | 金融（专项 1000 + Weakness 1000）+ 内联 `delivery/` |
| `harbor-work` / `caveman` / `wff-workspace-discipline` | 标注 / 精简输出 / 落盘纪律 |

frontmatter `name` **必须小写连字符**（含空格会调用失败）。

**注册 = 目录联结（junction）**：可发现路径 `~/.workbuddy/skills/`，9 个条目全指向 `wff-task/skills/<name>`。建：`New-Item -ItemType Junction -Path <link> -Target <target>`（免管理员；⚠️ `cmd /c mklink /J` 与 Git Bash 均不可用）；删：`[System.IO.Directory]::Delete($link,$false)`。改仓库即改用户级 skill；**禁止 copy 同步**。

**判分口径三线不可混用**：

| 题包线 | 判分 | 裁判 |
|---|---|---|
| `harbor-windows` | required F2P/P2P **二值** | 无 |
| `harbor-16` | `tests/quality.toml` + pytest | 无 |
| `harbor-rl` / `harbor-weakness` | rewardkit 20260913：`rubrics.toml`+`prompt.md`+claude-code | **有**（如 `qwen3.7-plus`） |

## 3 harbor-rl / harbor-weakness（法律 / 金融）

**粒度原则**：skill 对齐**规范文件**，不对齐题型细分。`harbor-rl` ←《RL0-1 数据生产规范（法律）》；`harbor-weakness` ←《基于 weakness 和 skill 的数据构造方案（金融）》；两者 `references/` + `delivery/00–08` + `templates/` + `assets/` 同构。
- **`delivery/` 双份须逐字一致**：`diff -r skills/harbor-rl/delivery skills/harbor-weakness/delivery`
- **`delivery/scripts/`**：`check_rubrics.py <tests/rubrics.toml>`（G3 门禁）、`check_package.py <题目目录>`（17 项中可静态验证的 11 项；#6/#13/#16/#17 须实机）。改一处须同步另一 skill。

**金融配额**：专项 1000（5 类 ×200：Skill Discovery / Generation-Editing / Dependency / Workflow / Subagent）+ Weakness 1000；每类 weakness ∈[50,250]；C1–C5 = 120/250/350/180/100；同一知识点出题 <3 道。
**法律口径映射**：`weight=-3/-7/-10` → 交付态 `3.0/7.0/10.0` + `negate=true`（**严禁负 weight**）；`type=Gradient` → `type=likert` + `points=5`。
共同验收：参考答案 >0.85；三模型均分 <0.7 且至少一个有分；人工质检发现 hack 直接打回。

**交付态五件套**（rewardkit 20260913，与 `harbor-sota` v4 **不得混用**）：`instruction.md` / `task.toml`(schema 1.4) / `rubrics.json` / `environment/`(Dockerfile+requirements.txt+input_files/+skills/) / `solution/`(solve.sh+golden_output/) / `tests/`(test.sh+finalize.py+rubrics.toml+prompt.md+__golden_output/)。`test.sh`/`finalize.py` **逐字复制**自 `delivery/templates/`。

**G1–G6 门禁**（**归纳编号**）：G1 结构齐全｜G2 六处文件名逐字节一致 + task_id 三处一致 + 无真实密钥｜G3 weight 仅 `3.0/7.0/10.0`、type 仅 binary/likert（likert 须 `points=5`+5/4/3/2/1 锚点）、`name==id`、description 含 `Deliverables to inspect:`、Critically Important ≥2、内容质量正分 ≥30%｜G4 golden 主分 >0.85 且 `verifier_error=0` + 镜像自检末行 `OK`｜G5 三模型均分 <0.7 且至少一个有分｜G6 洁净（无 `.git/`/`__pycache__/`/`.venv/`/`reward.json`/`logs/`/`jobs/`）。

**评分机制**：`S_max = Σ正向 weight`（负向不进分母）；`reward = clip((Σ正w×v − Σ负w×(1−v))/S_max, 0, 1)`；likert 归一 `(raw−1)/4`；扣分只能 `negate=true`+正 weight。`verifier_error=1` = 评分不可信须重评，**不是 0 分**。

**★ 本地全链路可跑（2026-10-01 打通，取代旧"须平台跑"结论）**：WSL Ubuntu 已有 `harbor 0.22.0`（`~/.local/bin/harbor`）+ `docker.io 29.1.3` + `docker-compose-v2`，可跑**真实 rewardkit + claude-code judge**；`harbor-rewardkit==0.1.7` 在 pypi 确实存在（旧结论错误：排序看漏）。
`harbor trial start -p <task> -a <oracle|claude-code|nop> [-m <model>] --ae K=V --ve K=V --ak K=V --trials-dir <dir>`；`-a oracle` 跑 `solution/` 做 G4；verifier 写 `/logs/verifier/reward.json`。⚠️ 纯 LLM 近似判分可预筛，但**不可**喂 `tests/prompt.md` 全文（含 shell 提示，模型会去执行工具）。

**★ harbor 实跑四坑**：
1. **`verifier_error=1` 可能是占位**：harbor 在 verifier 启动**前**写 fail-closed 占位 `{"reward":0,"verifier_error":1}`，跑完才覆盖 —— **必须等 verifier 进程消失后再读**。成功运行**不存在** `reward_exit_message.json`；`criteria_counted=23`+`verifier_error=0` 才是真结果。
2. **claude-code Plan Mode 死锁**：`gpt-5.6-sol` 触发 `EnterPlanMode`→`ExitPlanMode` 求批准，非交互 `--print` 下直接 `end_turn`，**只 Write 1 次、产物为空**。修法：`--agent-kwarg "disallowed_tools=EnterPlanMode,ExitPlanMode"`（`parse_kwargs` 按 `=` 切分；claude CLI `--disallowedTools` 收逗号分隔）。修复后 0.0 → 0.65。
3. **agent 提前收尾 ≠ 框架故障**：opus 476s/37 轮停在同处漏交主交付物 → 真实模型弱点（命中 `W04`），保留该分；只有 Plan Mode 这类"框架死路"才判无效重跑。
4. **单次 G5 耗时**：gpt 37min agent + 33min verifier；qwen 109min agent（120 轮、35 次 Edit）+ 20min verifier。四任务并发时 **LiteLLM 桥 + aliyun judge 是瓶颈**，verifier 拖到 30min+。

**★ `check_package.py` #9 与 06 号文档命名冲突（须规避）**：#9 用 `ROOT.rglob('*')` + `p.name in {'reward.json','reward-details.json','reward_exit_message.json','logs','jobs'}` 递归判残留 → 会把 06 号 §4 **要求**归档的 `model_runs/<模型>/reward.json` 判 FAIL。规避：归档分数文件加 `verifier_` 前缀。另 `model_runs/trace/` 的 claude 日志含运行期凭据与 U+3000 → 须脱敏（`<REDACTED_CREDENTIAL>` + 空格）才过 #8/#14。

**★ 交付文档（#17）**：批次根放 `交付文档.md`（批次信息 + 环境变量表覆盖全部实际变量 + 验证结论 + 归档说明）；单题时以**题包类型目录**兼作批次根。镜像整体自检命令（**末行须打印 `OK`**）在 `05-environment-and-solve.md` §2。

## 4 已交付验证题：FIN3-WKN-149（金融，唯一全链路验证题）

G4 三轮回溯 **0.8103 → 0.8914 → 0.9397**（同一 golden；残余 R12 情景窗口歧义 0.75、R20 复算脚本含字面量常量 0.00）。
G5：`gpt-5.6-sol 0.65` / `claude-opus-4-8 0.0966`（漏交主交付物备忘录）/ `qwen3.8-max0902 0.7259` → **均分 0.490805**（<0.7 达标，落 A3 `[0,0.5)`）。⚠️ 距 A3 上界仅 **0.0092**，换模型集合须复核。
归档 `harbor-weakness/FIN3-WKN-149/model_runs/`；交付文档 `harbor-weakness/交付文档.md`；`check_package.py` → `[PASS]`。

## 5 harbor-windows（Windows 专项 Coding Bench，平铺）

三底线：① 反事实判定（换 Linux 后实现/根因/Evaluator 不变 → 淘汰）；② **二值判分**（required F2P+P2P 全过=1，异常=INVALID 不得伪装 0 分），无权重/部分分/LLM Judge；③ 身份唯一 `task_id + task_version + task_hash`。

**task_hash**：`sha256("task_id="+id+"\n"+"task_version="+v+"\n"+"instruction_md_sha256="+h+"\n"+"test_patch_sha256="+h+"\n"+"oracle_patch_sha256="+h+"\n"+"dockerfile_sha256="+h")`，**末行不带换行**。

**平铺布局**（2026-10-01 起取代批次层）：`harbor-windows/<task-id>/`（task.toml / instruction.md / environment/ / solution/ / tests/ + platform_import.json + extras/）+ `_index/`。迁移只改元数据/文档层，**绝不触碰** `environment/workspace/**`、`tests/test_patch.diff`、`solution/oracle.patch`、`instruction.md`。

**骨架两处须按题适配**：① `tests/test.ps1` 判候选故障用 `$testRc -gt 1`（pytest 返回 1 是合法 0 分）；② `swelive_spec.json` 的 `log_parser` 须兼容多行 JSON（`json.JSONDecoder().raw_decode(...)`）。

**已验证**：9 题包，required 107 条（F2P 62 + P2P 51），全 L4；`validate_package.py --package harbor-windows` → PASS=256 FAIL=0 FLAG=0；仅 `wsync-142` 有实测对照。

**端点**：aliyun `https://llm-cz4pcezs463b102x.cn-beijing.maas.aliyuncs.com/apps/anthropic`（**须带后缀**）/ `qwen3.8-max`、`GLM-5.3`、`Kimi K3`；blvr `https://api.blvr.top` / `claude-opus-5`。协议 Anthropic Messages。env：`HARBOR_WINDOWS_ALIYUN_KEY`、`HARBOR_WINDOWS_BLVR_KEY`。

**火山方舟 coding plan**：Anthropic 端点 `https://ark.cn-beijing.volces.com/api/coding`，OpenAI 同址 + `/v3`；key 前缀 `ark-9bd32e64`（env `HARBOR_WINDOWS_ARK_KEY`）。**三坑**：① 鉴权必须 `Authorization: Bearer`（`x-api-key`→401）；② 模型 id 小写连字符 `glm-5.3`/`kimi-k3`；③ **默认强制 thinking**，GLM-5.3 无法关闭（`disabled`→400），`max_tokens=8192` 时正文为空，须 ≥32000。

## 6 harbor-16 vs harbor-sota

| 特征 | `harbor-16`（内部 RL） | `harbor-sota`（外发 v4） |
|---|---|---|
| schema | 1.3 | 1.4 |
| 评分 | `tests/quality.toml` + pytest | `tests/graded/judge.toml` + `tests/gating/gating.toml` |
| 参考答案 | `solution/`（oracle.patch） | `solution/golden_output/` + `tests/golden_output/` |

## 7 ⚠️ 真实明文密钥位置（2026-09-29 全库扫描，已推送私有仓库）

| # | 位置 | 前缀 | 类型 |
|---|---|---|---|
| 1 | `skills/harbor-windows/scripts/run_model_validation.py`(63/89/102) | `sk-ws-H.PIDYYYX` | aliyun MaaS |
| 2 | 同上(76) | `sk-l8hraN17` | blvr |
| 3 | `skills/harbor-16/workspace/docs/check.md`(3) | `sk-ws-H.ERLPMXH` | aliyun 旧 |
| 4 | `OBM/model.env` | `ark-9bd32e64` | 火山方舟 |
| 5 | `OBM/feishu-gsb.toml` | `cli_aaf0…`/`ou_35041…` | 飞书 |

低风险（仅端点无 Key）：`skills/harbor-16/references/notes-22.md`、`ops-notes.md`、`skills/OBM/subskills/run-qc/config/obm.paths.json`。合规非泄漏：`harbor-sota` 用 `${OPENAI_API_KEY}`/`${JUDGE_GATEWAY}` 占位符须逐字保留。扫描排除 `OBM/.venv/`。

## 8 Git 约定

认证走 **SSH**（`~/.ssh/id_ed25519`，账号 `wzswffhm`），**绝不改回 HTTPS**。必须 `core.longpaths=true`（有 >260 字符深路径）、`core.autocrlf=false`。本机两套 Git；`user.name=v_wffanwang`；`gh` 在 `C:\Program Files\GitHub CLI\gh.exe`。
大仓库加速：本机 **7897 端口有 HTTP 代理**，`git -c core.sshCommand="ssh -F <临时config>"` 走 CONNECT 隧道可达 4.7–6.2 MiB/s（**SSH 不读 `http_proxy`**）；详见用户级 skill `git-clone-accelerate`。
工作流 `git add -A && git commit && git push` —— **仅在用户明确要求时执行**。新增内容前先确认无内层 `.git`。

## 9 约束与排除

`OBM/Benchmark/terminal-bench-main/` 下有 3 个 60–95MB 归档（最大 `mysql/datadir.tar.zst` 94.68MB，逼近 100MB 硬限）；新增 >100MB 单文件 push 会被拒，需 Git LFS。排除：`OBM/.venv/`、`.git-archives/`、`.DS_Store`、`__pycache__/`、`*.pyc`。

## 10 文档与术语纪律

规范原文术语 ≠ 自造编号 —— 自行归纳的编号（`G1–G6` 等）须在首次出现处标注"归纳编号"；断言"某结论出自规范"前先 `grep` 原文定位行号；**同一文档内禁止同一编号两种含义**。

## 11 用户偏好

中文交流，**结论先行 + 结构化表格**；全局配置/破坏性操作前先说明影响面；直给风格。**不要自动提交代码**（等用户明确说"提交/推送"才 commit+push）；删除/清理不必逐次确认（已授权）。凭据/能力受限时倾向"先把工具链做完"，而非阻塞等待。
