# wfflab__wsparse-215 返修现场

本目录保存 215 号槽位替换（`wfmt` → `wsparse`）的跑分现场、控制证据与归档脚本。
它不属于交付题包，改动这里不会影响 Harbor 的 task checksum。

## 为什么替换 215

原 215（`wfflab__wfmt-215`）是二进制容器格式题，其验收条款全是平台无关的 Python
语义，题包自己的 `verifier/WINDOWS_VALUE.md` 就写着「不主张 Windows」，属于甲方
第七条所指的「Windows 价值缺失」，返修原因要求「改用依赖 Windows 机制的题目」。

新的 215 建立在**公开上游缺陷**上：CPython issue 39910《os.ftruncate on Windows
should be sparse》。容器内实测该缺陷在 Python 3.12.9 上依然存在：

```
os.truncate(64MB): st_size=67108864 compressed=67108864 sparse_bit=False
fsutil queryflag: This file is NOT set as sparse
```

同一行代码在 Linux 上扩展天然稀疏，因此该缺陷**只在 Windows/NTFS 上成立**。
issue 给出的正确做法（aria2 `src/AbstractDiskWriter.cc`）是先发 `FSCTL_SET_SPARSE`
再 seek + `SetEndOfFile`。

## 目录

| 路径 | 内容 |
|---|---|
| `harbor_agent/wsparse_model_agent.py` | 宿主侧 Harbor agent：在 Windows 容器里驱动候选模型（改自同批 219 的 agent，仅换名） |
| `run_wsparse_controls.py` | Golden / no-change 各 3 轮 **Harbor 原生** job |
| `run_wsparse_model_rounds.py` | Qwen×3 + Opus×3 模型轮（甲方口径：不跑 GLM/Kimi） |
| `assemble_wsparse_harbor_jobs.py` | 把 Harbor trial 组装成交付包 `jobs/` |
| `controls/`、`model-rounds/` | 跑分产物；`jobs-dir` 刻意放在题包**外**，避免污染 task checksum |
| `dirhash-probe.py` | 探测 Harbor `Task.checksum` 口径的临时脚本 |

## 判分链路与实测结果

| 场景 | 期望 | 实测 |
|---|---|---|
| Oracle ×3 | 1 | 1 / 1 / 1 |
| no-change ×3 | 0 | 0 / 0 / 0 |
| Qwen ×3 | — | 见 `model-rounds/rounds_summary.json` |
| Opus ×3 | — | 见 `model-rounds/rounds_summary.json` |

控制组与模型轮共用同一个 task checksum，`jobs/_index/assembly_report.json` 记录了
归档时的一致性检查结果。

## 踩过的四个基础设施坑（都已在脚本里修掉）

1. **`hcsshim::ImportLayer` 拒绝稀疏文件**
   最初把稀疏样本放在镜像构建阶段生成，该层提交时失败：
   `hcsshim::ImportLayer failed in Win32: The system cannot find the path specified. (0x3)`。
   稀疏性属于磁盘布局而非字节内容，无法穿过 zip / 构建上下文 / 容器层。
   改为不随包提供稀疏样本，由隐藏套件用自己的句柄创建全部 fixture。

2. **隐藏套件注入路径**
   Harbor 只在 verifier 阶段把 `tests/` 挂到 `C:\tests`，**不挂** `verifier/`。
   `tests/run_tests.ps1` 的候选根因此必须包含 `C:\tests`，套件也要随包发到
   `tests/test_wsparse_semantics.py`（与 `verifier/tests/` 那份逐字节一致）。

3. **Oracle 载荷必须随 `solution/` 交付**
   Harbor 的 oracle agent 只上传 `solution/`。参考实现因此放在
   `solution/reference/wsparse/`；`solve.ps1` 同时要把工作目录解析到 `C:\testbed`。

4. **Windows 注册表代理劫持模型请求**
   `HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings` 里
   `ProxyServer=127.0.0.1:7897`（`ProxyEnable=0`）。Python 的 `urllib` 读注册表时
   忽略 `ProxyEnable`，于是 Harbor 的模型 agent 全部经代理出网，Opus 三轮都拿到
   `http_502 upstream API error: 所有凭据均已禁用（4/16）`。同一把 key 直连返回 200。
   模型轮脚本因此显式设置 `no_proxy=*` / `NO_PROXY=*`。

## 题面与模块注释的去引导

甲方口径：答案不得写在题面上，不得有引导性注释。第一版题面点了 `DeviceIoControl`、
`FSCTL_SET_SPARSE`、`FSCTL_QUERY_ALLOCATED_RANGES`、`FSCTL_SET_ZERO_DATA` 以及
`fsutil` 的具体用法；缺陷模块的 `_winapi.py` 里还留着一个恰好能解决问题的
`get_compressed_file_size()`，其 docstring 明说「稀疏文件上这个数更小」。这些都已清除：

* 题面只保留可验证的**行为要求**（「必须在 NTFS 上把文件标记为稀疏文件」「占用统计必须
  反映真实簇分配」）与平台范围声明，不再出现任何控制码名、工具名或实现步骤；
* 原 E 条款第二条「必须先释放已分配区域再置位标志」是实现步骤，已删除；
* `_winapi.py` 只留 `is_windows()` 与 `SPARSE_ATTRIBUTE`，可复用的物理大小查询已移除；
* 可见冒烟测试的 docstring 不再暗示「需要检查文件系统布局」。

机制锚点（`metadata/windows_mechanism.json`）锚定的仍是题面里的行为条款，不依赖任何被
删除的实现细节；清除后已逐条复核，五条锚点与排他声明、环境层锚点全部仍在。

## 与甲方自检口径的对齐（2026-10-14）

`harbor-windows/_reference/windows-harbor-qc` 首次跑出 FAIL，逐条处理后：

| 自检报错 | 处置 |
|---|---|
| `Task has no pinned Docker image` | **`task.toml` 携带 `docker_image`**（甲方 2026-10-14 确认该字段必须存在：交付自检与随包 QC 都读它），且与 `environment/Dockerfile` 的 `FROM` 逐字一致。我方 `validate_package.py` 的对应规则同步为「必须有且必须钉住 digest」 |
| `model-result.json alias/model does not match opus` | **改模型名**：Harbor 的 `ALIASES` 只认 `claude-opus-5`，原先传的 `claude-opus-4-8` 不在表内。模型轮改为 `claude-opus-5`（该端点上两个名字都返回 200） |
| `glm requires exactly 1 runs, got 0` / `kimi ... got 0` | **改 `REQUIRED_COUNTS`** 为 `{"qwen": 3, "opus": 3}` |
| `jobs/ must contain exactly 14 ... got 12` | **改检查器**：期望数量改为按 `REQUIRED_COUNTS` 推导（`sum(REQUIRED_COUNTS) + 3 Oracle + 3 NOP` = 12），不再硬编码 14 |
| 十项人工质量复核 `BLOCKED` | 其中 8 项可由本题证据支撑；`wip94_complete` 与 `dynamic_d01_d20_complete` 属于批次级采购手册审计，不在单题替换范围内，保留 BLOCKED 并注明 |

改动同时同步到 `references/rule-matrix.md` 与 `README.md` 的文字描述，避免代码与文档不一致。
