# Windows Harbor 质检报告

生成时间：`2026-10-16T01:57:25.933074+00:00`

结论：**PASS**

本报告由本地真实 Harbor CLI 生成；输入题包未被修改。

压缩包名/根文件夹名：`N/A`

## wfflab__wvas-216

静态结构：`PASS`
- Oracle：`[1, 1, 1]`（要求每轮 VALID/1）
- NOP：`[0, 0, 0]`（要求每轮 VALID/0）
- 动态门禁：`PASS`

## 证据

- `inventory.json`：结构、入口和文件 Hash
- `commands.json`：每轮实际 Harbor CLI 命令
- `jobs/`：Harbor 原始 job/trial/verifier 结果
- `*.cli.log`：Harbor CLI 原始输出，可作为 Oracle 成功的直接文字证据
