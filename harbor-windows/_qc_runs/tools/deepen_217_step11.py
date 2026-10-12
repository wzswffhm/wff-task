"""217 加深（第十一步）：同步 harbor-windows/_index 材料。

  known_issues.md  题号对照里 217 的难度与 required 数；新增 K21 记录本轮加深
  tasks_index.csv  217 行：version / hash / difficulty / f2p / p2p / status / frozen_at
  CHANGELOG.md     追加 2026-10-09 条目

三模型区分度在加深后必须重跑才能重新声明，因此 status 明确标注为「待重跑」，
不沿用 1.0.0 时代的 qualified 结论。
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-windows")
INDEX = ROOT / "_index"
TASK_ID = "wfflab__wreparse-217"
TODAY = "2026-10-09"
failed = False


def tree_hash(task_dir: Path) -> str:
    digest = hashlib.sha256()
    files = sorted(
        p for p in task_dir.rglob("*")
        if p.is_file() and "jobs" not in p.relative_to(task_dir).parts
        and p.relative_to(task_dir).as_posix() != "platform_import.json"
    )
    for path in files:
        rel = path.relative_to(task_dir).as_posix()
        digest.update(rel.encode("utf-8") + b"\n")
        digest.update(hashlib.sha256(path.read_bytes()).hexdigest().encode("ascii") + b"\n")
    return digest.hexdigest()


# ------------------------------------------------------------------ 计算事实
task_dir = ROOT / TASK_ID
new_hash = tree_hash(task_dir)
items = json.loads((task_dir / "tests/required_testcases.json").read_text(encoding="utf-8-sig"))
f2p = sum(1 for i in items if i.get("group") == "F2P")
p2p = sum(1 for i in items if i.get("group") == "P2P")
print(f"{TASK_ID}: hash={new_hash[:16]}…  f2p={f2p} p2p={p2p} total={len(items)}")

# ------------------------------------------------------------- known_issues.md
path = INDEX / "known_issues.md"
text = path.read_text(encoding="utf-8")
old_line = ("- `wfflab__wreparse-217` —— 文件系统与路径（NTFS 重解析点）｜L3｜"
            "required **13 F2P + 11 P2P = 24**")
new_line = (f"- `wfflab__wreparse-217` —— 文件系统与路径（NTFS 重解析点）｜**L4**｜"
            f"required **{f2p} F2P + {p2p} P2P = {len(items)}**")
if text.count(old_line) == 1:
    text = text.replace(old_line, new_line)
    print("ok known_issues.md: 题号对照已更新（L3→L4，24→36）")
else:
    print(f"!! known_issues.md: 题号对照锚点命中 {text.count(old_line)} 次")
    failed = True

k21 = """
| K21 | 重要变更 | **`wfflab__wreparse-217` 已按 215 的 L4 难度设计加深（1.1.0 → 1.2.0）**：原题的行为依据是一份把规则写全的契约文档，模型照抄即可，因此停在 L3。本轮补齐 L4 所需的「信息不完备 + 自我一致性陷阱」：① 新增真机实测的 provider 权威事实 `environment/workspace/assets/observed-provider-facts.json`，契约文档补 §10 声明它不覆盖 provider 层返回值形状，两者冲突时以实测事实为准（对应 215 的「`docs/FORMAT.md` 是草稿、`assets/` 样本才是唯一权威」）；② 新增可见冒烟测试 `environment/workspace/tests/test_wreparse_basic.ps1`，只验证「自己产出的报告自己能读懂」，**当前带偏差的实现同样全过**（对应 215 的「可见冒烟测试掩盖问题」）；③ 新增 6 条契约一致性检查（导出面恰好六个函数、报告字段集合恰为五项、排序与宿主 culture 无关、未跟随不得报 cycle/broken_target、普通条目 InScope 恒 false、Target 类型稳定），required 由 30 条增至 **36 条**；④ 夹具有意加入 `Z.txt` / `Ä.txt` / `ö.txt`，其序数顺序与区域设置敏感顺序相反，用 `Sort-Object` 修排序必然踩中。 | 该题的 `task_version` / `task_hash` / `image_ref` 再次改变，**1.0.0 时代的 `qualification_summary.json`（QWEN 2 / OPUS 3、`qualified: true`）不再适用** | 本机控制组已复验通过（Oracle 3×`VALID/1`、NOP 3×`VALID/0`，证据 `_qc_runs/controls_217_v120.json`）；**三模型区分度必须重跑后才能重新声明 qualified** |
"""
anchor = "\n## 题号对照（本目录 2 题）"
if "| K21 |" in text:
    print("!! known_issues.md 已含 K21")
    failed = True
elif text.count(anchor) == 1:
    text = text.replace(anchor, k21 + anchor)
    print("ok known_issues.md: 新增 K21")
else:
    print(f"!! known_issues.md: K21 锚点命中 {text.count(anchor)} 次")
    failed = True
path.write_text(text, encoding="utf-8")

# ------------------------------------------------------------- tasks_index.csv
path = INDEX / "tasks_index.csv"
raw = path.read_text(encoding="utf-8-sig")
rows = list(csv.reader(io.StringIO(raw)))
header = rows[0]
out_rows = [header]
updated = 0
for row in rows[1:]:
    if not row:
        continue
    rec = dict(zip(header, row))
    if rec.get("task_id") == TASK_ID:
        rec["task_version"] = "1.2.0"
        rec["task_hash"] = new_hash
        rec["difficulty"] = "L4"
        rec["f2p"] = str(f2p)
        rec["p2p"] = str(p2p)
        rec["status"] = ("已按 215 的 L4 设计加深（1.2.0）；本机控制组复验通过"
                         "（Oracle 3×VALID/1、NOP 3×VALID/0）；"
                         "三模型区分度待重跑后重新声明")
        rec["frozen_at"] = TODAY
        updated += 1
    out_rows.append([rec.get(h, "") for h in header])

buf = io.StringIO()
writer = csv.writer(buf, lineterminator="\n", quoting=csv.QUOTE_ALL)
writer.writerows(out_rows)
path.write_text(buf.getvalue(), encoding="utf-8")
print(f"ok tasks_index.csv: 更新 {updated} 行（version=1.2.0, L4, f2p={f2p}, p2p={p2p}）")
if updated != 1:
    print("!! tasks_index.csv 更新行数异常")
    failed = True

# ---------------------------------------------------------------- CHANGELOG.md
path = INDEX / "CHANGELOG.md"
text = path.read_text(encoding="utf-8")
entry = f"""## [wreparse-217 难度加深 L3 → L4] - {TODAY}

### 变更原因

`wfflab__wreparse-217` 与 `wfflab__wfmt-215` 同为交付题包，但难度不对等：215 是 **L4**，
217 只有 **L3**。根因在**行为依据的完备程度**——215 的 `docs/FORMAT.md` 是早期草稿、
与真实布局脱节，`assets/` 下的样本才是唯一权威，模型必须逆向；而 217 的
`docs/REPARSE-CONTRACT.md` 把规则逐条写全，模型照抄即可。

甲方 QC 门禁两题都已通过（215：15 项；217：30 项），所以差距不在 QC 是否达标，
而在难度等级本身。

### 变更内容（215 → 217 的 L4 设计复刻）

1. **权威依据分流**：新增 `environment/workspace/assets/observed-provider-facts.json`
   （真机 Windows 11 + NTFS + Windows PowerShell 5.1 实测的 6 条 provider 事实）；
   契约文档新增 §10，声明它只规定**语义**、不规定 provider 层返回值形状，
   两者在实现细节上冲突时以实测事实为准。
2. **自我一致性陷阱**：新增可见冒烟测试 `environment/workspace/tests/test_wreparse_basic.ps1`，
   只验证「模块能导入、报告结构存在、能序列化」。**当前带 23 处契约偏差的实现同样全部通过**，
   与 215「pack 能读回自己的输出、所以可见冒烟测试掩盖问题」同构。
   `instruction.md` 明确声明通过它不代表符合契约。
3. **新增 6 条契约一致性检查**（required 30 → **36**：{f2p} F2P + {p2p} P2P）：
   模块导出面恰好六个函数（§2）、报告字段集合恰为五项（§3）、排序与宿主 culture 无关
   （§6.1/§6.2）、未给 `-Follow` 时不得报 `cycle`/`broken_target`（§7）、
   普通条目 `InScope` 恒为 `false`（§3.1）、`Target` 类型稳定（§3.1）。
   另把 `target-is-serialised-as-string` 登记为 P2P（合法解修复前后都必须通过）。
4. **夹具增强**：`scanroot` 下新增 `Z.txt` / `Ä.txt` / `ö.txt`。三者的**序数顺序**与
   **区域设置敏感顺序**相反（实测：`Sort-Object` 在 zh-CN 下给出 `Ä, ö, …, Z`，
   序数规则要求 `Z, Ä, ö`），因此把排序委托给 `Sort-Object` 的实现必然失败。
   文件名以字符码构造，避免脚本编码影响。
5. **候选实现新增 5 处可观测偏差**并同步 Golden：导出面放宽为 `*`（psm1 + manifest 两处）、
   用 `Sort-Object` 排序记录、错误列表只按 `Code` 排序、默认扫描也解析目标并报
   `broken_target`、普通条目写入 `InScope`。
6. **版本与元数据**：`task.toml` `difficulty` L3 → **L4**、`[task].version` → **1.2.0**；
   `rubric.json` 新增 `public-surface` 项并把 9 项权重重新配平到合计 1.0；
   `instruction.md` 增补第 9~12 条行为要求与第 12~17 条验收项。

### 复验证据

- **本机控制组**（`_qc_runs/controls_217_v120.json`）：
  Oracle 3 次全部 `VALID` / `formal_score=1` / 36 of 36；
  NOP 3 次全部 `VALID` / `formal_score=0` / 13 of 36（13 个 P2P 全过、23 个 F2P 全挂）。
- **包哈希**：`task_hash = {new_hash}`。

### 待办

- 三模型区分度（Qwen ×3 / Opus ×3 / GLM ≥1 / Kimi ≥1）必须重跑，原 `qualified: true`
  （`task_versions: ["1.0.0"]`）不再适用。
- 甲方 QC 工具的动态门禁需要 **Windows 容器**（本机 Docker 当前为 WSL2/Linux 引擎、
  `Containers` 可选功能为 `Disabled`），待环境恢复后重跑。

"""
anchor = "## [范围对齐 + 标准 Harbor 兼容] - 2026-10-08"
if "wreparse-217 难度加深" in text:
    print("!! CHANGELOG.md 已含本条目")
    failed = True
elif text.count(anchor) == 1:
    text = text.replace(anchor, entry + anchor)
    print("ok CHANGELOG.md: 新增 2026-10-09 条目")
else:
    print(f"!! CHANGELOG.md: 锚点命中 {text.count(anchor)} 次")
    failed = True
path.write_text(text, encoding="utf-8")

print("\nRESULT:", "部分失败" if failed else "第十一步完成")
sys.exit(1 if failed else 0)
