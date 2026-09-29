# 质检新增口径（2026-08-18 更新）

> 来源：COB-L4-001(L4-COBOL) 质检返修结论 + 验收执行细则。
> 与《外发版-评测题包交付规范 v4》（20260808 PDF）存在差异时，**以本口径为准**（质检执行版本更新于 PDF）。

## 1. 评测项总数（L4 ≥ 24）

- 统计口径不变：`graded/judge.toml` + `gating/gating.toml` 全部 criterion（含 gating 项）。
- **L4 下限由 18 条提升到 ≥ 24 条**；L2 ≥ 8、L3 ≥ 12、L5 ≥ 25 维持不变（如质检另行收紧以质检为准）。
- 返修示例：R1–R20（20 条 judge）+ G1/G2（2 条 gating）= 22 条 → 不达标；需补足到 ≥ 24 条。

## 2. 10 分核心项（L4 ≥ 4 条）

- 规范 v4 要求 Critically Important（weight=10.0）≥ 2 条；**质检执行口径 L4 需 ≥ 4 条**。
- 返修示例：仅 R1/R2 两个 10 分项 → 不达标；需凑够 4 个 10 分项。

## 3. Gating 门禁数量（1–2 条）

- **gating 项只能 1–2 条**，设卡过度会被打回。
- 返修示例：G1–G4 共 4 条 → 不达标；需削减到 ≤ 2 条，保留安全合规/致命专业错误红线即可。

## 4. judge.files 禁止 golden_output 脏路径，改用 reference

- `[judge].files` **禁止**出现 `/tests/golden_output/...` 等答案路径（判官不得把参考答案当候选产物读入）。
- 参考答案改用 `[judge].reference` 配置：
  - 单文件：`reference = "/tests/golden_output/<文件>"`；
  - 多文件（推荐）：`reference = "/tests/golden_output"`（rewardkit 递归读取目录内全部文件作为 Reference Solution）。
- `[judge].files` 只保留候选产物 `/app/output/...`。

## 5. 返修要点速查

| 质检项 | 不达标示例 | 达标要求 |
|---|---|---|
| 评测项总数 | 22 条（R1–R20 + G1/G2） | L4 ≥ 24 条 |
| 10 分核心项 | 2 个（R1/R2） | L4 ≥ 4 个 |
| Gating 数量 | G1–G4 共 4 条 | 1–2 条 |
| files 脏路径 | files 含 `/tests/golden_output/...` | 摘除 + `reference = "/tests/golden_output"` |

## 6. 配套校验脚本片段（python3.12 + tomllib）

```python
import tomllib
j = tomllib.load(open('tests/graded/judge.toml','rb'))
g = tomllib.load(open('tests/gating/gating.toml','rb'))
total = len(j['criterion']) + len(g['criterion'])
w10 = [c['id'] for c in j['criterion'] if c.get('weight') == 10.0]
dirty = [f for f in j['judge']['files'] if '/tests/golden_output' in f]
print('total criteria:', total, '(L4 >= 24)')
print('10pt count:', len(w10), '(L4 >= 4)')
print('gating count:', len(g['criterion']), '(1-2)')
print('files dirty golden paths:', dirty, '(must be empty)')
print('reference:', j['judge'].get('reference'))
```