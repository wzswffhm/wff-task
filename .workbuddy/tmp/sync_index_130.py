# -*- coding: utf-8 -*-
"""1.3.0 收口：同步 harbor-windows/_index 四件套（本轮 D1–D6 加深）。

  tasks_index.csv   217 行：version / hash / f2p / p2p / status
  known_issues.md   题号对照行 required 数改为 45+15=60；追加 K22 记录本轮加深
  CHANGELOG.md      顶部追加 2026-10-09 的 1.3.0 条目
  checksums.sha256  按现有格式重算整目录（含 jobs/，与 1.2.0 口径一致）

复现自 deepen_217_step11.py 的 tree_hash（排除 jobs/ 与 platform_import.json）。
用法：python sync_index_130.py
"""
from __future__ import annotations

import csv
import hashlib
import pathlib
import sys

ROOT = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-windows")
INDEX = ROOT / "_index"
TASK_DIR = ROOT / "wfflab__wreparse-217"
TASK_ID = "wfflab__wreparse-217"
NEW_VER = "1.3.0"
OLD_VER = "1.2.0"
TODAY = "2026-10-09"
F2P, P2P = "45", "15"

STATUS = ("已按 D1–D6 激进档再次加深（1.3.0）；本机控制组复验通过"
          "（Oracle 3×VALID/60、NOP 3×VALID/0）；三模型区分度待重跑后重新声明")

K22 = ("| K22 | 重要变更 | **`wfflab__wreparse-217` 再次加深（1.2.0 → 1.3.0，D1–D6）**："
       "1.2.0 后四模型 8 场全满分（Qwen/Opus/Kimi/GLM 均 36/36），`--score-only` 判定 `False`"
       "（Opus 3 vs Qwen 3 积分相同），区分度失败。处置：D1 契约黑盒化（以 15+ 实测样例替代规则）、"
       "D1 题面去答案、D2 矛盾源（draft 草稿含 9 处反向陷阱 + facts 6 → 16 条纯观测）、"
       "D4 夹具加深 8 层链、D3 required 36 → **60**（45 F2P / 15 P2P）、"
       "D5 冒烟测试不再检查字段结构、D6 新增验收 18 可复现自证脚本。"
       "控制组：Oracle 3×VALID/60、NOP 3×VALID/0（`_qc_runs/controls_217_v130.json`）。"
       "三模型区分度待重跑后重新声明。 |")

CHANGELOG = f"""## [wreparse-217 再次加深：1.2.0 → 1.3.0（D1–D6 激进档）] - {TODAY}

### 变更原因

1.2.0 按 215 的 L4 设计加深后，四模型 8 场验证**全部满分**（Qwen 3×36/36、Opus 3×36/36、
Kimi 1×36/36、GLM 1×36/36），`run_model_validation.py --score-only` 判定 **False**
（`各模型最终积分相同且不全为 0（Opus 3 vs Qwen 3）`）→ 区分度失败。
根因是加深**只增加了"要检查什么"，没有改变"答案可从文档直接抄出"**这一本质。

### 变更内容（D1–D6）

1. **D1 契约黑盒化**：`docs/REPARSE-CONTRACT.md` 删除 §2/§3/§4/§5/§6/§7 的规则文本，
   改为 **15+ 个实测样例**（8 条 reparse Record 对照、空树完整 JSON、`-MaxDepth` 0/-1/1 三组、
   `-Follow` 的 stats 与 errors、`link-in\\readme.txt` 前缀、canonical/within_root 对照、
   `Z/Ä/ö` 实测次序、7 个错误码的实测 Message），并明示"唯一允许照抄的只有 API 签名表"。
2. **D1 题面**：`instruction.md` 的「必须满足的行为」12 条规则复述与「用户可见验收」17 条
   答案式断言全部去答案，改为"只给要覆盖的情形、不给期望值"；新增**验收 18 可复现自证脚本**。
3. **D2 矛盾源**：新增 `docs/REPARSE-CONTRACT.draft.md`（含 9 处与正式契约/实测相反的陷阱，
   如"报告含 GeneratedAt 时间戳"、"`-Follow` 默认开启"、"`LinkType` 非空即重解析点"、
   "直接用 `Sort-Object`"）；`assets/observed-provider-facts.json` 6 → **16 条纯观测**
   （三种文化下的 `Sort-Object` 实测、reparse tag、相对目标解析探测、depth/maxdepth 探测等），
   只给数据不给结论。
4. **D4 夹具**：`tests/prepare.ps1` 新增 8 层深链（`level1..level8` + 两个文件）。
5. **D3 判据**：`tests/run_tests.ps1` +24 条检查 → **60 条**；
   `required_testcases.json` 36 → **60**（45 F2P / 15 P2P）；
   `rubric.json` 9 项权重保持合计 1.0、60/60 全覆盖，`task_version` → 1.3.0。
6. **D5 冒烟测试**：`tests/test_wreparse_basic.ps1` 不再检查 `Records/Errors/Stats` 字段名
   与 JSON 结构，通过它完全无法推断报告形态。
7. **版本与元数据**：`task.toml` / `source.json` / `tests/run_tests.ps1` → **1.3.0**；
   `difficulty` 保持 **L4**、step 上限保持 **40**（与其它题包口径一致）。

### 复验证据

- **本机控制组 3+3**（`_qc_runs/controls_217_v130.json`）：
  Oracle 3 次全部 `VALID` / `formal_score=1` / **60 of 60**；
  NOP 3 次全部 `VALID` / `formal_score=0` / 22 of 60（15 个 P2P 全过 + 7 个 F2P 过）。
- `task_hash` 由 `tree_hash()` 重算（排除 `jobs/` 与 `platform_import.json`）。
- 已砍掉三条不可行判据：`access_denied`（判分进程为管理员会绕过 ACL）、UNC（容器
  bind filter 语义不同）、同名不同大小写决胜（NTFS 不允许同名文件）。

### 待办

- 三模型区分度必须重跑；若仍全满分，需进一步加深（候选方向：删除契约文档、只留 assets）。
- 甲方 QC 动态门禁需 Windows 容器，待环境恢复后重跑。

"""


def tree_hash(task_dir: pathlib.Path) -> str:
    digest = hashlib.sha256()
    files = sorted(
        p for p in task_dir.rglob("*")
        if p.is_file() and "jobs" not in p.relative_to(task_dir).parts
        and p.relative_to(task_dir).as_posix() != "platform_import.json"
    )
    for path in files:
        rel = path.relative_to(task_dir).as_posix()
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def main() -> int:
    th = tree_hash(TASK_DIR)
    print(f"task_hash = {th}")

    # ---- tasks_index.csv ---------------------------------------------------
    csv_path = INDEX / "tasks_index.csv"
    with open(csv_path, encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
        fields = list(rows[0].keys())
    hit = 0
    for row in rows:
        if row.get("task_id") == TASK_ID:
            row["task_version"] = NEW_VER
            row["task_hash"] = th
            row["f2p"] = F2P
            row["p2p"] = P2P
            row["status"] = STATUS
            row["frozen_at"] = TODAY
            hit += 1
    with open(csv_path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    print(f"[OK] tasks_index.csv: 更新 {hit} 行 -> version={NEW_VER} f2p={F2P} p2p={P2P}")

    # ---- known_issues.md ---------------------------------------------------
    ki_path = INDEX / "known_issues.md"
    ki = ki_path.read_text(encoding="utf-8")
    old_line_fragment = "required **23 F2P + 13 P2P = 36**"
    new_line_fragment = "required **45 F2P + 15 P2P = 60**"
    if old_line_fragment in ki:
        ki = ki.replace(old_line_fragment, new_line_fragment)
        print("[OK] known_issues.md: 题号对照行 required -> 45+15=60")
    else:
        print("[SKIP] known_issues.md: 未找到 required 对照行（可能已更新）")
    if "K22" not in ki:
        # 追加在 K21 所在表格的最后一行之后
        lines = ki.splitlines(keepends=True)
        k21_idx = next((i for i, ln in enumerate(lines) if "| K21 " in ln), None)
        if k21_idx is None:
            print("[FAIL] 找不到 K21 行，无法定位插入点")
            return 1
        lines.insert(k21_idx + 1, K22 + "\n")
        ki = "".join(lines)
        print("[OK] known_issues.md: 追加 K22")
    else:
        print("[SKIP] known_issues.md: K22 已存在")
    ki_path.write_text(ki, encoding="utf-8", newline="\n")

    # ---- CHANGELOG.md ------------------------------------------------------
    cl_path = INDEX / "CHANGELOG.md"
    cl = cl_path.read_text(encoding="utf-8")
    marker = "# CHANGELOG"
    if CHANGELOG.splitlines()[0] in cl:
        print("[SKIP] CHANGELOG.md: 1.3.0 条目已存在")
    else:
        idx = cl.find(marker)
        idx = cl.find("\n", idx) + 1
        cl = cl[:idx] + "\n" + CHANGELOG + cl[idx:]
        cl_path.write_text(cl, encoding="utf-8", newline="\n")
        print("[OK] CHANGELOG.md: 顶部插入 1.3.0 条目")

    # ---- checksums.sha256 --------------------------------------------------
    ck_path = INDEX / "checksums.sha256"
    template = ck_path.read_text(encoding="utf-8").splitlines()[0] if ck_path.is_file() else ""
    sep = template[66:68] if len(template) > 68 else "  "
    out = []
    for path in sorted(p for p in ROOT.rglob("*") if p.is_file()):
        rel = path.relative_to(ROOT).as_posix()
        h = hashlib.sha256(path.read_bytes()).hexdigest()
        out.append(f"{h}{sep}{rel}")
    ck_path.write_text("\n".join(out) + "\n", encoding="utf-8", newline="\n")
    print(f"[OK] checksums.sha256: 重算 {len(out)} 个文件（间隔符 {sep!r}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
