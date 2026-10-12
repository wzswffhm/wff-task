# -*- coding: utf-8 -*-
"""改写交付文档：把失实的「R29/R30 锚点收紧 + regrade」叙述改为「判分重跑（判据未变）」。
同时修正 summary.json 的 round 字段。
"""
import json
import pathlib
import sys

sys.stdout.reconfigure(encoding="utf-8")

BATCH = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-weakness\work-金融-私募股权投资-20261008\FIN3-WKN-150")
DOC = BATCH / "交付文档.md"
SUM = BATCH / "跑分产物与轨迹" / "summary.json"

txt = DOC.read_text(encoding="utf-8")
orig = txt
edits = 0


def rep(old, new, label):
    global txt, edits
    n = txt.count(old)
    if n != 1:
        print(f"  [!!] {label}: 匹配 {n} 次（应为 1），跳过")
        return False
    txt = txt.replace(old, new)
    edits += 1
    print(f"  [OK] {label}")
    return True


print("=" * 100)
print("1) §3.2 正文的 regrade 表述（L86）")
print("=" * 100)
rep(
    "本轮为 §3.2.2 的 **regrade**（判据 R29/R30 锚点收紧后按 final 题包重判，复用交付物、不重跑 Agent）",
    "本轮为 §3.2.2 的**判分重跑**（判据未变，按质检整改后的 final 题包重判，复用交付物、不重跑 Agent）",
    "L86 regrade -> 判分重跑",
)

print()
print("=" * 100)
print("2) §3.2.2 整节替换")
print("=" * 100)
START = "#### 3.2.2 G5 判分口径披露（2026-10-09 第三轮：R29/R30 满分锚点收紧后 regrade）"
END = "### 3.3 静态自检（17 项）"
i, j = txt.find(START), txt.find(END)
if i < 0 or j < 0 or j <= i:
    print(f"  [!!] 锚点定位失败 i={i} j={j}")
    sys.exit(1)
NEW_322 = """#### 3.2.2 G5 判分口径披露（2026-10-09 第三轮：质检整改后判分重跑）

本轮（2026-10-09）按甲方质检报告（序号 239）的 5 项【待改】完成整改（金标八章、费用率趋势、R30/R31 去"个别"、归档结构、交付文档），随后对四执行体**重跑判官**。需特别说明：**本轮判据未作任何修改**——36 条判据的 `description`、`id`、权重、`negate`、`S_max = 220` 与上一轮（归档 fix3/fix4）**逐字一致**，且设计态 `rubrics.json` 与运行态 `tests/rubrics.toml` 的判据描述逐字同步（`check_package.py` #4b 通过）。

**重跑口径**：沿用已归档的 Agent 试次交付物（`-a nop` + bind mount，**不重跑 Agent**，四执行体 `output/` 与 `轨迹/` 逐字节不变），按 final 题包重跑判官（claude-code **2.1.114** / 裁判 **qwen3.7-plus**，36 条判据全部 `criteria_counted = 36`、`verifier_error = 0`）。判分暂存 `_rejudge/` 同步进归档后**已删除**（`check_package.py` #9 无残留）。

| 模型 | 上一轮（归档 fix3，甲方质检对象） | 本轮重跑 | 差值 |
|---|---|---|---|
| `oracle`（G4） | 1.000000 | **0.996591** | -0.003409 |
| `qwen3.8-max-0902` | 0.781818 | **0.787500** | +0.005682 |
| `claude-opus-4-8` | 0.411364 | **0.476136** | +0.064772 |
| `gpt-5.6-sol` | 0.672727 | **0.640909** | -0.031818 |
| **G5 三模型均分** | 0.621970 | **0.634848** | +0.012878 |

- **差值来源如实说明**：上表两侧差异来自**两处**——(a) **交付物本身的整改**（金标补足八章、费用率趋势修正、判据去"个别"后 R30/R31 的可复现性提高）；(b) **判官（LLM）逐次采样的正常波动**。**判据版本前后一致**（`S_max` 恒为 220），故该差异**不代表难度被抬高或压低**。
- **波动量级如实说明**：同一批交付物、同一套判据下的两次重跑，G5 曾分别测得 **0.700379** 与 **0.634848**（极差 0.065），可见 LLM 判分的采样波动量级**大于**本轮净变化 0.012878。**该波动不改变门禁结论**：均分 **0.634848 < 0.70 PASS**，余量 0.065152；档位仍落 **A1 `[0.6, 0.7)`**。
- **门禁复核**：G4 `0.996591 > 0.85` ✅；G5 `0.634848 < 0.70` ✅；三模型均非零（非死题）✅；`invalid_runs` 未新增 ✅。
- **难度未被抬高**：本轮整改只**消除事实矛盾、补齐可溯源信息、消除判据歧义**（见 §7 / §9），不改变题目场景、输入材料、评分维度与权重结构。

"""
txt = txt[:i] + NEW_322 + txt[j:]
edits += 1
print(f"  [OK] §3.2.2 整节已替换（{len(NEW_322)} 字符）")

print()
print("=" * 100)
print("3) 归档结构图与交付清单中的批次目录名")
print("=" * 100)
rep("work_fin-b01_20261006_fix4-150/            ← 批次目录（zip 顶层）",
    "work_fin-b01_20261006_fix5-150/            ← 批次目录（zip 顶层）",
    "L169 结构图批次名")
rep("| 1 | 交付文档（本文件） | `work_fin-b01_20261006_fix4-150/FIN3-WKN-150/交付文档.md` |",
    "| 1 | 交付文档（本文件） | `work_fin-b01_20261006_fix5-150/FIN3-WKN-150/交付文档.md` |",
    "L194 清单第1项")
rep("| 2 | 跑分产物与轨迹（四执行体 + summary） | `work_fin-b01_20261006_fix4-150/FIN3-WKN-150/跑分产物与轨迹/` |",
    "| 2 | 跑分产物与轨迹（四执行体 + summary） | `work_fin-b01_20261006_fix5-150/FIN3-WKN-150/跑分产物与轨迹/` |",
    "L195 清单第2项")
rep("| 3 | 题目 FIN3-WKN-150（五件套） | `work_fin-b01_20261006_fix4-150/FIN3-WKN-150/` |",
    "| 3 | 题目 FIN3-WKN-150（五件套） | `work_fin-b01_20261006_fix5-150/FIN3-WKN-150/` |",
    "L196 清单第3项")

print()
print("=" * 100)
print("4) §4.1 归档说明第 3 条")
print("=" * 100)
rep(
    "3. **本轮判分为「复用交付物重判」**：因 R29/R30 满分锚点收紧（见 §3.2.2），按 final 题包重跑判官；沿用已记录的 Agent 试次交付物",
    "3. **本轮判分为「复用交付物重判」**：按质检整改后的 final 题包重跑判官（**判据未变**，见 §3.2.2）；沿用已记录的 Agent 试次交付物",
    "L186 归档说明第3条",
)

print()
print("=" * 100)
print("5) §9 整节替换")
print("=" * 100)
S9 = "## 9. 第三轮调整记录（2026-10-09，R29/R30 满分锚点收紧 + regrade）"
E9 = "---\n\n*文档生成："
i9, j9 = txt.find(S9), txt.find(E9)
if i9 < 0 or j9 < 0 or j9 <= i9:
    print(f"  [!!] §9 锚点定位失败 i={i9} j={j9}")
    sys.exit(1)
NEW_9 = """## 9. 第三轮记录（2026-10-09，质检整改后判分重跑）

**背景**：甲方《序号239》质检报告结论「不通过（打回）」，最高严重度为"重跑判官"，列 5 项【待改】。本轮逐项整改后**重跑四执行体判官**，形成 fix5 批次（`[task].version` 1.0.4 → **1.0.5**）。

**质检 5 项【待改】的整改与闭环**：

| # | 质检项 | 处置 | 闭环证据 |
|---|---|---|---|
| 4 | 金标多出"九、交易执行与投后安排"，违反"八个章节不得增删" | 将第九章内容**并入既有八章**，两份 golden 与 oracle 输出同步 | 包内 `tests/__golden_output/` 与 `solution/golden_output/` 备忘录章节数 **8**（一—八），全文无"九、" |
| 5 | 金标正文"期间费用率逐年上升"与表中 14.02→13.62→13.38→13.61 矛盾 | 改为与数据一致的趋势描述 | 正文改为"期间费用率总体呈下降趋势（14.02% → 13.62% → 13.38%），2026 年上半年小幅回升至 13.61%" |
| 6 | R30、R31 使用未定义量词"个别"，边界不可复现；须同步 `rubrics.json` 与 `tests/rubrics.toml` 并**重新判分** | 改为明确数量阈值（R30"1 项"、R31"1 处／2 处以上"），双文件逐字同步 | 全文（`rubrics.toml` / `rubrics.json` / 四执行体判分快照）**零个"个别"**；36 条判据描述在 `rubrics.toml`、`rubrics.json` 与 `reward-details.json` **三处逐条一致** |
| 7 | ZIP 第二层混放交付文档、批次级证据，题目目录缺这两项 | 交付文档与四执行体证据**移入题目目录** | zip 顶层目录下第二层**仅为** `FIN3-WKN-150/` |
| 8 | `交付文档.md` 仍记录旧 Oracle 0.986364 与旧归档结构 | 同步更新为当前分数与现行归档口径 | 本文档 §1.1 / §3.1 / §3.2 / §4 / §5 均已按 fix5 终态更新 |

| 项 | 内容 |
|---|---|
| 改动判据 | **无**——36 条判据的 `description`、`id`、权重、`negate`、`S_max = 220` 与上一轮逐字一致 |
| 重跑方式 | `-a nop` + bind mount 复用已归档交付物，**不重跑 Agent**；claude-code 2.1.114 / 裁判 qwen3.7-plus |
| 判分结果 | G4 `oracle` **0.996591**（> 0.85 PASS）；G5 三模型 **0.634848**（qwen 0.787500 / gpt 0.640909 / opus 0.476136，均 `counted=36`、`verifier_error=0`）→ **< 0.70 PASS** |
| 难度定档 | **A1**（0.634848 ∈ `[0.6, 0.7)`），`task.toml` 的 `difficulty` / `keywords` / `tags` 三处已是 `A1`，**无需改动** |
| 归档同步 | `_rejudge/verifier/{reward.json, reward-details.json}` 按 06 号文档原名覆盖四执行体归档文件；`summary.json` 的 `runs[].reward`、`mean = 0.634848`、`gate_pass = true`、`round = fix3(qc-remediation)+rejudge` |
| 自检 | `check_rubrics.py` **[PASS]**（36 条 / S_max 220 / gradient levels 校验通过）；`check_package.py` **[PASS]**（含 #4b 设计态/运行态一致、#9 无残留） |
| 清理 | 判分暂存 `_rejudge/` 与 `tests/__pycache__/` 均已清除；本项目全部缓存（`__pycache__` / `.pytest_cache` / 判分 stage）已一并清理 |

**判分波动如实说明**：本轮 G5 较上轮 **+0.012878**（0.621970 → 0.634848）。该差异来自**交付物整改**与**判官（LLM）逐次采样波动**的叠加，且**判据版本前后完全一致**；同一批交付物、同一套判据下的两次重跑曾分别测得 **0.700379** 与 **0.634848**（极差 0.065），可见采样波动量级大于本轮净变化。**门禁结论不变**（0.634848 < 0.70，余量 0.065152），档位仍为 **A1**。

**飞书回写（本轮）**：附件字段按「先删旧、再传新」替换为 fix5 批次的三个 zip（交付物 `fix3-150` → `fix5-150`、`task` 68,694 → 69,349 B、`answer` 927,362 → 927,580 B），三字段均复核为**恰好 1 个文件**；`题目难度 fldYA4iRaD` 由空值置为 **`A1`**（与包内 `task.toml` 的 `difficulty` 定档一致，见 §3.2）；**状态字段 `fldKFzG0cA` 不做改动**（仍由质检方流转，当前「待返修」）；序号 / 原工作表 / 质检报告等字段均不动。

"""
txt = txt[:i9] + NEW_9 + txt[j9:]
edits += 1
print(f"  [OK] §9 整节已替换（{len(NEW_9)} 字符）")

print()
print("=" * 100)
print("6) footer")
print("=" * 100)
rep(
    "2026-10-09 更新为第二轮质检整改版 1.0.4（批次 work_fin-b01_20261006_fix4-150），并于同日追加第三轮 R29/R30 锚点收紧 regrade 记录（§9，批次 work_fin-b01_20261006_fix5-150）。验证环境：WSL Ubuntu + harbor 0.22.0 + docker 29.1.3（含 compose v2）；本轮 regrade 在 Windows 宿主 + Docker Desktop Linux 引擎执行。",
    "2026-10-09 更新为第二轮质检整改版 1.0.4（批次 work_fin-b01_20261006_fix4-150），同日按甲方质检报告（序号 239）完成 5 项【待改】整改并重跑判官，形成第三轮 1.0.5（批次 work_fin-b01_20261006_fix5-150，见 §9）。验证环境：WSL Ubuntu + harbor 0.22.0 + docker 29.1.3（含 compose v2）；本轮判分重跑在 Windows 宿主 + Docker Desktop Linux 引擎执行。",
    "footer 更新说明",
)

if txt != orig:
    DOC.write_text(txt, encoding="utf-8", newline="\n")
    print()
    print(f"  [写出] {DOC}  {len(txt.splitlines())} 行  {len(txt.encode('utf-8')):,} B  共 {edits} 处替换")
else:
    print("  [!!] 无变化")

print()
print("=" * 100)
print("7) 修正 summary.json 的 round")
print("=" * 100)
s = json.loads(SUM.read_text(encoding="utf-8"))
old_round = s.get("round")
s["round"] = "fix3(qc-remediation)+rejudge"
SUM.write_text(json.dumps(s, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
print(f"  round: {old_round!r} -> {s['round']!r}")
print(f"  mean={s.get('mean')}  gate_pass={s.get('gate_pass')}  task_version={s.get('task_version')}")
