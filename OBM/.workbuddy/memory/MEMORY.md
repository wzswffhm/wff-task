# 项目长期记忆 — OBM deepSWE 造题流水线（Windows 工作站）

## 环境前提
- 本机 Windows + Python 3.13（managed：`C:\Users\Administrator\.workbuddy\binaries\python\versions\3.13.12\python.exe`）。
- **WSL Docker 自 2026-09-29 起不可用**：`wsl.exe` 被 WorkBuddy 安全策略列入程序黑名单（Bash 与 PowerShell 均被拦，**不可绕过、不可重试**），且本机未装 Docker Desktop。此前（09-28）WSL docker 29.1.3 可用，离线构建 / verifier 判分 / 本地链路彩排都在那里跑；现在这些环节全部阻塞，须请用户在「安全中心 → 命令安全 → 程序黑名单」移除 wsl.exe 后恢复。基础镜像 `python:3.12@sha256:4d1ca…` 此前已拉取。
- **网络实况**：GitHub / codeload **不可达**；可达 = gitee.com（`gitee.com/mirrors/<repo>` 可 `git clone`，实测 click/attrs/jsonschema/flask/pydantic 均成功）、pypi.org 及 aliyun pypi 镜像、raw.githubusercontent.com、registry.npmmirror.com。→ 取新仓库源码走 gitee 镜像或 PyPI sdist。
- Trae 无可用无头 CLI（`traecli` 需企业旗舰套餐），且 OBM 规范禁止 Codex 驱动 Trae → no-skill/with-skill 双跑必须由用户在 GUI 手动执行。
- **本机代理链路（EDR/取证相关）**：本机长期运行 **whistle** 调试代理（`C://nvm4w//nodejs//node.exe`，监听 `0.0.0.0:8899`）与 Edge 扩展 **Proxy SwitchyOmega 3 (ZeroOmega)**（profile 指向 `localhost:8899`）。浏览器流量经它们出站时会以 **`node.exe`** 进程身份出现在 EDR/防火墙日志里 —— 排查“node.exe 访问某域名”类告警时，先看 Edge 历史与 SwitchyOmega 配置，再判断是否与本 Agent 有关。
- 运行 skill 脚本时 cwd 必须是 skill 根目录（脚本内部相对导入 + 相对 references）。

## 本地 SWE 题库的三个作用（不是"参考答案库"）
- **`Benchmark/` 下现有五个官方 benchmark 仓库**（2026-09-28 用户手动更新）：`deep-swe-main`(113 题，含真正的 `tasks/manifest.json`)、`frontier-swe-v2-main`(34)、`ProgramBench-main`、`swe-marathon-main`(22)、`terminal-bench-main`(68)。旧的 `deep-swe-prompts`（仅题面）已不在。新 manifest 的 **113 个 task_id 与 `benchmark_tasks.json` 完全一致** → validator 映射仍有效；语言分布 TS 35 / Python 34 / Go 34 / Rust 5 / JS 5。
- `Benchmark/deep-swe-main/tasks/<task>/` = 官方**完整**题：`instruction.md` + `task.toml`(metadata.category / repository_url / base_commit_hash / verifier 配置) + `environment/` + **`solution/`** + **`tests/`**。`task.toml` 是 `domain`（如 `deepSWE/feature_request`）与 `related_question` 的权威来源。选型/校准/去重只读 `instruction.md` 与 `manifest.json`；**`solution/`、`tests/` 严禁读**。
- 三大用途：①**选型发散源**（挑 `related_question`，新题对标官方某题考察的能力）②**难度/形态校准**（看官方题面的契约密度、环境与 verifier 设定）③**去重召回语料**（`check_scene_overlap.py --benchmark-root Benchmark/deep-swe-main/tasks` 算相似度）。
- ⚠️ **`deep-swe-main` 的 `solution/`、`tests/` 严禁用于造题**——读了即触发拒收项"从公开 commit/PR 倒推"与"Verifier 只是复制已有 tests"。本项目全程未读取。
- 离线校验用 `skills/obm-task-production/proposal_validator/benchmark_tasks.json`（上面 task.toml 的映射快照，`validate_proposals.py --mapping` 据此校验 domain/related_question，无需联网）。
- 与另外两处资源的区别：**飞书共享题面库**=本团队已生产 proposal 的跨题去重语料；**`work/upstream/<repo>/`**=待改造的上游仓库源码（真正写代码处，现有 diskcache 与 marshmallow 两个全量克隆）。题库只提供"对标 + 去重"，不提供源码，也不进交付 ZIP。

## 飞书共享题面库（去重前置门槛，硬要求）
- 坐标：base_token `NqtYbxHF1aEYrNsyJSRcUFvMnbe`，table_id `tblk47ilQNyL7Aim`。
- **读回值为「不重复」之前，禁止创建正式题包与 Trae 工作空间**。必须先用 `auth status --verify` 确认 identity=user & verified，再全量读记录（返回结构是 `data.data` 二维数组，不是 `data.records`）。
- lark-cli 授权：`auth login --domain base --no-wait --json` 拿 device_code（**10 分钟有效**）→ 用户扫码 → `auth login --device-code <code>`。
- 写入字段：题目编号/题面/核心场景/对比题面/去重判断(不重复|疑似重复|重复)/判断依据；标注员填 `wff`（openId `ou_35041bb28c45c5be1213b2b1af040d90`）。
- **该 Base 只有一张表**（就是 scene_dedup 表），submission 表在别处尚未定位。scene_dedup：base `NqtYbxHF1aEYrNsyJSRcUFvMnbe` / table `tblk47ilQNyL7Aim` / view `vewF5fmGFr`（`base +view-list` 取）；字段 id：核心场景 `fldAdsWFYl`、对比题面 `fldztVYa9n`、去重判断 `fld8pud4aQ`、判断依据 `fldrnPrFjg`、标注员 `fldBCUsfKv`、题目编号 `fldetsVKw3`、题面 `fldsetqPgK`。导出快照见 `work/feishu-dedup-scan.ndjson`（101 条，rev 130）。
- 去重双写入口：`register_scene_dedup.py --root . --reservation-id <id> --conclusion distinct --review-file <scene-overlap-review.md> --scene-profile <scene-profile.json> --config ./feishu-gsb.toml`，先 `--dry-run` 核对。成功即把登记表推到 `candidate`。
- `check_scene_overlap.py` 只做文本召回、不是判重器：实测最高分常在 0.08～0.16 的噪声区间，必须人工做八维比较 + **改名测试**。已知高占用方向：租约/所有权/fencing、缓存新鲜度状态机、快照与代际、解析/AST、时区、Unicode 断行、任务队列死信。相对空白：数值/符号计算、几何、共识协议、访问控制策略执行。

## Windows 上 OBM 题包打包的四个硬坑
1. **可执行位**：Windows `os.chmod(0o755)` 不生效，`st_mode` 恒 0o666。直接对目录跑 `check_package.py` 时 test.sh/grader.py 的 executable 子项必 FAIL（环境限制，非缺陷）；官方 `build_delivery_zip.py` 以 `path.stat().st_mode` 写归档，Windows 上会把 0o666 存进 ZIP。解决：**用 Docker python 容器挂载项目根复跑 check_package.py**（`MSYS_NO_PATHCONV=1` 必须设，否则 `-w /w` 被转成 `W:/`），或在 Windows 用 `work/make_delivery_zip.py`（强制 test.sh/grader.py = 0o755）。
2. **upstream.tar.gz 单一顶层目录**：必须用 `git archive --prefix=<repo>/ <commit>`，否则 safe_extract 因"不止一个顶层目录"报错。
3. **git archive 在 autocrlf=true 的 Windows 仓库输出 CRLF**：sources/app、upstream.tar.gz 全 CRLF，而补丁为 LF，容器内（无 autocrlf）`git apply` 报 "patch failed"。必须 `git -c core.autocrlf=false archive`，diff 类补丁生成后做 CRLF→LF 归一。**Git Bash 的 `cat -A` 会骗人**（MSYS 文本模式吞 \r）；核对行尾必须用 Python `open('rb')` 或容器内 `od -c`。
4. **构建上下文 exec 位污染 git 索引**：Windows checkout 的部分文件被标 100755，容器内 `git add` 记进索引，`git apply` 报 "has type 100755, expected 100644"。app Dockerfile 需 `git config core.filemode false` + `git ls-files -z | xargs -0 git update-index --chmod=-x` 后再 commit。
5. **收尾链的 check_package 两处调用点在 Windows 必挂**：① `capture_final_check.py` 对题包目录质检、② `build_delivery_zip.py` 构建后的 ZIP 自检（safe_extract 重放 mode 后宿主机仍读 0o666）。**已修**（2026-09-29）：两脚本均加 Windows 容器分支——`check_package_command()` / `run_package_checker()` 用 `docker run python@sha256:4d1ca…`（task、ZIP 目录、skill 根挂载进容器；`OBM_CHECK_IMAGE` 可覆盖镜像）；`archive_task()` Windows 分支对文件 mode 规范化（test.sh/grader.py 强制 0o755、其余 0o644）。此后 finalize_seed_delivery.py 可在 Windows 全链直跑。

## Seed 判分链路（verify_agent_patch + grader）
- `verify_agent_patch.py` 只把 `--patch` 复制到 `artifacts/model.patch`，**不做应用**；补丁应用必须由 grader 在容器内对 `/app` 执行 `git apply /logs/artifacts/model.patch`（官方 deepSWE 设计）。pycasbin 题的 grader.py 已实现 `prepare_app()`：patch 缺失/为空→跳过；应用失败→结构化 `status=patch_apply_failed` + reward=0。漏掉这步会让 with-skill 恒 reward=0。
- E2E 验证法：用原始 app 镜像 + verifier，挂载 `artifacts/model.patch`（空=NOP 应 0；solution.patch=ORACLE 应 1）。
- Seed 实验的 Windows 垫片：`work/2026-09-29-1-pycasbin-decision-trace/compat/sitecustomize.py`（PYTHONPATH 注入）：`os.getuid/getgid=0`（docker --user）、`os.killpg/setsid` stub、`signal.SIGKILL=SIGTERM`。`start_new_session=True` Windows 可用。

## 复用脚本/工具
- `work/win_skill_run.py`：**通用** Windows 启动器，注入 fcntl stub + 把目标脚本目录加入 sys.path。用法 `python work/win_skill_run.py skills/<skill>/scripts/xxx.py <args...>`，cwd 保持项目根（脚本用 `--root .`）。旧的 `work/win_task_registry.py` 只指向旧的 `obm-task-production`，已弃用。
- `work/larkcli_shim/` + `.venv/Scripts/lark-cli-shim.exe`：**lark-cli 的 Windows 转发 exe**（`pip install ./work/larkcli_shim` 生成）。必须用它而**不能**用 `lark-cli.cmd`——Python 执行 .cmd 会经 cmd.exe，URL 里的 `&` 被当命令分隔符（`url-resolve` rc=1），`--json` 载荷被拆成位置参数。shim 直接调 `node.exe .../@larksuite/cli/scripts/run.js`，参数原样传递。`feishu-gsb.toml` 的 `[cli].path` 指向它。
- `work/make_delivery_zip.py`：Windows 下强制 exec 位出 ZIP（替代官方 build_delivery_zip）。
- `run_local_verifier.py`（各题工作区自带）：build 干净树 + 注入 verifier tests + 跑 grader.py，验证 NOP=0 / ORACLE=1。
- safe-delete 常拦截 `rmtree`/`rm -rf` → 改用带时间戳新目录或 copytree(dirs_exist_ok=True)。

## obm-task-production-openai skill 的 Windows 实况
- 项目根 `model.env`（`key=` / `url=`）与 `feishu-gsb.toml` 已就位；两者都不进题包。
- **2026-09-29-1 pycasbin-decision-trace 已交付就绪**：正式 ZIP `output/deepSWE_2026-09-29-1-pycasbin-decision-trace.zip`（sha256 `89f30ad5db6bf87d0d8c0cc0db0a32b296b4208bd85b70c539744d6eb112fe84`）；质检证据 `work/2026-09-29-1-pycasbin-decision-trace/final-check/FINAL_CHECK.{json,png,txt}`（ok=true）；实验证据 `agent-runs-3/`（no-skill 65 轮 reward=0 / with-skill 57 轮 reward=1）。
- **飞书提交表（正确坐标，2026-09-29 用户提供）**：wiki 节点 `R9dbw2Dm6ioXbrkefZScH1dFnfk` → base `ZqH1bHq4AaTIqrsg4sfctdknnuf`（vcnuhsx1gwu0 域）/ table `tblEzvAKrSNJNkwi`；字段：题目名or编号(text)、备注(text)、关联benchmark(select=deepSWE)、甲方质检结果(select，质检方填)、最终检测skill的检测结果截图(attachment fldGG5rJo1)、交付压缩包(attachment fldIqaadoN)、状态(select：已领取/待质检/已同步/待返修/驳回/质检通过/内部质检通过)、驳回理由(text)、标注人(user)。惯例：题目名=完整 ZIP 名。**已创建记录 reczz28HEThWtwwu**（题目名=deepSWE_2026-09-29-1-pycasbin-decision-trace、状态=待质检、标注人=wff、备注含实验摘要+ZIP sha256），但**附件上传被拒**（user 身份 800020812——记录可写、media upload 被高级权限单独控制；bot 缺 scope）→ 待用户手动拖入两个附件（ZIP=`output/deepSWE_2026-09-29-1-pycasbin-decision-trace.zip`、截图=`work/2026-09-29-1-pycasbin-decision-trace/final-check/FINAL_CHECK.png`）或提权后由我重试。旧 base `NTsFbkdhbasuCKs1m86cBiI9nwd`（tbldSJPkt98phRcS）是另一个只有读权限的空表，非提交表。
- `feishu-gsb.toml` 值**必须用正斜杠**：`parse_toml_subset` 走 `ast.literal_eval`，Windows 反斜杠会被当转义（`\U` 直接 ValueError）。
- 已修 `skills/obm-task-production-openai/scripts/register_scene_dedup.py` 的 `run_cli`：补 `encoding="utf-8", errors="replace"`（原实现在 `PYTHONUTF8=1` 下用 utf-8 解码 lark-cli 的 GBK stderr 会崩 reader 线程）。该 skill 是外部来源、非 agent_created，故直接编辑文件而非 SkillManage。
- 已修 `capture_final_check.py` 渲染（2026-09-29）：① `font()` 原只枚举 macOS/Linux 字体，Windows 上回退 PIL 默认位图字体 → **中文全变方块乱码**；已加 `C:/Windows/Fonts/msyh.ttc` 等候选。② 版式对齐官方样例：4 张指标卡（"人工复核提醒"= [WARN] 计数，summary 新增 `warnings` 列表；**"需要处理"区段仅在 warnings 非空时渲染**，内容取真实检查输出）、Seed 面板 F2P/P2P 明细从 `<side>/verification/VERIFIER_RUN.log` 的 JSON 块解析（`load_verifier_stats()`：f2p/p2p 的 passed/expected；no-skill 实测 474/514、with-skill 514/514）。**注意**：FINAL_CHECK.png 变更后必须重跑 finalize（screenshot_sha256 绑定校验），交付 ZIP 不含 PNG、sha256 不受影响。归档链：final-check-run1-failed（exec位）/ run2-garbled-png / run3（F2P??）/ run4（轮次回退版）。
- **飞书提交表操作顺序（用户明示）**：状态字段一旦设为「待质检」其他字段即被锁定 → 必须**先填全部字段+附件，最后一步才改状态**。**2026-09-29-1 已完成提交**：记录 `reczz28HEThWtwwu` 状态=待质检；ZIP 附件 sha256 经下载核验与本地 `89f30ad5…` 逐字节一致；截图 173,043 bytes=本地最终版；备注被用户编辑时清空且锁定无法补（非必填，不影响）。附件下载核验命令：`base +record-download-attachment --file-token <token> --output <dir> --overwrite`。
- 该 skill 判断 `.venv/bin/python`（Windows 实为 `.venv/Scripts/python.exe`）→ `OBM_PYTHON` 需显式给实际路径。项目 venv 在 `.venv`（含 pytest 8.4.1 / simpleeval / wcmatch / larkcli-shim）。

## check_package.py deepSWE 硬性要求（易漏）
- 必交付：sources/app/{Dockerfile,upstream.tar.gz}、sources/README.md、sources/skill/SKILL.md、sources/verifier/{Dockerfile,test.sh(可执行),grader.py(可执行),config.json,test.patch}。
- config.json 字段名必须是 `f2p_node_ids` / `p2p_node_ids`（非空）；基础镜像按 `@sha256:` digest 固定；Dockerfile 不得含 apt-get/git clone/curl/wget，pip install 须 `--no-index`。
