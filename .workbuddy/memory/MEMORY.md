# MEMORY.md — wff-task 项目长期记忆

> 2026-10-07 三次压缩（去重/精简/更新 215）。仓库根 `Desktop\wff-task`：`git@github.com:wzswffhm/wff-task.git`（PRIVATE/`main`）。

## 1 目录铁律（skill `wff-workspace-discipline`）
题包类型目录 `OBM/ harbor-16/ harbor-sota/ harbor-windows/ harbor-weakness/ harbor-rl/`；产出 `deliverables/<date>_<材料名>/`；唯一 skill 目录 `skills/`；记忆 `.workbuddy/`。
① 根级只放 README/.gitignore/deliverables/skills+题包目录；② 题包目录根只放公用配置，一题一目录、禁上浮；③ 日期用 `date +%F`。

## 2 skills/
frontmatter `name` 小写连字符（含空格调用失败）。注册=junction：`~/.workbuddy/skills/` → `wff-task/skills/<name>`（删用 `[System.IO.Directory]::Delete($link,$false)`）；**改仓库即改 skill，禁 copy 同步**。判分三线不混用：windows 二值 F2P/P2P ｜ harbor-16 `tests/quality.toml`+pytest ｜ rl/weakness rewardkit。

## 3 harbor-rl / harbor-weakness（法律/金融，rewardkit）
两 skill 的 `references/delivery(00–08)/templates/assets` 同构，`delivery/` 双份须逐字一致。
配额 专项 1000（5类×200）+ Weakness 1000；每类 weakness∈[50,250]；C1–C5=120/250/350/180/100；同知识点<3 道。
法律映射 `weight=-3/-7/-10`→`3.0/7.0/10.0`+`negate=true`（禁负 weight）；`Gradient`→`likert`+`points=5`。验收：参考答案>0.85；三模型均分<0.7 且至少一个有分；hack 打回。
五件套 `instruction.md`/`task.toml`(1.4)/`rubrics.json`/`environment/`/`solution/`/`tests/`；`test.sh`(`5920c204`)/`finalize.py`(`f528b27f`) 逐字复制**平台模板**（149/150 采用版；skills 内 templates 较旧勿用）。
G1–G6（**归纳编号**）：结构齐全｜六处文件名逐字节一致+task_id 三处一致+无真实密钥｜weight∈{3,7,10}、likert points=5+1–5 锚点、`name==id`、description 含 `Deliverables to inspect:`、CI≥2、正分池≥30%｜golden>0.85 且 verifier_error=0｜三模型均分<0.7 且至少一个有分｜洁净。
评分 `S_max=Σ正w`；`reward=clip((Σ正w×v−Σ负w×(1−v))/S_max,0,1)`；likert 归一 `(raw−1)/4`；`verifier_error=1`=评分不可信须重评。
甲方门禁（桌面 `weakness-data-construction` v2.4 / `weakness-qc` v1.0）细节已固化进 `harbor-rl`/`harbor-weakness` 的 `delivery/04 §0b`、`06 §7`、`07 B13/B14` + wrapper `delivery/scripts/client_gates.py`（**不复制甲方脚本**、打印 SHA256 防漂移、runs-dir 自动发现、`--waive` 须规范原文复核后留痕）。
**★ B12**：`validate_rubrics` 用正则 `'negate = true' in 块` 判 negate → rubrics.toml **注释/description 含该字面串会被吞进前条判据块**假报 → 注释禁写该串（已修 150/151）。另：`check_instruction_anchors.py` 硬编码批次；`check_package_permissions` 按批次包口径（拆分包 FAIL 属口径不符）；`rejudge_by_docker.py` 可只重跑判官；`check_rubric_style --strict` 量词 FAIL 系 likert 锚点递进量词=口径冲突→waive。

## 4 harbor 本地实跑（WSL Ubuntu + harbor 0.22.0 + docker）
`harbor trial start -p <task> -a <oracle|claude-code|nop> [-m <model>] --ae/--ve/--ak K=V --trials-dir <dir>`；`-a oracle` 做 G4。
坑：① `verifier_error=1` 可能是占位 → 等 verifier 进程消失再读。② claude-code Plan Mode 死锁 → `--agent-kwarg "disallowed_tools=EnterPlanMode,ExitPlanMode"`。③ 并发判官打同一 judge key 互相拖死。④ config.json 的 JUDGE_API_KEY 是掩码；探 key `curl -H "x-api-key: <k>" <URL>/v1/messages`（429=有效/401=无效）。
**★ WSL 长任务中断根因**=发行版级空闲关机（最后一个 `wsl.exe` 客户端脱离即关停 → docker Exited(255)）。解：2 个计划任务（`wsl-keeper-ubuntu`/`-b`）动作 `wsl.exe -d Ubuntu -u root -e sleep infinity`，`-ExecutionTimeLimit ([TimeSpan]::Zero)`+`IgnoreNew`+每分钟重复+`RestartCount 999`；校验须见 2 条。编排器 `systemd-run --unit=<n> --setenv=HOME=/home/wff` **必须 root**。
**★ verifier-only 重判**：`harbor trial regrade` 仅支持 separate；SHARED 等价 = `harbor trial start -a nop --mounts '[{…bind /app/output}]' --ve JUDGE_*`。
**★ judge 死循环**：claude-code+individual 每判据一会话（`sessions`=已判条数）。故障=单判据内反复 emit `StructuredOutput`（>15 且增长）→ 烧到 timeout。识别：会话数不动 + claude etime 涨而 pcpu≈3%。处置：stop + `docker rm -f` + 删 run 目录 + 原样重跑。
**★ WSL/Git Bash 硬规避**：① 需变量命令落 `.sh` 再 `wsl bash /mnt/c/...`；② 加 `MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL='*'`；③ root 操作 `wsl -u root -- bash <script>`；④ `bash script.sh|head -N` 会 SIGPIPE 杀脚本。

## 5 harbor-weakness 已交付题（索引）
| 题 | 域 | 批次 | 关键锚点 |
|---|---|---|---|
| FIN3-WKN-149 | 金融/宏观压力测试 | `work_fin-b01_20261005_fix6-149` | G4 0.991422/36；G5 均分 0.595588；飞书 `rec28himvkSA77` rev223；zip 336624/1011976/8549036 |
| FIN3-WKN-148 | 公司法 | — | **作废**（他人已用） |
| FIN3-WKN-150 | 金融/Pre-IPO 尽调 | `work_fin-b01_20261006_fix2-150` | G4 g4v6 `Sek4FmX` **1.0**/36/err=0；G5 均分 0.621970；飞书行 `reczz28Jf9pZeD1T`；zip 14057147/68644/927362 |
| FIN3-WKN-151 | 金融/银行授信 | `work_fin-b01_20261006-151` | G4 0.967914/32/err=0；G5 均分 0.659091；飞书行 `reczz28JsandcwbA`；zip 10235591/56919/587232；task_version=1.0.1 + run_task_version=1.0.0 |

**★ 归档在批次级**：`跑分产物与轨迹/` 与任务目录、交付文档平级。zip 根=批次目录；zipfile 显式写 external_attr（*.sh→0755）。`check_package.py`：#9/#14 对"跑分产物与轨迹"豁免（**#8 真实密钥不豁免** → 轨迹 claude 日志须脱敏 sk-*/ark-*/Bearer/x-api-key）。
**★ 金标脆弱点**：判据要"说明本次为 Pre-IPO 少数股权增资、不涉及控制权转移"时，金标只写结论不写前提会被 binary 判 0。判据字数按"汉字+中文标点"口径核对。
**★ 端点截断假分**：末轮 message 无 stop_reason + result 却是 tool_use + output_tokens≈1 + 交付物缺失。
**★ summary 版本对账**：未重跑的修复批次写 `task_version=交付版本`+`run_task_version=实际运行版本`+`version_note`。
**★ record-get 解析坑**：返回 `data.field_id_list`/`field_type_list`/`fields`(字段名列表)/`data`(行值列表)，按 zip(ids,names,types,row) 对齐，不是 fields dict。
**★ 飞书（weakness 表）**：`+record-upload-attachment --file` 有路径白名单 → 先 cp 到 temp 再传；同名先删旧再传新。字段 `fld2LBu2Ns`=参考答案、`fld2TmGhqt`=标准答案附件。建行 `+record-upsert`；**探测可写性禁用「新建」试探**。序号↔金融Sheet(N-126)；base `QpzNb4fXSamfX6sLloBcPfHNnug`/table `tblPNrBtjFfwOowN`。

## 6 harbor-windows（Windows Coding Bench）
三底线：① 反事实判定；② 二值判分（F2P+P2P 全过=1，异常=INVALID 不得伪装 0 分）；③ task_hash = `sha256("task_id="+id+"\n"+"task_version="+v+"\n"+"instruction_md_sha256="+h+"\n"+"test_patch_sha256="+h+"\n"+"oracle_patch_sha256="+h+"\n"+"dockerfile_sha256="+h")`，末行不带换行。
布局 `harbor-windows/<task-id>/` 平铺 + `_index/`。迁移只改元数据/文档层，绝不触碰 environment/workspace/**、tests/test_patch.diff、solution/oracle.patch、instruction.md。

**★ 资格门禁**（`Desktop/generate-win/scripts/summarize_model_runs.py`，sha256 `449cc0ea…5f8d`）：`REQUIRED_MODELS={QWEN:3, OPUS:3, GLM:1, KIMI:1}`；`qualified = controls_ok ∧ models_ok ∧ (sum(OPUS)>sum(QWEN)) ∧ version_consistent ∧ epoch_ok`。必须带 `--after <epoch>`；**`agent.status ∈ {completed, max_turns}` 才计分**，`error`/`no_tool_call`/`None` **剔除**（网关故障不得计 0）；每模型取 `valid[-required:]`；controls `--control-runs 3` 须 no-change=0 + golden=1 全 VALID；**GLM/KIMI 得分不影响门禁**。CLI：`--workspace-root <runner> --task-id <id> --after <epoch> --control-runs 3 --output logs/_.json`。
**★ 端点**：OPUS `https://4router.net`/`claude-opus-5`（**可用，key `sk-ABTd…2gE`，支持流式**；ebond key `sk-ff43…` **余额耗尽 403**）；QWEN `…maas.aliyuncs.com/apps/anthropic`（须带后缀）/`qwen3.8-max-0902`；GLM `https://api.lmuai.com`/`glm-5.3`；KIMI `https://ark.cn-beijing.volces.com/api/coding`/`kimi-k3`（`Authorization: Bearer`）。`api.blvr.top` 无 key。
**★★ 传输层超时 → 开流式（2026-10-07 定论）**：runner 默认非流式（`urlopen`→`read()`），长输出（2 万+ tokens）必撞 `REQUEST_TIMEOUT`/网关非流式墙 → `agent.status=error` **被剔除**（非 0 分）。**口诀：小请求秒回、长输出必挂、同 payload 反复挂 = 传输层**。正解=`.env.local` 加 **`<ALIAS>_STREAM=1`**（runner 内置 SSE，输出与非流式逐字节兼容，agent 零改动）；其次抬超时/禁 thinking。**换端点前先开流式**。详见 `harbor-windows/references/08-model-validation.md` §7.10–§7.14。
**★ QWEN 须禁 thinking**：`QWEN3.8-Max-0902` 是推理模型，大改动题 thinking 爆表（65536 tok≈1150 s）→ 请求永不返回。配 `QWEN_EXTRA_JSON={"thinking":{"type":"disabled"}}`（GLM/KIMI 同型；**OPUS 忽略**）。
**★ 出题三步法（用户 2026-10-06 群公告）**：① 先只并跑 QWEN 压 rubrics 分到均分 <0.7；② 再串行跑 oracle/qwen/opus/gpt 出交付物；③ 用 skill 质检一次。**交付节奏**：争取 10-07 18:00 前交，之后可能**锁表**。
**★ 离线复评（免重跑）**：`runner/work/<run_id>/case/environment/workspace/` 保留模型改完后的实现（`-KeepWork`）→ 改完 `tests/` 可对历史轮次离线复评。
**★ Outside Harbor 进度**：217 已 `qualified=true` 并交付（飞书 `reczz28KQU8reW2k`，编号 118）。**215 `wfflab__wfmt-215` 已 `qualified=true`（2026-10-07 22:59；task_version 2.0.0；epoch `2026-10-07T06:12:40+00:00`；OPUS `[1,1,0]=2`@4router ｜ QWEN `[0,0,0]` ｜ GLM `[1]` ｜ KIMI `[0]`；`agent_failures_excluded=2`=ebond 余额耗尽的 e43c/c3ca）**；读数 `runner/logs/_wfp_summary.json`；**尚未打包、尚未飞书写回**。

**★ Windows 运维细节已移入 skill**：`harbor-windows/references/10-windows-ops-pitfalls.md` ——
① Windows 容器适配 6 坑（PATH 不展开 / `python -c` 引号 / `._pth` 隔离 sys.path / `WORKDIR` 反斜杠 / git safe.directory / `--keep-work`）；
② 计划任务编排命令 + 3 坑（`-Execute` 绝对路径、二次触发、`AddDays(1)` 次日自燃 → 用毕 `Disable`）；
③ 飞书写回编码坑（`OutputEncoding=UTF8` 否则 read-back 抛 `Invalid lark-cli JSON`）+ 表/字段 ID；
④ `runner.py` 已参数化（`resolve_task_profile`，217 零影响）+ `run_id` 加 `token_hex(2)` 防并行互踩；
⑤ PS 7.6.4 的 `-AllowStartIfOnBatteries` 命名坑、日志通配符自吞坑。
**★ 本机跑题**：管理员 + PS 绝对路径 `…\v1.0\powershell.exe`；**PowerShell 工具不回 stdout → 一律 `*> file` 再 Read**（已见上）。

## 7 harbor-16 vs harbor-sota
harbor-16（内部 RL）：schema 1.3，tests/quality.toml+pytest，答案 solution/（oracle.patch）。
harbor-sota（外发 v4）：schema 1.4，tests/graded/judge.toml+tests/gating/gating.toml，答案 solution/golden_output/。

## 8 明文密钥位置（2026-09-29 扫描）
`skills/harbor-windows/scripts/run_model_validation.py`(63/89/102 aliyun、76 blvr)｜`skills/harbor-16/workspace/docs/check.md`(3)｜`OBM/model.env` 火山｜`OBM/feishu-gsb.toml` 飞书。合规占位符：harbor-sota 的 `${OPENAI_API_KEY}`/`${JUDGE_GATEWAY}` 逐字保留。

## 9 Git 与约束
SSH（`~/.ssh/id_ed25519`，账号 wzswffhm），绝不 HTTPS；`core.longpaths=true`、`core.autocrlf=false`；`user.name=v_wffanwang`。本机 7897 端口 HTTP 代理。排除 `OBM/.venv/`、`.git-archives/`、`.DS_Store`、`__pycache__/`、`*.pyc`。

## 10 文档纪律与用户偏好
自归纳编号（G1–G6）须标注"归纳编号"；断言"出自规范"前先 grep 原文定位。
用户：中文；结论先行+结构化表格；破坏性操作前说明影响面；直给。**不要自动提交代码**；删除/清理不必逐次确认；凭据受限时先做完工具链而非阻塞等待。
