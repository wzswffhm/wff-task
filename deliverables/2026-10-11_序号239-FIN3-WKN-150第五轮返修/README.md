# 序号 239（FIN3-WKN-150）第五轮返修说明

- 飞书记录：wiki 节点 `S4dVwTGtviikDPkF0wycdMernKf`，Base `QpzNb4fXSamfX6sLloBcPfHNnug`，表 `tblPNrBtjFfwOowN`，记录 `reczz28Jf9pZeD1T`。
- 批次：`work_fin-b01_20261006_fix7-150`；题包版本 `1.0.7`；执行体 `oracle / qwen3.8-max-0902 / claude-opus-4-8 / gpt-5.6-sol`。

## 1. 本轮问题与处置

依据飞书《序号239_质检报告 (2).md》【待改】第 2、3 项，本轮将原“2029 年上市并按 PE 16.12 × 2027 年承诺利润 18,000 万元”退出基准改为信息不足披露与条件分析：

1. 金标备忘录改为“退出回报测算与信息边界”，明确退出时点、退出日估值口径、锁定减持期与退出日持股比例缺失，可靠绝对退出价值、MOIC/IRR 与固定年化回报均标注“待核实”；290,160 / 18,873 / 1.26 / 8.0% 仅作条件分析；33 号材料只规定 2029-12-31 前完成上市申报。
2. `tests/rubrics.toml` 与 `tests/rubrics.json` 的 R27 改为“退出回报口径披露正确”；条数仍为 36、权重仍为 7、`S_max = 220`。
3. 未改题面、输入、PNG 路径与包结构；四执行体复用现有原生 `output/`，仅重跑 verifier，不伪造 Agent 产物。

## 2. 判分与门禁

| 执行体 | fix6（旧） | fix7（本轮） |
|---|---:|---:|
| oracle | 1.000000 | **1.000000** |
| qwen3.8-max-0902 | 0.765909 | **0.731818** |
| gpt-5.6-sol | 0.654545 | **0.686364** |
| claude-opus-4-8 | 0.573864 | **0.534091** |
| 三模型均分 | 0.664773 | **0.650758** |

门禁：oracle `1.0 > 0.85`；均分 `0.650758 < 0.70`；三模型非零；`criteria_counted = 36`、`verifier_error = 0`；难度维持 **A1**。`summary.json` 已写入 `task_version = 1.0.7`、`round = fix7(exit-assumption-remediation)+rejudge`，并留痕 17 条 `invalid_runs`。

## 3. 打包与飞书回写

- `work_fin-b01_20261006_fix7-150.zip`：14,077,398 B，sha256 `36b416bcdd4cb4791715a91b06a6c6c84a23b09bb44307f17bc63322e02386f8`，140 条目，`.sh=0755`、其余 0644、LF、无 `_rejudge/__pycache__`。
- `FIN3-WKN-150_task.zip`：69,195 B，sha256 前缀 `31901bb15309ff0b`。
- `FIN3-WKN-150_answer.zip`：930,200 B，sha256 前缀 `310d5045b07bb2e1`。
- 飞书回写采用“先删同名旧附件、再上传新附件”；复核三字段均恰好 1 个文件：交付物 `work_fin-b01_20261006_fix7-150.zip`、题目附件 `FIN3-WKN-150_task.zip`、标准答案附件 `FIN3-WKN-150_answer.zip`。
- 未改动：状态 `待返修`、题目难度 `A1`、标注人 `wff`、序号 239 及质检报告字段；未上传机器原报告或其他附件。

## 4. 证据

- 最新质检报告：`evidence/飞书最新质检报告.md`
- 改前备份：`evidence/before_fix7/`
- 前轮包与提取：`evidence/work_fin-b01_20261006_fix6-150.zip`、`evidence/fix6_extract/`
- 脚本：`scripts/apply_fix7_150.py`、`scripts/run_rejudge_150_fix7_wsl.py`、`scripts/archive_fix7.py`、`scripts/repack_150_fix7.py`、`scripts/verify_fix7_150.py`、`scripts/feishu_writeback_fix7_150.py`
