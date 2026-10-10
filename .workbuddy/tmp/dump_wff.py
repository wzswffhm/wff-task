import json, os, subprocess, sys
sys.stdout.reconfigure(encoding="utf-8")
LARK = r"C:\nvm4w\nodejs\lark-cli.cmd"
BT, TB = "QpzNb4fXSamfX6sLloBcPfHNnug", "tblPNrBtjFfwOowN"
env = dict(os.environ); env["LARK_CLI_NO_PROXY"] = "1"
p = subprocess.run([LARK, "base", "+record-list", "--base-token", BT, "--table-id", TB,
                    "--page-size", "200", "--as", "user", "--format", "json"],
                   capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
dd = json.loads(p.stdout)["data"]
idx = {n: i for i, n in enumerate(dd["fields"])}
recs = []
for rid, row in zip(dd["record_id_list"], dd["data"]):
    def g(f):
        v = row[idx[f]] if f in idx else None
        if isinstance(v, list):
            out = []
            for x in v:
                if isinstance(x, dict):
                    out.append(x.get("text") or x.get("name") or x.get("en_name") or str(x))
                else:
                    out.append(str(x))
            return ",".join(out)
        return v
    recs.append((rid, g("序号"), g("题目"), g("标注人"), g("状态")))
from collections import Counter
print("标注人分布:", dict(Counter(r[3] for r in recs)))
print()
print("=== 标注人含 wff 的记录 ===")
wff = [r for r in recs if r[3] and "wff" in str(r[3]).lower()]
for rid, no, t, who, st in wff:
    print(f"  序号={no:<6} 题目={t}  标注人={who}  状态={st}  rec={rid}")
print(f"\n小计: {len(wff)} 条")
