import json, os, subprocess, sys
sys.stdout.reconfigure(encoding="utf-8")
LARK = r"C:\nvm4w\nodejs\lark-cli.cmd"
BT, TB, REC = "QpzNb4fXSamfX6sLloBcPfHNnug", "tblPNrBtjFfwOowN", "reczz28Jf9pZeD1T"
env = dict(os.environ); env["LARK_CLI_NO_PROXY"] = "1"
p = subprocess.run([LARK, "base", "+record-list", "--base-token", BT, "--table-id", TB,
                    "--page-size", "100", "--as", "user", "--format", "json"],
                   capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
dd = json.loads(p.stdout)["data"]
row = dd["data"][dd["record_id_list"].index(REC)]
print("=== 序号 239 记录的全部附件字段 ===")
for name, val in zip(dd["fields"], row):
    if isinstance(val, list) and val and isinstance(val[0], dict) and "file_token" in val[0]:
        print(f"  [{name}]")
        for a in val:
            print(f"     - {a.get('name')}  size={a.get('size')}  token={a.get('file_token')}")
    elif name in ("状态", "题目难度", "返修类型", "序号"):
        print(f"  [{name}] = {val!r}")
