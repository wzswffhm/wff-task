# 跑分产物与轨迹说明（FIN-PE-001）

本目录随题包一并提交，用于复核难度门槛（参考答案 > 0.85、三模型平均分 < 0.7）与逐条失分点。

## 目录结构

```
FIN-PE-001/
├── oracle/                 # 参考答案（solution/golden_output 的 6 份交付物）
│   ├── output/             # 6 份交付物，文件名与题面逐字一致
│   ├── reward.json         # 平台 finalize.py 输出的主分与错误码
│   └── reward-details.json # 逐条判分记录：criterion id / value / weight / 判官理由
├── qwen3.8-max-0902/       # 执行体 1：claude-code 2.1.114 + qwen3.8-max-0902
├── claude-opus-4-8/        # 执行体 2：claude-code 2.1.114 + claude-opus-4-8
└── gpt-5.6-sol/            # 执行体 3：claude-code 2.1.114 + gpt-5.6-sol（经本地 anthropic→openai 桥）
```

非 oracle 的执行体目录内含 `轨迹/`：claude-code agent 的 `trajectory.json`（agent.name = claude-code、
version 2.1.114）与终端流式日志 `claude-code.txt`。执行体目录统一为标准四件
（`output/`、`reward.json`、`reward-details.json`、`轨迹/`）；原生会话 `session-*.jsonl` 与汇总
`scores.json` 已按归档规范移出题包，随包不含。三个模型均在同一框架
（claude-code）下各跑 1 次；gpt-5.6-sol 因该 key 分组不允许 anthropic 分发，经本地桥接器
（`_runtime/anthropic_openai_bridge.py`，上游 `/v1/responses`）接入，客户端仍是 claude-code。

## 判分口径

- 判官：`claude-code` agent judge，裁判模型 `qwen3.7-plus`，`mode = "individual"`（每条 criterion 一个独立会话，逐条串行）。
- 主分：`Score = (Σ 正分 weight×value − Σ negate weight×(1−value)) / S_max`，`S_max` 为正分权重之和 298（negate 条目不进分母）。
- 四个执行体（oracle / qwen3.8-max-0902 / claude-opus-4-8 / gpt-5.6-sol）均使用**同一份最终版**
  `instruction.md`、`tests/rubrics.toml`（51 条判据、正分池 298）与 `environment/input_files/` 完成判分；
  判分在统一流程内**串行**完成（oracle → qwen → opus → gpt，每个跑完才起下一个），未使用跨环境人工重判结果。

## 复现方式

```powershell
cd C:\Users\Administrator\Downloads\rl01-data-production
# 参考解（oracle）自检
harbor run -p "_deliverable\zq-金融-私募股权-20260930_fix2\FIN-PE-001" -a oracle `
  --extra-docker-compose _harbor\compose-cn-mirror.yaml --env-file _run\harbor.env -y
# 执行体（claude-code + 裁判 qwen3.7-plus）
harbor run -p "_deliverable\zq-金融-私募股权-20260930_fix2\FIN-PE-001" -a claude-code -m qwen3.8-max-0902 `
  --extra-docker-compose _harbor\compose-cn-mirror.yaml --env-file _run\harbor.qwen.env -y
# gpt-5.6-sol（先起桥接器，再用 claude-code 执行体）
python _run\build\start_gpt_bridge.py
harbor run -p "_deliverable\zq-金融-私募股权-20260930_fix2\FIN-PE-001" -a claude-code -m gpt-5.6-sol `
  --extra-docker-compose _harbor\compose-cn-mirror.yaml --env-file _run\harbor.gpt.bridge.env -y
# 只重跑判官（判据或参考答案改动后）
# 注：该脚本内的 TASK 路径需先改成本版批次目录（原路径指向已归档的初版目录）
python _run\build\rejudge_finpe_serial.py          # 严格串行：oracle → qwen → opus → gpt
```
