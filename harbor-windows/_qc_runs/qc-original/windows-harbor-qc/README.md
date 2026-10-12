# windows-harbor-qc

这是一个可直接分发的本地 Windows Harbor 题包质检 Skill。它不依赖飞书账号、固定项目路径或私有配置，接收题目目录或 ZIP，输出可审计的 Markdown/JSON 结果和原始 Harbor 运行证据。

## 依赖

- Windows 主机，并切换到 Docker Windows Containers 模式；
- Docker CLI，`docker info` 能返回 `windows`；
- Harbor CLI，`harbor --version` 可执行；
- Python 3.11 或更高版本（使用标准库 `tomllib`）；
- 题包自身声明的 Windows 镜像、离线依赖和资源预算。

## 运行

在本目录执行：

```powershell
python scripts\run_qc.py `
  --input D:\path\task.zip `
  --out D:\path\qc-result
```

也可以直接检查目录：

```powershell
python scripts\run_qc.py `
  --input D:\path\task-root `
  --out D:\path\qc-result
```

默认每个题目对 `oracle` 和 `nop` 各跑 3 次；使用 `--attempts 6` 可以执行六轮稳定性门禁。`--force-build` 会要求 Harbor 重新构建镜像。默认环境扩展是包内 `windows_qc_env:WindowsQCEnvironment`；平台有其他已冻结扩展时，可用 `--environment module:Class` 明确覆盖。

## 结果

结果目录必须为空或不存在，程序会拒绝覆盖旧证据。重点文件：

- `report.md`：人读结论和失败原因；
- `report.json`：结构化结论、每轮状态、分数和 testcase；
- `inventory.json` / `hashes.json`：输入身份、目录结构和文件 Hash；
- `commands.json`：实际执行的 Harbor 命令；
- `jobs/`、`*.cli.log`：原始 job、trial、verifier 和 Harbor CLI 输出。

`PASS` 只表示全部静态和动态门禁通过。`FAIL` 表示题包结构、测试协议或行为门禁不通过。`BLOCKED` 表示没有完成真实执行，例如 Docker 仍是 Linux 模式、Harbor 不可用、输入归档不安全或运行目录受阻。

正式批次还需校验模型区分度。把本地 Qwen/Opus/GLM/Kimi 运行结果整理为 JSON 后执行：

```powershell
python scripts\validate_model_gate.py --input D:\path\model-evidence.json
```

JSON 的每个运行项包含 `validity`、`score` 和 `cases`（每个 testcase 有 `id`、`status`）。Qwen/Opus 必须各有 3 次有效运行；GLM/Kimi 至少各有 1 次。Opus 总分必须严格高于 Qwen；若两者总分都为 0，则 Opus 的 testcase PASS 总数必须严格更高。总分相等且不全为 0，或全 0 但 testcase 总数相等，均不通过。

## 分发边界

本 Skill 只做检查和证据生成。它不会自动修复题包、删除历史结果、修改 Feishu/Base，也不会把任何 API key、账号、`.env` 或当前项目证据打包进去。修改题包后必须变更版本/Hash，并在新的空结果目录重新执行完整门禁。
