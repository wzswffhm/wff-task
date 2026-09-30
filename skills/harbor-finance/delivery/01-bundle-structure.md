# 题包结构与组件清单

## 1. 交付目录树（一题一目录，目录名 = 题目编号）

```text
<批次目录：供应商名+领域+一级分类+时间>/
├── 交付文档.md                       # 环境变量配置说明等（见 04 号文档）
├── FIN-T2-001/
│   ├── instruction.md
│   ├── task.toml
│   ├── rubrics.json
│   ├── environment/
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   ├── skills/
│   │   │   └── <skill_name>/
│   │   │       ├── SKILL.md
│   │   │       ├── scripts/
│   │   │       └── references/
│   │   └── input_files/
│   ├── solution/
│   │   ├── solve.sh
│   │   └── golden_output/
│   └── tests/
│       ├── test.sh
│       ├── finalize.py
│       ├── rubrics.toml
│       ├── prompt.md
│       ├── __golden_output/
│       └── __assets/
└── FIN-T2-002/
    └── ...
```

## 2. 组件清单（必交性 / 大小 / 作用）

| 组件 | 必交 | 大小 | 作用 |
|---|---|---|---|
| `instruction.md` | 是 | ≤1 MiB | 任务书，作为 prompt 交给 Agent |
| `task.toml` | 是 | ≤1 MiB | Harbor 配置 + 元数据 + 交付物清单 + Rubric 索引 |
| `rubrics.json` | 是 | — | 原始评分细则 |
| `environment/Dockerfile` | 是 | — | 任务镜像层，含全部依赖 |
| `environment/requirements.txt` | 是 | — | 执行侧依赖，构建期预装；**无依赖交空文件** |
| `environment/input_files/` | 是 | 计入整批 ≤20 GB | 全部输入材料 |
| `environment/skills/` | 有 Skill 时必交 | 计入整批 ≤20 GB | `skill_set` 对应的技能目录，含 SKILL.md 及所需脚本、引用资料；Workflow 可由技能内 SOP 承载 |
| `solution/solve.sh` | 是 | — | Oracle 入口（正向预检基准） |
| `solution/golden_output/` | 是 | 计入整批 ≤20 GB | 专家标准答案 |
| `tests/test.sh` | 是 | — | 固定模板 |
| `tests/finalize.py` | 是 | — | 固定模板 |
| `tests/rubrics.toml` | 是 | ≤2 MiB | 由 rubric 转换的计分 criteria |
| `tests/prompt.md` | 是 | — | 评分 agent 提示词，**须含 `{criteria}` 占位符** |
| `tests/__golden_output/` | 是 | 计入整批 ≤20 GB | 参考答案副本，供判官对照 |
| `tests/__assets/` | 否 | 计入整批 ≤20 GB | 评分侧基准材料 |

> `solution/golden_output/` 与 `tests/__golden_output/` **内容一致，两目录均不得为空**。

## 3. 容器内路径与可见性

| 题包内容 | 容器内位置 | Agent 可见 |
|---|---|---|
| `instruction.md` | 作为 prompt | 可见 |
| `environment/input_files/` | `/app/input_files/`（只读） | 可见 |
| `environment/skills/` | 由 Dockerfile 指定并在任务书列明 | 可见 |
| `environment/requirements.txt` | 构建期预装进镜像 | 可见 |
| Agent 交付目录 | `/app/output/`（唯一交付目录，工作目录 = `/app`） | 可见（可写） |
| Agent 日志 | `/logs/agent/`（不作为交付物） | 可见 |
| `solution/` | `/solution`（仅 Oracle 阶段） | **不可见** |
| `tests/` | `/tests`（仅评分阶段上传） | **不可见** |
| `task.toml` | 文件不入容器 | 仅 `[environment].env` 的值可见 |

**推论**：
- Agent 侧看不到 rubric、golden、tests → 题面**不得**引用"评分会检查"类信息。
- judge 侧 cwd = `/app`，`input_files/` 与 `output/` 同级可见，`tests/` 挂到 `/tests`（含 `__golden_output/`）→ `prompt.md` 必须显式写明三区语义。

## 4. 资源默认上限

| 项 | 默认值 | 说明 |
|---|---|---|
| `[agent].timeout_sec` | 72000（1200 min） | A3 长程任务须按实际需要上调 |
| `[verifier].timeout_sec` | 18000 | **须大于单个 judge 会话超时**（`rubrics.toml` `timeout = 7200`） |
| `cpus` / `memory_mb` / `storage_mb` | 2 / 8192 / 30720 | 可按需调整 |
| Agent 交付物总量 | ≤2 GB | 指 `/app/output/` |
| 整批 zip | ≤20 GB | 含 input_files 与 golden_output |

## 5. 运行链路（固定）

```
harness → bash /tests/test.sh
        → rewardkit /tests --workspace /app --output /logs/verifier/graded/reward.json
        → python3 /tests/finalize.py --out /logs/verifier/reward.json
```

输出落点：

| 文件 | 语义 |
|---|---|
| `/logs/verifier/reward.json` | 主结果（`reward` / `verifier_error` / `graded_score` / `criteria_counted`） |
| `/logs/verifier/reward.txt` | 单一数值 |
| `/logs/verifier/reward-details.json` | 逐条明细（审计用，缺失不影响主分） |
| `/logs/verifier/reward_exit_message.json` | **仅评分不可用时存在**；错误码枚举 `judge:timeout` / `judge:api_error` / `judge:parse_error` / `judge:scorer_error` / `judge:invalid_output` / `judge:unknown` |

## 6. 文件级硬约束

- 所有文件名 **UTF-8**，单个 ≤200 字节，**无控制字符**，**禁止符号链接**。
- `solve.sh` / `test.sh`：**LF 换行 + 可执行位**。
- 交付物文件名建议以**题目编号为前缀**，避免与 Agent 中间产物混淆。
- toml / prompt.md 内**不得含不可见空白**（U+00A0、U+3000 等）。
