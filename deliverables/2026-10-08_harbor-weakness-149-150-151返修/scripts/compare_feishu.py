"""Compare the Feishu row content for FIN3-WKN-149/150/151 against the package files."""
import json
import pathlib
import re
import sys

ev = pathlib.Path(sys.argv[1])
raw = (ev / "feishu-wff-rows.json").read_bytes()
for enc in ("utf-8-sig", "utf-16", "utf-8"):
    try:
        text = raw.decode(enc)
        break
    except UnicodeDecodeError:
        continue

d = json.loads(text)
data = d["data"]
cols = data.get("fields") or data.get("field_id_list")
recids = data.get("record_id_list") or []
print("columns:", cols)
print("record ids:", recids)
print("rev:", data.get("rev"))

repo = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task")
summary = []
for i, row in enumerate(data["data"]):
    f = dict(zip(cols, row))
    rid = recids[i] if i < len(recids) else "?"
    title = f.get("题目") or ""
    kp = f.get("考点信息（rubrics）") or ""
    ans = f.get("参考答案") or ""

    def names(key):
        v = f.get(key)
        if isinstance(v, list):
            return [x.get("name") if isinstance(x, dict) else x for x in v]
        return v

    m = re.search(r"FIN3-WKN-(\d+)", str(names("题目附件信息")))
    tid = f"FIN3-WKN-{m.group(1)}" if m else "?"
    task = repo / "harbor-weakness" / tid
    instr = (task / "instruction.md").read_text(encoding="utf-8") if task.exists() else ""

    print("=" * 95)
    print(f"{tid}  record={rid}  序号={f.get('序号')}  类型={f.get('类型')}  状态={f.get('状态')}  "
          f"难度={f.get('题目难度')}  原工作表={f.get('原工作表')}")
    print(f"  长度: 题目={len(title)}  考点={len(kp)}  参考答案={len(ans)}  包内instruction={len(instr)}")
    print(f"  交付物   : {names('交付物')}")
    print(f"  质检报告 : {names('质检报告')}")
    print(f"  标准答案 : {names('标准答案附件信息')}")
    print(f"  题目附件 : {names('题目附件信息')}")

    for label, txt in (("题目", title), ("考点", kp), ("参考答案", ans)):
        (ev / f"{tid}-feishu-{label}.txt").write_text(txt, encoding="utf-8")
    summary.append((tid, rid, f.get("序号"), len(title), len(kp), len(ans)))

print("\n--- summary ---")
for s in summary:
    print(s)
