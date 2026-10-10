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
for rid, row in zip(dd["record_id_list"], dd["data"]):
    def g(f):
        v = row[idx[f]] if f in idx else None
        if isinstance(v, list):
            return ",".join((x.get("name") or x.get("text") or "") if isinstance(x, dict) else str(x) for x in v)
        return v
    if str(g("序号")) in ("282", "267", "239", "149"):
        print(f'--- 序号 {g("序号")}  标注人={g("标注人")}  状态={g("状态")} ---')
        print(f'    题目附件信息: {g("题目附件信息") or "(空)"}')
        print(f'    标准答案附件: {g("标准答案附件信息") or "(空)"}')
        print(f'    交付物:       {g("交付物") or "(空)"}')
        print(f'    原工作表:     {g("原工作表")}')
