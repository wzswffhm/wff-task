"""解析 lark-cli 输出的飞书记录（自动探测编码）。"""
import io
import json
import pathlib
import sys

sys.stdout.reconfigure(encoding="utf-8")

p = pathlib.Path(sys.argv[1])
raw = p.read_bytes()
for enc in ("utf-16", "utf-8-sig", "utf-8"):
    try:
        text = raw.decode(enc)
        break
    except UnicodeDecodeError:
        continue
else:
    raise SystemExit("无法解码")

d = json.loads(text)
print("ok =", d.get("ok"))
if not d.get("ok"):
    print(json.dumps(d.get("error"), ensure_ascii=False, indent=2)[:600])
    raise SystemExit(0)

data = d.get("data") or {}
items = data.get("items") or data.get("records") or []
print(f"记录数 = {len(items)}\n")

FIELDS = ["文本", "状态", "标注员", "题目方向", "返修原因", "作业压缩包", "领取日期",
          "zhang质检", "xie质检", "分数截图", "oracle/nop截图", "提示词", "父记录"]


def fmt(v):
    if v is None:
        return "<空>"
    if isinstance(v, list):
        out = []
        for x in v:
            if isinstance(x, dict):
                out.append(x.get("name") or x.get("text") or x.get("file_token") or str(x))
            else:
                out.append(str(x))
        return " | ".join(out)
    if isinstance(v, dict):
        return v.get("name") or v.get("text") or json.dumps(v, ensure_ascii=False)
    return str(v)


for it in items:
    f = it.get("fields") or {}
    print("=" * 80)
    print("record_id =", it.get("record_id"))
    for k in FIELDS:
        if k in f:
            s = fmt(f[k])
            if len(s) > 260:
                s = s[:260] + f"…（共{len(s)}字）"
            print(f"  {k}: {s}")
    extra = [k for k in f if k not in FIELDS]
    if extra:
        print("  [其他字段]", extra)
