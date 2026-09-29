# 03 · 标准 Harbor Task 构题规范

来源：规范第五章 + 对 `Windows_SWE_d70d30df` 27 题现包的实测分析

---

## 一、固定目录结构

```
<task-id>/
├── task.toml
├── instruction.md
├── environment/
│   ├── Dockerfile
│   └── workspace/          # 初始工作区内容（会被 COPY 到 C:\testbed）
├── solution/
│   └── oracle.patch        # 参考补丁（仅用于 Golden 验证）
└── tests/
    ├── test.ps1            # 验证入口
    ├── grade.py            # 程序化评分
    ├── swelive_spec.json   # 题面/测试元数据（含 F2P/P2P）
    └── test_patch.diff     # 隐藏测试补丁
```

**约束**：
- 默认对接 **Harbor schema 1.3**
- **不得**为了保留旧生产结构在 Task 内新增自定义必需目录或私有字段
- 最终计分集加载和执行的对象**只包含标准 Harbor 题包**

> 平台导入 JSON（`outside_harbor/<task-id>.json`）**不属于** Harbor Task 内部结构，见 `05-delivery-structure.md`。

---

## 二、task.toml 规范

### 身份与版本

```toml
version = "1.0"        # 必须与 task_version 一致；任何影响题面/环境/Solution/Tests/判分的修改必须升级
```

> schema 1.3 下版本以 `task.toml` 的 `version` + 交付清单的 `task_version` + `task_hash` 三元组共同界定。

### 资源与超时

```toml
[agent]
timeout_sec = 172800.0        # 单次端到端评测原则上 ≤ 12 小时（43200s）

[verifier]
timeout_sec = 7200.0

[environment]
docker_image = "<registry>/<repo>:<tag>"
build_timeout_sec = 7200.0
cpus = 8
memory = "16G"
storage = "30G"
```

> ⚠️ 规范要求**单次端到端评测原则上不超过 12 小时**。若 `agent.timeout_sec` 超过 43200，
> 必须在 `delivery-extras/tasks/<task-id>/quality_review.md` 中说明理由。

### 元数据

```toml
[metadata]
author_name = "SWE-bench-Live"
tags = ["coding", "windows", "windows-bench"]
```

### 镜像身份要求

- `docker_image` 若在构建期生成，可先留空并加注释说明
- **镜像标签不是不可变身份**，必须在 `delivery-extras` 中**另存实际 Digest**
- Harbor JSON、`task.toml`、`swelive_spec.json` 三处的镜像引用必须**统一**

---

## 三、instruction.md 规范

**这是 Agent 唯一可见的题面**，内容必须与实际下发版本一致。

| 应包含 | 不得包含 |
|---|---|
| 背景或现象 | Golden Patch |
| 目标 | 答案路径 |
| 功能边界 | 隐藏测试内容 |
| 约束条件 | 精确修改位置 |
| 允许修改范围 | 可照抄的实现步骤 |
| 用户可见的验收标准 | 任何形式的 Reward 信息 |

---

## 四、environment/ 规范

### Dockerfile 关键约束

1. **基线镜像**：从已烘焙源码与工具链的 base image 派生
   ```dockerfile
   FROM <registry>/swe-bench-live:<instance_id 变体>

   SHELL ["powershell", "-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command",
          "$ErrorActionPreference = 'Stop'; $ProgressPreference = 'SilentlyContinue';"]
   ```

2. **必备工具链**：git（patch 捕获与回放）、Python + uv、RewardKit（预取后转离线）
   ```dockerfile
   RUN uvx.exe --from 'harbor-rewardkit==0.1.7' rewardkit --help | Out-Null
   ENV UV_OFFLINE="1"
   ```

3. **工作区注入**：
   ```dockerfile
   COPY ["workspace/", "C:/testbed/"]
   ```

4. **基线提交**（可用 patch 回放，**不要用 wall-clock 标记**）：
   ```dockerfile
   RUN Set-Location C:\testbed; \
       if (-not (Test-Path .git)) { git init -q }; \
       git add -A; \
       git -c user.email=bench@example.com -c user.name='Terminal Bench' commit --allow-empty -qm baseline
   ```

5. **依赖必须锁定**，且在**断网条件**下真实可用
6. **禁止**在 environment 中泄露 Solution 和隐藏 Tests

### 目录位置约定

| 路径 | 用途 |
|---|---|
| `C:\testbed` | 被测工作区（Agent 修改此处） |
| `C:\tests` | 隐藏测试（Agent 不可见） |
| `C:\logs` | 运行日志与评分产物 |

---

## 五、tests/ 规范

### 5.1 test.ps1 —— 验证入口

职责顺序：

1. **还原被 test_patch 触碰的文件**（从 HEAD 恢复，删除新增文件）
2. **apply test_patch**（`git apply --check --binary` 失败 → 输出 `===SWELIVE_INVALID test_patch_check_failed===` 并 exit 2）
3. **环境预检**（如 `python -c "import pytest, <pkg>"`，失败 → `===SWELIVE_INVALID prepared_environment_missing===`）
4. **清除旧产物**（如 `Remove-Item reports -Recurse -Force`）
5. **运行 required 测试**
6. **调用 grade.py 评分**
7. **校验评分产物完整性**（reward.txt / reward.json / reward-details.json 三者缺一即 INVALID）

**关键 INVALID 标记**（必须区分于模型 0 分）：

| 标记 | 含义 |
|---|---|
| `===SWELIVE_INVALID test_patch_check_failed===` | test_patch 无法应用 |
| `===SWELIVE_INVALID test_patch_apply_failed===` | apply 执行失败 |
| `===SWELIVE_INVALID prepared_environment_missing===` | 环境未就绪 |
| `===SWELIVE_INVALID test_report_missing===` | 测试报告缺失 |
| `===SWELIVE_INVALID reward_artifact_missing===` | 评分产物缺失 |
| `===SWELIVE_INVALID reward_artifact_malformed===` | 评分产物损坏 |

> **设计原则**：模型测试失败 = 合法 0 分；缺失/损坏的评分产物 = 基础设施故障，**不得静默接受为 0 分**。

### 5.2 grade.py —— 程序化评分

核心逻辑：

```
f2p_all_pass = set(F2P).issubset(set(F2P_parsed_pass))
p2p_all_pass = set(P2P).issubset(set(P2P_parsed_pass))
resolved = (not candidate_failure) and infrastructure_valid and f2p_all_pass and p2p_all_pass
score = 1.0 if resolved else 0.0
```

**必须区分三种状态**：

| 状态 | 处理 |
|---|---|
| 合法 0 分 | 候选编译/测试收集失败（已过环境预检）→ 输出 reward=0 |
| INVALID | required 缺失/SKIP/解析失败/环境异常 → **不写 reward 产物**，exit 2 |
| 合法 1 分 | 所有 required F2P+P2P 观测到且 PASS → reward=1 |

**证据完整性**：评分报告须记录 `run_id`、`source_commit`、`image_digest`、
`log_sha256`、`spec_sha256`、`test_patch_sha256` —— 用于跨运行晋升校验。

### 5.3 swelive_spec.json —— 元数据

```json
{
  "instance_id": "<task-id>",
  "test_cmds": ["..."],
  "print_cmds": ["..."],
  "rebuild_cmds": ["..."],
  "log_parser": "def parser(log): ...",
  "FAIL_TO_PASS": ["<test id>", "..."],
  "PASS_TO_PASS": ["<test id>", "..."],
  "verification_evidence": {
    "required_base_runs": 3,
    "required_oracle_runs": 3,
    "same_image_digest": true,
    "require_source_commit": true,
    "require_test_patch_sha256": true,
    "require_raw_log_sha256": true,
    "allow_missing_tests": false
  },
  "base_commit": "<sha>",
  "image_ref": "<registry>/<repo>:<tag>"
}
```

> `allow_missing_tests: false` —— 缺失测试**必须**标为 INVALID。

### 5.4 test_patch.diff —— 隐藏测试补丁

- 与参考解**实现相互独立审查**
- 只包含测试代码，不含解法
- 格式为标准 git diff（`--- a/` / `+++ b/`）

---

## 六、solution/ 规范

- 提供可执行参考解或参考补丁
- **仅用于 Golden 验证**，不向 Agent 暴露
- Golden 必须有**直接证据**证明参考解已实际应用，不能只依赖环境变量、任务名称或日志标题

---

## 七、Windows 环境硬性要求

| 要求 | 说明 |
|---|---|
| 真实 Windows Runtime | 在真实 Windows 环境触发验证 |
| **禁止 Linux Mock 替代** | Windows VM/Server/桌面/企业/驱动/硬件题不得为迁就目录形式而用 Linux Mock 或普通容器 |
| 依赖锁定 | 版本固定，断网可复现 |
| 副作用可恢复 | 注册表/服务/计划任务/证书/ACL/防火墙/安装器/驱动变更必须可清理、可恢复 |
| 旧产物清理 | 每次运行前清除旧构建产物和系统残留 |

> 必要的 Runner/Adapter 由平台与供应商在 **Harbor 标准扩展机制内**冻结，
> **不能改变"题目最终仍是标准 Harbor Task"的要求**。
