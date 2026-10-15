# Windows Harbor 质检报告

生成时间：`2026-10-15T02:29:37.926895+00:00`

结论：**FAIL**

本报告由本地真实 Harbor CLI 生成；输入题包未被修改。

压缩包名/根文件夹名：`N/A`

## wfflab__wtoken-221

静态结构：`FAIL`
- 静态错误：environment/Dockerfile:13 运行层使用禁止的 Nano Server/Server Core 镜像：mcr.microsoft.com/windows/servercore:ltsc2022@sha256:76cf422c98ca437b308374d0498280541fa42ac7061bb44015a6c8b70cf4db6a

## 证据

- `inventory.json`：结构、入口和文件 Hash
- `commands.json`：每轮实际 Harbor CLI 命令
- `jobs/`：Harbor 原始 job/trial/verifier 结果
- `*.cli.log`：Harbor CLI 原始输出，可作为 Oracle 成功的直接文字证据
