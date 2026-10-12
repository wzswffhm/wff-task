# Windows Harbor 质检报告

生成时间：`2026-10-12T09:25:11.484456+00:00`

结论：**FAIL**

本报告由本地真实 Harbor CLI 生成；输入题包未被修改。

压缩包名/根文件夹名：`N/A`

## wfflab__wlogseg-218

静态结构：`FAIL`
- 静态错误：referenced files are missing: solution\reference\wlogseg, tests\test_wlogseg_semantics.py

## 证据

- `inventory.json`：结构、入口和文件 Hash
- `commands.json`：每轮实际 Harbor CLI 命令
- `jobs/`：Harbor 原始 job/trial/verifier 结果
- `*.cli.log`：Harbor CLI 原始输出，可作为 Oracle 成功的直接文字证据
