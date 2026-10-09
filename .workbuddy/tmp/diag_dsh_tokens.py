# -*- coding: utf-8 -*-
"""诊断「火山方舟 deepseek-v4-1-flash 报输出 token 上限」的根因。

取证两处硬证据：
  1) DSH 应用包（app.asar）里 maxTokens 的默认值/回落逻辑
  2) 最近的会话缓存中该次请求实际使用的模型与预算字段
"""
import glob
import os
import re

print("=" * 78)
print("1) DSH 应用包中的 maxTokens 片段")
print("=" * 78)
ASAR = r"D:\DSH\resources\app.asar"
try:
    data = open(ASAR, "rb").read()
    print(f"asar 大小: {len(data):,} B")
    for pat in (rb"maxTokens", rb"max_output_tokens", rb"defaultMaxTokens"):
        hits = [m.start() for m in re.finditer(pat, data)]
        print(f"\n[{pat.decode()}] 出现 {len(hits)} 次")
        for i in hits[:5]:
            seg = data[max(0, i - 300):i + 200].decode("utf-8", "replace")
            seg = re.sub(r"\s+", " ", seg)
            print(f"   ... {seg[:430]}")
except Exception as e:  # noqa: BLE001
    print("读取 asar 失败:", e)

print()
print("=" * 78)
print("2) 最近会话缓存中的模型与预算字段")
print("=" * 78)
d = os.path.expanduser(r"~\.dsh\storages\session_projcache\sessions")
files = sorted(glob.glob(os.path.join(d, "*.json")), key=os.path.getmtime, reverse=True)[:4]
for f in files:
    raw = open(f, encoding="utf-8", errors="replace").read()
    print(f"\n--- {os.path.basename(f)}  ({len(raw):,} chars)")
    for kw in ("deepseek-v4", "maxTokens", "max_tokens", "finishReason",
               "finish_reason", "ark", "reasoningEffort"):
        i = raw.find(kw)
        print(f"      {kw:16} {'@' + str(i) if i >= 0 else '未出现'}")
    i = raw.find("maxTokens")
    if i >= 0:
        print("      maxTokens 片段:", re.sub(r"\s+", " ", raw[max(0, i - 200):i + 200]))
