# Windows Harbor 质检报告

生成时间：`2026-10-16T16:37:04.215539+00:00`

结论：**FAIL**

本报告由本地真实 Harbor CLI 生成；输入题包未被修改。

压缩包名/根文件夹名：`N/A`

## wfflab__wvas-216

静态结构：`FAIL`
- 静态错误：judge.toml rubric hash does not match rubric.json

## 证据

- `inventory.json`：结构、入口和文件 Hash
- `commands.json`：每轮实际 Harbor CLI 命令
- `jobs/`：Harbor 原始 job/trial/verifier 结果
- `*.cli.log`：Harbor CLI 原始输出，可作为 Oracle 成功的直接文字证据
