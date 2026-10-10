import json, os, subprocess, sys
sys.stdout.reconfigure(encoding="utf-8")
LARK = r"C:\nvm4w\nodejs\lark-cli.cmd"
BT, TB = "QpzNb4fXSamfX6sLloBcPfHNnug", "tblPNrBtjFfwOowN"
env = dict(os.environ); env["LARK_CLI_NO_PROXY"] = "1"
p = subprocess.run([LARK, "base", "+record-list", "--base-token", BT, "--table-id", TB,
                    "--page-size", "200", "--as", "user", "--format", "json"],
                   capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
dd = json.loads(p.stdout)["data"]
print(f"总记录数: {len(dd['record_id_list'])}")
print("字段列表:")
for i, n in enumerate(dd["fields"]):
    print(f"  [{i}] {n}")
