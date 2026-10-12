# OBM Skill

OBM Source benchmark 题目生产与交付的统一 skill，覆盖从选题生产到质检交付的全流程。

## 安装到其他 Agentic

将本目录（`OBM/`）整体复制到目标 Agentic 的 skills 目录即可。目录内所有子流程自带完整的 `scripts/` 与 `references/`，无外部依赖（除 Python 3.9+ 标准库、系统 `git`、Docker、`lark-cli`，按流程按需使用）。

```bash
# 示例：复制到目标 skill 目录
cp -r OBM <目标 skills 目录>/OBM
```

部署后重启会话使其生效。

## 子流程

| 子流程 | 位置 | 用途 |
|---|---|---|
| **production**（主流程） | 本目录根 | OpenAI 兼容接口版生产：Seed API 对照实验、场景去重、proposal、中文专家 skill、verifier、最终质检、打包、飞书提交 |
| **production-trae**（备选） | `subskills/production-trae/` | Trae 手动版生产：用户在 Trae 中手动执行 no-skill/with-skill |
| **review** | `subskills/review/` | proposal 内容审查：格式校验、source 复用、相关度评分、公开历史审查 |
| **run-qc** | `subskills/run-qc/` | 本地跑题与质检：批量跑题、质检 ZIP 包 |

**production 与 production-trae 互斥**，两者的 `references/` 内容不同，不可混用。默认使用 production。

## 目录结构

```text
OBM/
├── SKILL.md                    # 统一入口，含意图路由表
├── README.md                   # 本文件
├── scripts/                    # production 主流程脚本
├── references/                 # production 主流程规范
├── agents/                     # production 主流程 agent 定义
├── proposal_validator/         # production 主流程 proposal 校验器
└── subskills/
    ├── production-trae/        # Trae 手动版生产
    │   ├── SKILL.md
    │   ├── scripts/
    │   ├── references/
    │   ├── agents/
    │   └── proposal_validator/
    ├── review/                 # proposal 内容审查
    │   ├── SKILL.md
    │   ├── scripts/
    │   ├── references/
    │   └── templates/
    └── run-qc/                 # 本地跑题与质检
        ├── SKILL.md
        ├── README.md
        ├── scripts/
        ├── config/
        ├── references/
        └── vendor/             # 规则快照
```

## 关键环境变量

主流程脚本通过 `OBM_SKILL_DIR` 引用本 skill 的安装路径：

```bash
export OBM_SKILL_DIR=/path/to/skills/OBM
```

使用子流程脚本时指向对应子目录：

```bash
export OBM_SKILL_DIR=/path/to/skills/OBM/subskills/review
```

Python 解释器优先使用项目虚拟环境（`.venv/Scripts/python.exe` on Windows，`.venv/bin/python` on Linux/macOS），无 venv 时回退 `python3`。

## 使用示例

在 Agentic 会话中直接说出意图，skill 会自动路由：

- `生成新的 OBM 题包` → production 主流程
- `继续返修上一个题` → production 主流程
- `质检 D:\hc\obm\result\xxx.zip` → run-qc 子流程
- `审查这批 proposal` → review 子流程
- `用 Trae 手动跑这题` → production-trae 子流程

## 注意

- 密钥只从环境变量或配置文件读取，绝不写入命令行、日志、截图或交付 ZIP。
- 独立 verifier 才能决定题目是否 solved，模型自报成功不能代替 verifier 结果。
- 不要把 OBM 与 Harbor 生产、Pair-wise GSB 或其他标注项目混用。
