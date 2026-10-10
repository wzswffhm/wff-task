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
nos = []
for rid, row in zip(dd["record_id_list"], dd["data"]):
    def g(f):
        v = row[idx[f]] if f in idx else None
        if isinstance(v, list):
            return ",".join((x.get("name") or x.get("text") or "") if isinstance(x, dict) else str(x) for x in v)
        return v
    nos.append(str(g("序号")))
print("飞书序号全集:", ", ".join(sorted(nos, key=lambda x: int(x) if x.isdigit() else 9999)))
print("\n是否存在序号 148 :", "148" in nos)
for rid, row in zip(dd["record_id_list"], dd["data"]):
    def g(f):
        v = row[idx[f]] if f in idx else None
        if isinstance(v, list):
            return ",".join((x.get("name") or x.get("text") or "") if isinstance(x, dict) else str(x) for x in v)
        return v
    if str(g("序号")) in ("148", "150", "151", "152") and str(g("序号")) != "152":
        pass
    if str(g("序号")) == "148":
        print(f'  148: 标注人={g("标注人")} 状态={g("状态")} 题目附件={g("题目附件信息")}')
