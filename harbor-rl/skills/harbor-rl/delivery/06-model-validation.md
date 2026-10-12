# 三模型难度验证（G5）

## 1. 口径（冻结，不得自行替换）

| 项 | 值 |
|---|---|
| 运行框架 | **Claude code** |
| 待测模型 | `gpt-5.6-sol`、`claude-opus-4-8`、`qwen3.8-max0902` |
| 裁判模型 | **`qwen3.7-plus`** |
| 分数归一化 | 所有题目满分归一化为 **1.0** |
| 次数 | **每种模型跑 1 次**，取三模型平均分 |
| 通过标准 | 三模型平均分 **< 0.7**，**且至少有一个模型有得分**（避免全 0 的"死题"） |
| 交附件 | **模型产物 + 跑分轨迹须随题提交**，用于验证难度要求 |

## 2. 难度等级区间（达标后归档）

| 等级 | 平均分区间 | 产量占比 |
|---|---|---|
| A1 基础/易 | 0.6 ≤ 得分 < 0.7 | 20% |
| A2 进阶/中 | 0.5 ≤ 得分 < 0.6 | 60% |
| A3 高难/难 | 得分 < 0.5 | 20% |

> 参考答案得分 **> 0.85** **且** 三模型平均分 **< 0.7**。

## 3. 执行流程

```
1) 冻结口径（模型标识、框架版本、judge 版本、采样参数、timeout）
2) 逐题执行：三模型 × 1 次，各自产出交付物
3) 对每份产物跑判分：rewardkit（claude-code agent judge，裁判 qwen3.7-plus）
4) 逐题计算三模型平均分；同时记录每模型是否 >0
5) 与目标等级区间比对；核对"至少一个模型得分"
6) 归档跑分产物与轨迹
```

### 执行要点

- **评分行为随 claude-code CLI 版本漂移** → 必须锁 `2.1.114`；版本或平台变更后**不得与旧结果直接比较**，需要用于准入时应**统一回刷**。
- **`verifier_error = 1` 的运行不是"0 分"**，而是"评分不可信"，必须重跑；不得纳入难度统计。
- 难度未达标 → **重做题目或调整定级后重跑**，**不得伪装跑分**。
- **本地跑分必须让 WSL 发行版保持"有客户端附着"**：WSL 发行版在最后一个 `wsl.exe` 客户端脱离后会**空闲关机**，杀掉全部进程与容器（docker 报 `Exited (255)`；实测脱离后数分钟到数十分钟被回收）。judge 逐条串行，36 条常需 60min+，所以长跑必须先解决"谁来持有客户端"。三种持有方式的实测结论：

  | 方式 | 结论 |
  |---|---|
  | 前台 `sleep` 循环持有 | ❌ 用户一发消息即打断工具调用 → 客户端脱离 → 整轮跑废 |
  | `run_in_background` hold | ⚠️ 只在同一回合内有效；**回合结束 / 会话被压缩 / 用户新消息都可能回收该后台任务** → 同样跑废（已三次实证） |
  | **Windows 计划任务常驻 keeper** | ✅ **正解**，跨会话、跨回合存活 |

  `.wslconfig` 的 `vmIdleTimeout=2147483647` **挡不住**发行版级空闲关机，别指望它。

  **keeper 建立（一次性，务必"双 holder + 自愈"）**：单个 keeper 仍会偶发消失（149 实证：一个 keeper 存活 3.5h 后死亡，
  13 秒空隙即触发关机、带走正在判分的容器）。因此**注册两个独立任务**，并给触发器加**每分钟重复**做自愈：
  ```powershell
  $exe = "$env:SystemRoot\System32\wsl.exe"
  $arg = '-d Ubuntu -u root -e sleep infinity'
  foreach ($name in @('wsl-keeper-ubuntu','wsl-keeper-ubuntu-b')) {
    $a = New-ScheduledTaskAction -Execute $exe -Argument $arg
    $t1 = New-ScheduledTaskTrigger -AtStartup
    $t2 = New-ScheduledTaskTrigger -AtLogOn
    $t3 = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 1) -RepetitionDuration (New-TimeSpan -Days 3650)
    $s = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
         -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew `
         -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -StartWhenAvailable
    Register-ScheduledTask -TaskName $name -Action $a -Trigger @($t1,$t2,$t3) -Settings $s -RunLevel Highest -Force
    Start-ScheduledTask -TaskName $name
  }
  ```
  校验：`wsl -d Ubuntu -u root -- bash -c "ps -eo pid,etime,args | grep 'sleep infinity' | grep -v grep"` **应有 2 条**且 `etime` 持续增长
  （只有 1 条 = 已有一个死了，`IgnoreNew` 会让重复触发补不进来，需先 `Stop-ScheduledTask` 再 `Start-ScheduledTask`）。
  ⚠️ 有的会话里 **PowerShell 工具不回 stdout（只给 exit code）**：把脚本写成 `.ps1` 用 `Register-ScheduledTask`，
  并在脚本末尾 `| Out-File <文件>`，再用 Read 读结果；不要依赖工具直接显示。

  **编排器用 `systemd-run` 托管**（`--collect --setenv=HOME=/home/wff --setenv=LANG=C`），脱离调用方 shell 生命周期；**必须以 root 运行**——`--uid=wff` 会因 `open /home/wff/.docker/buildx/current: permission denied`、drvfs 文件属主等原因在 3 秒内秒退（现象：`ALL LAUNCHED` 后立刻 `ALL DONE`、无容器）。

  判断"是否发生过关机"看 `/proc/1` 的 mtime，**别看 `uptime`/`boot_id`**——它们读的是共享内核，发行版重启不重置。

- **★ 单试次分数必须先判"真弱分 / 故障分"，再入均分**（149 实证：gpt-5.6-sol 两次得 0.0，均为基础设施故障，不是弱分）：
  1. **`terminal_reason: "completed"` 不可信**——必须打开 `agent/claude-code.txt`，看**最后一条 `"type":"result"` 记录**的
     `is_error` 与 `result` 文本；再看最后一条 assistant 消息。若为 `API Error: 5xx ...`（如
     `litellm.ServiceUnavailableError ... Model Group=<模型>`）或 `API Error: Unable to connect to API (ConnectionRefused)`
     → 该试次是**故障分，作废补跑**。
  2. 交叉证据：`artifacts/manifest.json` 里交付物 `"status": "failed"`；且 agent 全程工具调用**完全没有 `Write`/`Edit`**
     （只有 Read/Glob/Bash/TodoWrite）→ 模型根本没产出。
  3. **有效弱分的长相**：交付物齐备 + 逐条判据有区分度（部分 1、部分 0），而不是 35/36 全 0 只靠一条"不得伪造数据"类负向判据得分。
  4. 补跑用独立 tag（如 `TAG=fix5d`）生成新 trial 目录，别覆盖原目录，便于留证。
  5. **"交付物齐备但仍在收尾时挂掉"也是一种故障分**：149 实证——`manifest` 7 项全 `ok`、文件时间戳完整，
     但 CLI 末条 `result.is_error=true` + `ConnectionRefused`（本地 LiteLLM 桥上挂），harbor 判 `UnknownApiError`
     并**直接中止 trial、verifier 根本没跑**（只留 fail-closed 占位）。这类"看起来快要完成"的轮次**不能当弱分**；
     **好消息是它的交付物可用**——直接走下面的"复用交付物重判"即可拿到有效分，无需再让 agent 重跑。
  > 判分链路正常与否另看 `verifier/reward.json`：`criteria_counted=36` 且 `verifier_error=0` 只说明**判官跑通了**，
  > **不能**说明候选交付正常。
- **★ 判分中途失败：先看 `reward_exit_message.json`，别猜题目**（149 实证：nop 判分跑到 R20 被踢出，`criteria_counted=0`）：
  1. 读 `<trial>/verifier/reward_exit_message.json`：
     - `exit_code = "judge:scorer_error"` → **判官侧失败**（凭据/网络/上游），题目本身没问题；
     - `exit_code = "test:failed"` / `"agent:..."` → 另按对应侧排查。
  2. `judge:scorer_error` 时读 `verifier/test-stdout.txt` 尾部，通常有 rewardkit 抛出的原始 `claude` 报错 JSON。常见两类：
     - **`"api_error_status":401 ... "API-key is block[ed]"`** → **judge key 被平台封禁**（不是限流）。立刻用 `curl` 直测：
       `POST <judge_base>/v1/messages`（`x-api-key`，`model=qwen3.7-plus`）——若 401 即该 key 已废；**换 key 重跑即可**，
       不必改题、不必重跑 agent。注意判官模型与候选模型**都要测**（一次 block 会同时命中两者）。
     - `429 / overloaded / timeout` → 限流/慢响应，属可重试类，换独立 key 降压后重跑。
  3. 判分失败会写 **fail-closed 占位** `reward.json`（`criteria_counted=0 / verifier_error=1`）——**这不是 0 分**，
     不要入均分，直接重跑该试次（`-a nop --mounts` 复用交付物即可，见下文）。
- **同一 judge key 多路并发会互相拖死**：judge 为**逐条串行** `claude -p`；若同 key 上还叠着候选模型 agent 的流量，个别判据可卡住数十分钟（实测一条判据卡 52min）。多试次并发时，**候选模型 agent 应换用独立 key**（judge 仍用原 key），可显著降压。
- **"agent 未退出"≠"卡死"**：先看容器内 `/logs/agent/claude-code.txt` 是否仍在增长、`/app/output` 是否已产出交付物；若产出完整而 CLI 迟迟不退，属上游慢响应/长迭代，勿轻易杀进程。

### 复用已记录的交付物重判（省掉 agent 段，规避端点故障）

当某试次的 agent 段因基础设施故障中止、但**交付物已完整落盘**时，不必让 agent 从头重跑，直接复用交付物判分：

1. **`harbor trial regrade <源trial目录> -p <task> [--ve ...]`**（0.22.0 自带）——复用已记录试次的 agent 日志 + 交付物，只重跑 verifier。
   **前提**：① 源试次有可读 `result.json`（异常中止的轮次往往没有，会被拒）；② 题目为**单步**且 verifier 解析为
   `environment_mode = "separate"`。先判定：
   ```bash
   <harbor-venv>/bin/python -c "
   from pathlib import Path
   from harbor.models.task.config import TaskConfig
   from harbor.trial.regrade import resolve_task_verifier_mode, check_task_regradable
   td=Path('<task_dir>'); cfg=TaskConfig.model_validate_toml((td/'task.toml').read_text())
   print(resolve_task_verifier_mode(cfg)); print(check_task_regradable(td))"
   ```
   返回 `SHARED` 或非 None 的错误串 → regrade **不可用**（149 即 SHARED）。
2. **SHARED 模式的等价做法（已验证可行）**：`-a nop` + bind mount 把交付物塞进容器 `/app/output`，只跑真判分。
   ```bash
   harbor trial start -p <task_dir> -a nop --trials-dir <out> \
     --mounts '[{"type":"bind","source":"<该模型真实交付物目录>","target":"/app/output"}]' \
     --ve JUDGE_API_KEY=... --ve JUDGE_BASE_URL=... --ve JUDGE_MODEL=... \
     --ve JUDGE_PROVIDER=anthropic --ve JUDGE_API_PROTOCOL=anthropic
   ```
   前提：判分脚本读 `/app/output`（平台模板 `rewardkit /tests --workspace /app` 即是）；源目录按输出根直接放齐
   全部交付物（如 `FIN3-…_xxx.md`、`_reproduce.py`、`_charts/*.png`）。
   校验：`docker inspect -f '{{range .Mounts}}{{.Source}} -> {{.Destination}}{{"\n"}}{{end}}' <容器>` 有该 bind，
   容器内 `ls /app/output` 文件齐，且 `ps -eo args | grep 'claude -p'` 出现判官。
   > 该法**不经过模型端点**（无 agent、无 LiteLLM 桥），不受上游限流/抖动影响，是补分最稳的路径；
   > 归档时须注明"verifier-only 重判（agent 段因基础设施故障中止，交付物为该模型真实产出）"。
   - 相关：claude-code 跑 **gpt-5.6-sol** 只能经本地 LiteLLM 桥（上游 `api.ebondai.com` **不允许 `/v1/messages`，403**），
     桥是单点故障 → 长跑应加 port-4000 watchdog 自动重启，或改走上面的 verifier-only 路径。
   > **脚本化重判的坑（150 实证）**：定位候选产物时若写
   > `find <trial> -maxdepth 3 -path '*/artifacts/app/output'` 会**永远返回空**——实际层级是
   > `<trial>/FIN3-…__xxxx/artifacts/app/output`（4 层）。用
   > `find <trial> -type d -path '*/artifacts/app/output' | head -1`，不要加 `-maxdepth`。
   > 失败现象是判分脚本秒退并打印 `ERR: no candidate output`，别误判成 harbor 故障。

### G5 档位落定与判分噪声（务必按"交付题包上的实测均分"落档）

- 判官是 LLM **逐条采样**：**同一批候选交付物、同一套权重，两轮判分**的单模型分可差 **±0.05**、三模型均分可差 **≈0.04**；
  甚至只改一条 binary 判据的**文字表述**（口径不变）也会带来同量级波动。
- 因此 **`metadata.difficulty` 必须按"交付题包（最终版）上实测出来的那个均分"落档**，不能按设计目标或更早一轮的数字：
  区间 A1∈[0.6,0.7) / A2∈[0.5,0.6) / A3<0.5，**申报档必须包含所报均分**（06 §5 自检脚本机械核验 `lo <= mean < hi`）。
- 均分落在档位**边界附近**（如 0.60±0.03）时：如实记录两轮数字与差值来源（哪条判据、判分噪声），
  **挑一份"好看的"报上去属伪装跑分**。150 实证：v2 轮 0.585606（A2）／final 重判轮 0.621970（A1），
  交付以 final 轮为准 → 申报 **A1**，并在交付文档披露两轮对照。

## 4. 归档要求

每题留存：

```
<题包>/model_runs/
├── gpt-5.6-sol/     { deliverables/, trace/, reward.json, reward-details.json }
├── claude-opus-4-8/ { … }
└── qwen3.8-max0902/ { … }

<题包>/model_runs/summary.json
```

`summary.json` 建议结构：

```json
{
  "task_id": "FIN1-SKL-DEP-001",
  "frozen": {
    "framework": "claude-code",
    "framework_version": "2.1.114",
    "rewardkit_version": "0.1.7",
    "judge_model": "qwen3.7-plus",
    "sample_params": {"temperature": null, "note": "以平台冻结值为准"}
  },
  "runs": [
    {"model": "gpt-5.6-sol",        "reward": 0.42, "verifier_error": 0, "scored": true},
    {"model": "claude-opus-4-8",    "reward": 0.61, "verifier_error": 0, "scored": true},
    {"model": "qwen3.8-max0902",    "reward": 0.33, "verifier_error": 0, "scored": true}
  ],
  "mean": 0.453,
  "any_model_scored": true,
  "declared_difficulty": "A3",
  "gate_pass": true
}
```

## 5. 结果自查脚本

用于跑分完成后机械核验门槛（不代跑模型，只校验汇总结果）：

```python
# check_model_gates.py — 用法: python3 check_model_gates.py summary.json
import json, sys

BANDS = {"A1": (0.60, 0.70), "A2": (0.50, 0.60), "A3": (0.0, 0.50)}

def main(path):
    s = json.load(open(path, encoding="utf-8"))
    runs = [r for r in s["runs"] if r.get("verifier_error", 1) == 0]
    bad = [r["model"] for r in s["runs"] if r.get("verifier_error", 1) != 0]
    if bad:
        print(f"[FAIL] 存在评分不可信(verifier_error=1)的运行，必须重跑: {bad}")
    if not runs:
        print("[FAIL] 无有效运行");  return 1
    mean = sum(r["reward"] for r in runs) / len(runs)
    any_scored = any(r["reward"] > 0 for r in runs)
    lo, hi = BANDS[s["declared_difficulty"]]
    ok_mean = mean < 0.70
    ok_band = lo <= mean < hi
    print(f"三模型均分 = {mean:.3f}  (有效运行 {len(runs)} 次)")
    print(f"至少一个模型有得分: {any_scored}")
    print(f"难度门槛(<0.7): {'PASS' if ok_mean else 'FAIL'}")
    print(f"等级区间 {s['declared_difficulty']} ∈ [{lo},{hi}): {'PASS' if ok_band else 'FAIL'}")
    return 0 if (ok_mean and ok_band and any_scored and not bad) else 1

if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
```

## 6. 与参考答案预检的关系（两道独立的门）

| 门 | 对象 | 标准 | 失败含义 |
|---|---|---|---|
| **golden 预检（G4）** | 参考答案产物 | 主分 **> 0.85** 且 `verifier_error = 0` | **Rubric 写歪**（要求过高/锚点错误/golden 不完整）→ 整题退回重写 |
| **三模型验证（G5）** | 三模型产物 | 均分 **< 0.7** 且至少一个模型有得分 | **难度不达标或过难成死题** → 重做题目或调级重跑 |

两者必须**都过**才可提交。golden 过高而模型也高 → 题目太简单；golden 达标而三模型全 0 → 死题，需降低门槛或补充可得分项。

## 7. 甲方质检的判分复算与独立重算要求（自检必做，冻结自甲方 evidence-checks.md）

### 7.1 计分口径（rewardkit）

```text
Score = ( Σ_{正分项} w_i·v_i − Σ_{negate 项} w_j·(1−v_j) ) / Σ_{正分项} w_i
```

- **negate 条目的 `value = 1.0` 表示"未触发违规"，不是"得了 1 分"**——只按正分项求和会得到 >1 的假值，这是最容易算错的一步；
- likert 归一 `(raw − 1) / 4`（1–5 整数锚点）。

### 7.2 逐条复算与一致性核对（对每个执行体）

1. 读 `reward.json` 的 `reward`；读 `reward-details.json` 的 `reward.criteria[*]`（字段 `id/name/value/raw/weight/description/reasoning`）；
2. 按 7.1 公式复算，必须与 `reward.json` **完全一致**；
3. 逐条比对 `description` 与 `weight` 是否与现行 `tests/rubrics.toml` **完全相同**——不一致说明该轮判分用的不是最终版判据，
   **该轮分数不能作为难度证据，必须重跑判官**（这是甲方"判分未重跑"接受矩阵的红线）；
4. 记录每个执行体的"未满分条目清单"，供口径歧义排查（配合集中度检查）。

### 7.3 "判分未重跑"能否接受（甲方接受矩阵，冻结）

| 情形 | 判定 |
|---|---|
| 判据/权重/金标未变，直接用原判分 | 可接受 |
| 仅调权重，但用**同一批逐条判定**重新聚合、聚合结果可复算一致，且交付文档如实披露 | 可接受（须在报告单列该口径） |
| 判据 description 变了却沿用旧判分（reward-details 与现行 toml 漂移） | **不可接受，必须重跑判官** |
| 题面/材料变了却沿用旧 agent 产物 | **不可接受，必须重跑 agent** |

### 7.4 均值余量

记录三模型均分距 0.7 的余量（如 0.6591 距 0.7 仅 4.1pp）；余量薄时在交付文档提示
**"重跑判官可能越档"**——判官为 LLM 逐条采样，两轮判分均分可差 ≈0.04（见 §3 判分噪声）。

### 7.5 独立重算关键链路（核心原则）

- **不引用金标结论作推导依据**：只读 `environment/input_files/` 自己重建计算，金标仅用于事后对照——否则复算退化成"抄答案"；
- 先找"卡点链路"（1–3 条决定大部分分值）：看交付文档自述的不可省略点 + 集中度检查的判据聚集 + 问"哪个单一判定错了会污染一批下游"；
- 复算产出对照表（复核点 / 材料出处 / 独立复算 / 金标 / 结论），结论只能写「一致 / 不一致 / 口径存疑」，不一致必须给推导过程；
- **复算结果与预期不符时先怀疑自己的实现**（MILP 约束写法、符号方向、百分比/小数单位），再怀疑金标；
- 环境缺库先清代理变量再 `pip install pandas scipy`（否则走不存在的代理）。
