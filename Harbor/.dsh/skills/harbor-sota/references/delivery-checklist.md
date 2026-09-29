# 提交前自检清单（规范 8.2，11 项全过才允许打包提交）

## 检查项

| # | 检查项 |
|---|--------|
| 1 | 五件套齐全；environment/requirements.txt 即使无依赖也已交空文件 |
| 2 | solution/solve.sh、tests/test.sh 为 LF 换行且带可执行位 |
| 3 | 交付物文件名六处逐字节一致：instruction.md、deliverables.path、artifacts、两份 golden_output/、judge 的 files |
| 4 | judge.toml + gating.toml 的 criterion id 集合与 [[metadata.rubric_index]] 完全一致 |
| 5 | 满足 6.7 条数下限、Critically Important ≥2、负向 ≥20%、锚点 ≥30%、三个必需维度已覆盖 |
| 6 | weight 只出现 3.0 / 7.0 / 10.0；无负数 weight；只有 binary 类型 |
| 7 | 本地跑通双向预检：Oracle ≥0.7 且 gating=1.0、空产物 ≤0.10，两次均 verifier_error=0 |
| 8 | task_id 在目录名、[metadata].task_id、[task].name 的 name 段三处一致（按小写连字符规则归一化后比较）；[task].name 的 org 段与批次目录前缀为同一代号 |
| 9 | 题包任何位置无真实密钥 / token / 凭证；需要时用占位符（如 <API_KEY>）并在任务书说明；[environment].env 中不得出现凭证或评分相关信息 |
| 10 | 无残留：.git/、__pycache__/、.venv/、__MACOSX/、.DS_Store，以及本地跑测产生的 reward.json / reward-details.json / logs/ / jobs/ |
| 11 | 所有文件名 UTF-8、单个 ≤200 字节、禁止符号链接；整包 ≤20 GB |

## 打包结构（8.1）

```text
供应商名字 + 领域 + 一级分类 + 时间/        ← 如 xx-金融-投资银行-20260807提交
├── FIN-T2-001/
│   ├── instruction.md
│   ├── task.toml
│   ├── environment/
│   ├── solution/
│   └── tests/
├── FIN-T2-002/
└── ...
```

- 固定「批次目录 → 题目目录 → 五件套」，不得多套一层，也不得把题目目录平铺在 zip 根。
- 单题提交命名：供应商名字+领域+一级分类+时间（如 `xx-金融-投资银行-20260807提交`）。
- 多题一批：压缩包命名 `供应商名字+领域+批次+时间`，按领域分别提交压缩包。

## 提交与返修（8.3）

- 整批打成一个 zip 发给对接人 / 上传登记表，随件注明批次目录名与题目数。
- 返修重交：修订题目的 [task].version 递增补丁号（1.0.0 → 1.0.1），只重交修订过的题目目录，批次目录名沿用原名加 `_fix<N>`（如 acme_b01_20260805_fix1），zip 名同步。供应商代号不随返修变更。

## 打包后硬自检命令

```bash
# 1) 五件套必须都在
unzip -l "$ZIP" | grep -qE 'instruction\.md|task\.toml' || { echo 'FAIL 五件套'; exit 1; }

# 2) 固定模板未改动（test.sh 含 rewardkit 调用、finalize.py 存在）
unzip -l "$ZIP" | grep -q 'tests/finalize.py' || { echo 'FAIL finalize.py'; exit 1; }

# 3) graded + gating 都在
unzip -l "$ZIP" | grep -q 'tests/graded/judge.toml' || { echo 'FAIL graded'; exit 1; }
unzip -l "$ZIP" | grep -q 'tests/gating/gating.toml' || { echo 'FAIL gating'; exit 1; }

# 4) 无残留（jobs/logs/reward/.git 等）
unzip -l "$ZIP" | grep -qE '(^|/)(jobs|logs|reward\.json|reward-details\.json|\.git)(/|$)' \
  && { echo 'FAIL 有残留'; exit 1; }

# 5) 无真实密钥（抽查）
unzip -p "$ZIP" '*/task.toml' | grep -qE 'sk-[A-Za-z0-9]|AKIA|BEGIN .*PRIVATE KEY' \
  && { echo 'FAIL 含密钥'; exit 1; }

# 6) 无嵌套 zip
unzip -l "$ZIP" | grep -qE '\.zip$' && { echo 'FAIL 嵌套 zip'; exit 1; }

echo 'PASS'
```

## Rubric 自检脚本（G3 指标）

```python
"""在题包目录下运行：python check_rubric.py <题目目录> <难度L2..L5>

注意：dimension 只在 [[metadata.rubric_index]] 登记（规范 6.7），judge.toml 的
[[criterion]] 不含 dimension 字段；锚点占比 / 维度覆盖从 rubric_index 统计。
"""
import sys, tomllib, pathlib

root = pathlib.Path(sys.argv[1]); diff = sys.argv[2]
mins = {"L2": 8, "L3": 12, "L4": 18, "L5": 25}[diff]

def load(p):
    with open(p, "rb") as f: return tomllib.load(f)

judge = load(root / "tests/graded/judge.toml")
gating = load(root / "tests/gating/gating.toml")
toml = tomllib.loads((root / "task.toml").read_text(encoding="utf-8"))
idx = toml["metadata"].get("rubric_index", [])

crits = list(judge.get("criterion", [])) + list(gating.get("criterion", []))
ok = True

def chk(name, cond):
    global ok
    print(("PASS" if cond else "FAIL") + " " + name)
    if not cond: ok = False

# 条数与结构（judge+gating 全部 criterion）
chk(f"条数≥{mins}", len(crits) >= mins)
chk("Critical≥2", sum(1 for c in crits if c.get("weight") == 10.0 and not c.get("negate")) >= 2)
chk("仅binary", all(c.get("type") == "binary" for c in crits))
judge_c = judge.get("criterion", [])
gating_c = gating.get("criterion", [])
chk("权重∈{3,7,10}", all((c.get("weight") or 0) in (3.0, 7.0, 10.0) for c in judge_c))
chk("gating不写weight", all(c.get("weight") is None for c in gating_c))
neg = sum(1 for c in crits if c.get("negate"))
chk("负向≥20%", len(crits) > 0 and neg / len(crits) >= 0.20)
chk("gating≥1", len(gating.get("criterion", [])) >= 1)

# id 一致性：judge+gating 的 id 集合 vs rubric_index
idx_ids = {r["id"] for r in idx}
crit_ids = {c["id"] for c in crits}
chk("id与rubric_index一致", idx_ids == crit_ids)

# 维度统计从 rubric_index（dimension 登记处）
graded_idx = [r for r in idx if not r.get("gating")]
pos_idx = [r for r in graded_idx if not r.get("negate")]
S_judge = sum(r.get("weight", 0) for r in pos_idx)
anchor_w = sum(r.get("weight", 0) for r in pos_idx
               if r.get("dimension") in ("交付物内容质量-准确性", "交付物内容质量-专业性"))
chk("锚点≥30%", S_judge > 0 and anchor_w / S_judge >= 0.30)
dims = {r.get("dimension") for r in graded_idx}
chk("指令遵循覆盖", any("指令遵循" in (d or "") for d in dims))
chk("内容质量覆盖", any("交付物内容质量" in (d or "") for d in dims))

sys.exit(0 if ok else 1)
```
