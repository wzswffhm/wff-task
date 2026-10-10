# -*- coding: utf-8 -*-
"""A) 追加 §8 交付前自检修复记录（151 有同款章节，展示逐项闭环）
   B) 扫 v4 归档轨迹/文本的不可见空白 U+00A0 / U+3000（149 提示 3 / 151 提示 4）
"""
import pathlib
import sys

sys.stdout.reconfigure(encoding="utf-8")

H = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-weakness")
BATCH = H / "work_fin-b01_20261009-152"
DOC = BATCH / "交付文档.md"
RUNS = BATCH / "跑分产物与轨迹"

# ── A) 追加修复记录 ──
SECTION = """
## 8. 交付前自检修复记录（逐项闭环）

本节按 151（序号267）同款章法，列示本轮交付前自检发现并已闭环的问题，供质检复核。

| # | 自检发现的问题 | 影响的门禁/质检项 | 处置 | 状态 |
|---|---|---|---|---|
| 1 | `tests/rubrics.toml` R16 结果数写成 **632.456518**，与其自身算式 `(15.276527 + 3.3) × 34` 的真值 **631.601918** 差 0.8546 > ±0.5 容差，且该值无法由材料推出 | 判据锚点须可由材料唯一推出（pitfall 案例 2/4） | 判据结果数改为 **631.601918** 并要求写出算式；金标按真值输出；双文件同步 | ✅ G4 判官复核通过（R16 value=1） |
| 2 | R34 所列七目录计数 8+17+14+4+5+6+4=**58**，却写「七行合计等于 60」（漏根目录 2 个散件） | 同上（判据自相矛盾） | 改为「七目录小计 58 + 根目录散件 2 = 总数 60」，金标按「七目录分列 + 根散件 2 行 + 合计 60 行」输出 | ✅ G4/G5 判官按新文本核验（opus 触发该条失分，证明判据生效） |
| 3 | `tests/__golden_output`（旧版）与 `solution/golden_output` 3 个文件不一致，另有违规残留目录 `tests/__golden_output__`（结尾双下划线） | golden 双份逐字节一致 | 以 `solution/golden_output` 为准复制到标准目录、删除残留目录（旧版备份至 `_backup/FIN3-WKN-152-golden-old-20261010`） | ✅ 两目录 7 文件 SHA-256 全等 |
| 4 | 金标旧版仅覆盖 37 条判据中的部分要求（备忘录无「数据核验」四条分列表、无 `Tieout_Detail` 表、无 25 格钦定网格、无材料清点与四项方法论理由） | G4 ≥0.85（否则门禁 FAIL） | 改造 `reproduce.py`（40,566 → 67,478 B），金标重生成并跑 40 条自检 | ✅ **40/40 PASS**，G4 = **1.000000** |
| 5 | 甲方 `validate_rubrics` 5 项 FAIL：设计态负分 `weight` 被写成正数（应 −7/−7/−7/−3） | json↔toml negate 集合一致、正分池==s_max | N01–N04 改回负权；正分池 228==s_max | ✅ FAIL 0 |
| 6 | 甲方 `validate_task_package` 3 项 ERROR：新增 R34/R35/R36 的 `criterion_type` 写成 `correctness`、`criterion_necessity` 写成 `重要` | 枚举须为 Objective/Subjective、Explicit/Implicit | 改为 `Objective`/`Explicit` | ✅ PASS |
| 7 | `check_rubric_style` FAIL：R18 含表格定位语「单元格」；R34–R36 的 `name` 与 `id` 不等 | 提问式/量词/措辞门禁、name==id | 「单元格」→「格位」；name 改为 id | ✅ FAIL 0 |
| 8 | `check_package #3` 提示：判据描述用交付物简称（`ipo_model`、`source_trace` 等） | 交付物须写全名（含前缀与扩展名） | 全部替换为 `FIN3-WKN-152_` 全名 | ✅ 提示消除 |
| 9 | 题面 `instruction.md` L58 把三类异常类型（重复导出/同月多值/量级错位）直接写出、L60 列出处置规则 | **答案不得写在题面**（红线） | 删除异常类型枚举与处置规则括号，仅保留「明细底表不带质量标注，须自行核验」 | ✅ 题面答案锚点 0 命中、引导性注释 0 命中 |
| 10 | 三个 zip 内 `solve.sh`/`test.sh` 权限 0o666 | **149 返修 #2**：须 0755 | 打包时显式写 `external_attr = 0o755 << 16` | ✅ 三 zip 均 0755 |
| 11 | `rubrics.json` 的 `_comment` 仍写「任务为 weakness 类（v2.0.0…）」 | 版本号一致性 | 改为 v4.0.0（本体与批次副本同步） | ✅ 无 v2.0.0 残留 |
| 12 | `task.toml` 申报 `difficulty = A3`，实测均分 0.590643 落 **A2** | 实测落档（不看申报值）；申报≠实测须整改 | `difficulty`/`keywords`/`tags` 三处同步为 A2 | ✅ 申报==实测 |
| 13 | 交付文档含 v2 旧数据（33 条/S_max 179/92.7%）、未回填占位符、§4 描述与实际结构相反 | 交付文档须反映终态 | 数据更新为 40 条/228/94.3%；7 个占位符回填；§4 按实际结构重写 | ✅ 残留扫描通过 |

**未做的处置（如实披露，见 §3.2.3）**：qwen `N01` 单条判官 reasoning 与 final answer 不一致（误扣 7 分），按既定决策**不 regrade**，理由与档位余量风险已在 §3.2.3 完整披露。

"""

raw = DOC.read_text(encoding="utf-8")
if "## 8. 交付前自检修复记录" in raw:
    print("  [--] §8 已存在")
else:
    DOC.write_text(raw.rstrip() + "\n" + SECTION, encoding="utf-8", newline="\n")
    print(f"  [OK] 追加 §8 修复记录  {len(DOC.read_text(encoding='utf-8').splitlines())} 行")

# ── B) 不可见空白扫描 ──
print()
print("=" * 94)
print("不可见空白扫描（U+00A0 / U+3000）—— 149 提示3 / 151 提示4")
print("=" * 94)
TXT_EXT = {".md", ".toml", ".json", ".py", ".sh", ".csv", ".txt", ".yaml", ".yml"}
bad = []
targets = []
# 题包本体（不含轨迹）
for p in (H / "FIN3-WKN-152").rglob("*"):
    if p.is_file() and p.suffix.lower() in TXT_EXT:
        targets.append(("本体", p))
# 批次（含归档，但跳过超大轨迹的 base64 类？全扫）
for p in BATCH.rglob("*"):
    if p.is_file() and p.suffix.lower() in TXT_EXT:
        targets.append(("批次", p))

for tag, p in targets:
    try:
        t = p.read_text(encoding="utf-8", errors="strict")
    except UnicodeDecodeError:
        continue
    except Exception:
        continue
    n3000 = t.count("　")
    n00a0 = t.count(" ")
    if n3000 or n00a0:
        bad.append((tag, p, n3000, n00a0))

if bad:
    print(f"  发现 {len(bad)} 个文件含不可见空白：")
    for tag, p, a, b in bad:
        rel = p.relative_to(H) if H in p.parents else p
        print(f"    [{tag}] {rel}  U+3000={a} U+00A0={b}")
else:
    print("  ✅ 全部文件 0 命中（U+3000=0, U+00A0=0）")

print()
print(">>> 完成")
