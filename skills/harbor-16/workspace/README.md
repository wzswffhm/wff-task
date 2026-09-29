# Harbor 工作区归档

本目录保存原 `Harbor/` 文件夹中有复用价值的文件。该文件夹已于 2026-09-29 按要求删除，其题包内容此前已分类至：

- `harbor-16/` — 内部 RL 题包
- `harbor-sota/` — 外发供应商题包

## 目录说明

| 位置 | 内容 | 来源 |
|---|---|---|
| `*.sh` / `*.py` / `*.ps1` | 工作区工具脚本（tree 交付、难度监控、skill 同步等） | `Harbor/scripts/` |
| `docs/readme.md` | WSL2/Docker/Harbor 环境搭建说明与难度提升方向笔记 | `Harbor/readme.md` |
| `docs/check.md` | Harbor 验证与测试命令指南（NOP/Oracle/跑题命令） | `Harbor/check.md` |
| `docs/外发规范-内部题包差异清单.md` | 内部题包 vs 外发规范 v4 的差异对比 | `Harbor/` |
| `docs/分类说明.md` | Harbor 内容分类判定依据 | `Harbor/` |
| `memory/*.md` | 会话记忆（2026-08-13、08-14） | `Harbor/.workbuddy/memory/` |

## 已删除的 skill 副本

原 `Harbor/.dsh/skills/` 与 `Harbor/.trae/skills/` 中的 skill 副本已全部删除，原因是 `skills/` 目录中已有对应或更完整的版本：

| 已删除 | 处置原因 |
|---|---|
| `.dsh/skills/caveman` | 与 `skills/caveman` 完全一致 |
| `.dsh/skills/harbor-16` | 与 `skills/harbor-16` 一致（仅 `name` 字段写法不同，`skills/` 版已修正为规范形式） |
| `.dsh/skills/harbor-sota` | 同上 |
| `.dsh/skills/harbor-work` | 同上 |
| `.dsh/skills/webdev3d-annotator` | 按用户决定删除（Text-to-3D 前端标注 skill，8 文件） |
| `.trae/skills/harbor-skill` | harbor-16 的旧版，内容较少（缺 10 个 references 文件） |

## 注意

`docs/check.md` 含**明文 API Key**（阿里云 MaaS `OPENAI_API_KEY`）。使用前请替换为环境变量，并建议轮换该 Key。
