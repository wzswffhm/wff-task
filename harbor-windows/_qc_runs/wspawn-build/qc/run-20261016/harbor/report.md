# Windows Harbor 质检报告

生成时间：`2026-10-16T04:58:11.599473+00:00`

结论：**FAIL**

本报告由本地真实 Harbor CLI 生成；输入题包未被修改。

压缩包名/根文件夹名：`N/A`

## wfflab__wspawn-218

静态结构：`PASS`
- Oracle：`[1, 1, 1]`（要求每轮 VALID/1）
- NOP：`[0, None, None, None, None]`（要求每轮 VALID/0）
- 动态门禁：`FAIL`
- 动态错误：NOP has BLOCKED/INVALID execution
- 动态错误：NOP is not VALID/0 on every independent run
- 动态错误：not all requested Oracle/NOP attempts completed

## 证据

- `inventory.json`：结构、入口和文件 Hash
- `commands.json`：每轮实际 Harbor CLI 命令
- `jobs/`：Harbor 原始 job/trial/verifier 结果
- `*.cli.log`：Harbor CLI 原始输出，可作为 Oracle 成功的直接文字证据
