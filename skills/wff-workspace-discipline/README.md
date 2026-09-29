# wff-workspace-discipline

wff-task 工作区的**落盘纪律** skill —— 约束 Agent 把文件写到正确位置，防止污染仓库根目录与题包目录。

## 解决的问题

Agent 容易把分析报告、抽取文本、临时脚本直接写到工作区根目录，或把题目专属内容丢在题包类型目录根部、污染其他题包。
本 skill 通过三条铁律约束产出位置。

## 三条铁律

| 铁律 | 内容 |
|---|---|
| **一、根目录单一制** | `README.md`、`.gitignore`、`deliverables/`、`skills/` **只允许存在一个**；题包类型目录可扩展但须登记 |
| **二、题包按类型隔离** | `OBM/`、`harbor-16/`、`harbor-sota/` 是题包**类型目录**；单包 = 类型目录下的独立子目录；类型目录根部**只放公用**脚本/配置（参考 `OBM/`） |
| **三、deliverables 命名** | 解析材料产出放在 `deliverables/<日期>_<材料名>/`，目录名 = 产出日期 + 材料主名（去扩展名），**保持原拼写** |

## 落点速查

| 产出内容 | 落点 |
|---|---|
| 解析某份材料的报告 | `deliverables/<日期>_<材料名>/` |
| 解析支撑材料 | 同上目录 |
| 题包中间产物 | `<类型目录>/work/<题号>/` |
| 成品题包 | `<类型目录>/<题包>/` 或 `OBM/output/<题包>/` |
| 跨题复用配置/脚本 | 类型目录根部（公用层） |

新增题包类型（如 Windows-Harbor）时：先 `mkdir` 类型目录，再按「公用 + 单包目录」两层组织，并在根 `README.md` 登记。

## 安装

```bash
# 用户级（所有项目可用）
cp -r skills/wff-workspace-discipline ~/.workbuddy/skills/

# 项目级（仅本仓库）
cp -r skills/wff-workspace-discipline <你的项目>/.workbuddy/skills/
```

详细规则见 `SKILL.md`。
