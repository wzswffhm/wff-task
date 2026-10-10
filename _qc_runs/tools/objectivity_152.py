# -*- coding: utf-8 -*-
"""152 v3 判据可核验性分析：
- 客观判据（含数值锚点 / 明确文件与行 / 二值结构）→ 判官难放水
- 主观判据（质量描述 / 论证类）→ 判官易给满分，是压分障碍
目标：找出"要压分必须改写"的判据。
"""
import pathlib
import re
import sys

import tomllib

sys.stdout.reconfigure(encoding="utf-8")

TASK = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-weakness\FIN3-WKN-152")
crit = tomllib.loads((TASK / "tests" / "rubrics.toml").read_text(encoding="utf-8"))["criterion"]

NUM_RE = re.compile(r"-?\d[\d,]*\.?\d*")
SUBJ = ["评分锚点", "质量", "论证", "合理", "清晰", "充分", "专业", "完整说明",
        "有依据", "阐述", "表述", "可操作", "实质价值", "增量贡献", "自然"]
OBJ_MARK = ["约为", "±", "等于", "应为", "必须等于", "加总", "行", "文件",
            "不得", "缺失", "至少覆盖", "逐条", "档", "mm", "%", "$"]

print("=" * 112)
print("判据可核验性分类")
print("=" * 112)
print(f"{'ID':<6}{'w':>5}{'锚点数':>6} {'主观词':>6}  {'类型':<10} description 摘要")
print("-" * 112)

groups = {"客观强": [], "客观中": [], "主观": []}
for c in crit:
    cid, w = c["id"], c.get("weight")
    desc = c.get("description", "")
    body = desc.split("Deliverables to inspect")[0]
    nums = NUM_RE.findall(body)
    nums = [n for n in nums if len(n.replace(",", "").replace(".", "").replace("-", "")) >= 1]
    n_num = len(nums)
    n_subj = sum(1 for k in SUBJ if k in body)
    n_obj = sum(1 for k in OBJ_MARK if k in body)

    if n_num >= 3 and n_subj <= 1:
        kind = "客观强"
    elif n_subj >= 3 and n_num <= 1:
        kind = "主观"
    else:
        kind = "客观中"
    groups[kind].append(cid)
    brief = re.sub(r"\s+", " ", body)[:96]
    print(f"{cid:<6}{str(w):>5}{n_num:>6} {n_subj:>6}  {kind:<10} {brief}")

print()
print("=" * 112)
for k, v in groups.items():
    print(f"  {k}: {len(v)} 条 -> {v}")
print("=" * 112)

print()
print("【主观判据详情】判官易满分，是压分重点改写对象：")
for c in crit:
    if c["id"] in groups["主观"]:
        body = c.get("description", "").split("Deliverables to inspect")[0]
        print(f"  {c['id']} (w={c.get('weight')}):")
        print(f"     {re.sub(r'\\s+', ' ', body)[:520]}")
        print()
