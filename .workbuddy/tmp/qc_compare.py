"""提取甲方 QC 历史报告的结论，对比 215 与 217。"""
import json
import pathlib

Q = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\_qc_runs")


def brief(obj, depth=0, max_depth=3):
    """把 report.json 压成可读摘要。"""
    pad = "  " * (depth + 1)
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, (dict, list)) and depth < max_depth:
                n = len(v)
                print(f"{pad}{k}: ({'dict' if isinstance(v, dict) else f'list[{n}]'})")
                brief(v, depth + 1, max_depth)
            else:
                s = str(v)
                if len(s) > 160:
                    s = s[:160] + "…"
                print(f"{pad}{k}: {s}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj[:8]):
            if isinstance(v, (dict, list)) and depth < max_depth:
                print(f"{pad}[{i}]")
                brief(v, depth + 1, max_depth)
            else:
                s = str(v)
                if len(s) > 160:
                    s = s[:160] + "…"
                print(f"{pad}[{i}] {s}")
        if len(obj) > 8:
            print(f"{pad}... 共 {len(obj)} 项")


for name in ["qcorig-215", "qcorig-217", "qcpass-215", "qcpass-217", "qcpass2-217"]:
    p = Q / name / "report.json"
    if not p.is_file():
        continue
    d = json.loads(p.read_text(encoding="utf-8"))
    print("=" * 90)
    print(f"### {name}   顶层字段: {list(d.keys())}")
    # 优先打印结论类字段
    for key in ("status", "verdict", "passed", "summary", "conclusion", "overall",
                "result", "gate", "gates", "exit_code"):
        if key in d:
            print(f"  [结论] {key} = {json.dumps(d[key], ensure_ascii=False)[:400]}")
    print("  ---- 完整结构（前 3 层）----")
    brief(d, 0, 3)
    print()
