# windows-qwen-opus 模型运行配置说明

本包用于在当前 Windows 仓库 + Windows Docker / Harbor 环境中，分别运行 Qwen 和 Claude(Opus) 完成 Windows 评测作业。

## 1. 适用对象

你已经具备：

- 当前 Windows 仓库
- Windows Docker / Windows Containers
- Harbor
- Claude Code 可执行文件已固化在题目镜像中

本包不包含模型密钥，也不包含真实 `.local\harbor-models.psd1`。

## 2. 文件清单

```text
windows-qwen-opus模型运行配置说明/
├── README.md
├── scripts/
│   ├── start_relay.ps1
│   ├── relaunch_qwen.ps1
│   ├── relaunch_claude.ps1
│   └── host_api_relay.py
├── agent/
│   ├── windows_claude_code.py
│   └── windows_claude_code_workspace.py
└── examples/
    └── harbor-models.example.psd1
```

## 3. 一个作业的调用流程

1. Harbor 启动题目任务。
2. Harbor 调用 agent：

   ```text
   agent.windows_claude_code:WindowsClaudeCodeAgent
   ```

3. 容器内执行 `C:\node\claude.cmd`，Claude Code 是实际作业 agent。
4. Claude Code 把模型请求发给宿主机 relay。
5. 宿主机 relay 读取对应模型 profile 的上游地址，转发 `/v1/messages`。
6. relay 在转发前注入模型参数。
7. 作业完成后，Harbor 运行 verifier，生成 reward。

### Qwen 调用链

```text
Harbor job
  -> agent.windows_claude_code:WindowsClaudeCodeAgent
  -> 容器内 claude.cmd
  -> http://host.docker.internal:18184
  -> scripts/host_api_relay.py
  -> Qwen profile BaseUrl
```

### Claude/Opus 调用链

```text
Harbor job
  -> agent.windows_claude_code:WindowsClaudeCodeAgent
  -> 容器内 claude.cmd
  -> http://host.docker.internal:18183
  -> scripts/host_api_relay.py
  -> Claude profile BaseUrl
```

> 端口可以改，只要 `start_relay.ps1 -Port` 和 `relaunch_*.ps1 -RelayPort` 一致即可。

## 4. 配置准备

真实模型配置放在仓库的：

```text
.local/harbor-models.psd1
```

结构参考：

```powershell
@{
    Profiles = @{
        qwen_3_8_max = @{
            Model   = "qwen3.8-max-0902"
            ApiKey  = "<qwen-key>"
            Agent   = "windows-claude-code"
            BaseUrl = "<qwen-endpoint>"
        }
        claude_opus_5 = @{
            Model   = "claude-opus-5"
            ApiKey  = "<claude-key>"
            Agent   = "windows-claude-code"
            BaseUrl = "<claude-endpoint>"
        }
    }
}
```

占位模板见 `examples/harbor-models.example.psd1`。

## 5. 参数说明

### 5.1 容器内 Claude Code 参数

这些参数由 agent 设置，在 `agent/windows_claude_code.py` 的 `_model_env()` 中：

```text
CLAUDE_CODE_NO_MODEL_FALLBACK=true
CLAUDE_CODE_MAX_CONTEXT_TOKENS=1000000
CLAUDE_CODE_AUTO_COMPACT_WINDOW=1000000
CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=80
API_TIMEOUT_MS=900000
BASH_DEFAULT_TIMEOUT_MS=600000
CLAUDE_CODE_MAX_RETRIES=8
CLAUDE_CODE_MAX_OUTPUT_TOKENS=128000
```

同时清空容器内代理，避免 Claude Code 误走不可达的宿主代理。

### 5.2 relay 模型请求参数

这些参数由 `start_relay.ps1` 设置，由 `host_api_relay.py` 注入：

```text
temperature=1
top_p=0.95
top_k=20
max_tokens=65535
enable_thinking=true
reasoning_effort=xhigh
```

旧思考参数也保留：

```text
THINKING_ENABLED=true
THINKING_MODE=adaptive
THINKING_BUDGET_TOKENS=24000
MID_SYSTEM_MESSAGE_STRATEGY=merge
```

### 5.3 Qwen 与 Claude 的差异

- Qwen：
  - 注入 `enable_thinking=true`
  - 注入 `reasoning_effort=xhigh`
- Claude/Opus：
  - 使用标准 Anthropic `thinking` 对象
  - 不额外注入 `enable_thinking` 和 `reasoning_effort`
  - 原因是部分 Claude 网关同时给 `reasoning_effort` 和 `thinking_budget` 会冲突

## 6. 启动步骤

下面用占位符：

```text
<REPO_ROOT>   = 当前仓库根目录，例如 D:\bianhuikang\windows-xiufu
<TASK_PATH>   = Harbor 题目目录
<JOBS_DIR>    = jobs 输出目录
```

### 6.1 启动 Qwen relay

```powershell
.\scripts\start_relay.ps1 `
  -RepoRoot <REPO_ROOT> `
  -ProfileName qwen_3_8_max `
  -Port 18184
```

### 6.2 启动 Claude/Opus relay

```powershell
.\scripts\start_relay.ps1 `
  -RepoRoot <REPO_ROOT> `
  -ProfileName claude_opus_5 `
  -Port 18183
```

### 6.3 启动 Qwen 作业

```powershell
.\scripts\relaunch_qwen.ps1 `
  -RepoRoot <REPO_ROOT> `
  -TaskPath <TASK_PATH> `
  -JobsDir <JOBS_DIR> `
  -JobName windows-d6-002-qwen-1 `
  -RelayPort 18184
```

### 6.4 启动 Claude/Opus 作业

```powershell
.\scripts\relaunch_claude.ps1 `
  -RepoRoot <REPO_ROOT> `
  -TaskPath <TASK_PATH> `
  -JobsDir <JOBS_DIR> `
  -JobName windows-d6-002-claude-1 `
  -RelayPort 18183
```

## 7. 验证是否正常

### 7.1 检查 relay 端口

```powershell
Get-NetTCPConnection -LocalPort 18183,18184 -State Listen
```

### 7.2 检查作业容器

```powershell
docker ps --filter ancestor=windows-d6-002:r01
```

### 7.3 检查轨迹和思考内容

在 jobs 目录下：

```text
<JOBS_DIR>\<JOB_NAME>\<trial>\agent\claude-code.jsonl
<JOBS_DIR>\<JOB_NAME>\<trial>\agent\sessions\projects\...
```

如果看到 `"type":"thinking"` 且 `thinking` 非空，说明思考模式已生效。

## 8. 常见问题

### 8.1 `401 InvalidApiKey`

先确认：

- profile 的 `ApiKey` 是否正确
- relay 是否使用正确的 `ProfileName`
- relay 端口是否和作业脚本一致

### 8.2 `Insufficient system resources exist to complete the requested service`

这是 Windows Docker 资源不足，不是模型或题目问题。先停掉旧的 Windows 容器，再重跑。

### 8.3 `reasoning_effort and thinking_budget cannot be set simultaneously`

说明对非 Claude 模型错误地同时注入了两个思考参数。使用本包脚本即可避免；Claude 模型不走 `reasoning_effort`。

### 8.4 思考块为空

检查：

- relay 是否真的启动了
- 模型请求是否走 relay
- 模型是否为推理模型

