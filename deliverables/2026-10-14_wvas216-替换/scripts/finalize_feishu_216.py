# -*- coding: utf-8 -*-
"""最终写回：用 drive +upload 上传 54MB ZIP 拿 file_token，再一次 PUT 写入三个附件字段。

为什么绕开 lark-cli 的 typed 附件命令：
  +record-upload-attachment / +record-remove-attachment 在 1.0.85 与 1.0.98 上都返回
  "HTTP 404: 404 page not found"。--dry-run 显示其编排走 /open-apis/base/v3/...，
  而 base/v3 在本环境整体 404（单独 GET 字段也 404）；bitable/v1 与 drive/v1 均正常。
  另外 medias/upload_all 对 54MB ZIP 返回 1061002 params error（超过 20MB 上限），
  medias/upload_part 也报 1061002，故改用 drive +upload（其对 >20MB 自动分片）。
"""
import json
import pathlib
import subprocess
import sys

DELIV = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\deliverables\2026-10-14_wvas216-替换")
BASE = "EsJebL8JJaf7g4sIbItcnMFgnvg"
TABLE = "tblRDxcGkblflMBA"
REC = "reczz28KQU8reW2k"

# 两张 PNG 已在本轮成功上传，直接复用 token。
PNG = {
    "oracle/nop截图": "NbzNbjz7ro7Fq2xT9CEcqPRPn1E",
    "分数截图": "Ug0abGLdVopTNAxYuu5cCJRqn5g",
}


def run(args, cwd):
    """调用 lark-cli；返回解析后的 JSON。

    lark-cli 在 PATH 上只暴露 .ps1 / .cmd 包装器，Windows 下它们不是可执行映像，
    subprocess 直接 spawn 会 FileNotFoundError，必须经 shell 解析。这里所有命令行
    参数都是 ASCII（中文只在 @json 文件里），所以不存在代码页损坏中文的问题。
    """
    proc = subprocess.run(args, cwd=str(cwd), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", shell=True)
    raw = (proc.stdout or "") + (proc.stderr or "")
    i, j = raw.find("{"), raw.rfind("}")
    if i < 0 or j <= i:
        raise SystemExit("lark-cli 未返回 JSON:\n" + raw[:2000])
    doc = json.loads(raw[i:j + 1])
    if doc.get("ok") is False:
        raise SystemExit("lark-cli 报错: " + json.dumps(doc.get("error"), ensure_ascii=False))
    return doc


def lark():
    """返回可直接 exec 的 lark-cli 入口（.cmd 包装器需要 shell 解析）。"""
    for cand in (r"C:\nvm4w\nodejs\lark-cli.cmd",):
        if pathlib.Path(cand).exists():
            return cand
    raise SystemExit("找不到 lark-cli.cmd")


CLI = lark()
zip_path = DELIV / "package" / "wfflab__wvas-216-v1.0.0-delivery.zip"
print("ZIP", zip_path.name, zip_path.stat().st_size, "bytes")

# 1) drive +upload（>20MB 自动分片）
print("[1] drive +upload ...")
doc = run([CLI, "drive", "+upload", "--as", "user",
           "--file", "./" + zip_path.name, "--format", "json"], cwd=zip_path.parent)
token = doc["data"].get("file_token") or doc["data"].get("token")
print("    file_token =", token)

# 2) 一次 PUT 写入三个附件字段（整体赋值 => 格内只有新件）
cells = {
    "oracle/nop截图": [{"file_token": PNG["oracle/nop截图"], "image_width": 1600, "image_height": 900}],
    "分数截图": [{"file_token": PNG["分数截图"], "image_width": 1600, "image_height": 900}],
    "作业压缩包": [{"file_token": token}],
}
body = DELIV / "scripts" / ".record.json"
body.write_text(json.dumps({"fields": cells}, ensure_ascii=False), encoding="utf-8")
print("[2] PUT bitable record ...")
try:
    res = run([CLI, "api", "PUT",
               "/open-apis/bitable/v1/apps/%s/tables/%s/records/%s" % (BASE, TABLE, REC),
               "--as", "user", "--data", "@.record.json", "--format", "json"],
              cwd=DELIV / "scripts")
    print("    code =", res.get("code"))
finally:
    body.unlink(missing_ok=True)

# 3) 回读验证
print("[3] 回读验证 ...")
g = run([CLI, "base", "+record-get", "--as", "user", "--base-token", BASE,
         "--table-id", TABLE, "--record-id", REC, "--format", "json"], cwd=DELIV / "scripts")
fields = list(g["data"]["fields"])
rows = g["data"]["data"]
row = rows[0] if rows else []
idx = {name: (row[i] if i < len(row) else None) for i, name in enumerate(fields)}

expect = {
    "oracle/nop截图": (DELIV / "evidence/images/oracle_nop_controls.png", 84635),
    "分数截图": (DELIV / "evidence/images/score_summary.png", 55651),
    "作业压缩包": (zip_path, 54455198),
}
ok = True
for name, (path, size) in expect.items():
    cell = [c for c in (idx.get(name) or []) if c]
    exact = [c for c in cell if c.get("name") == path.name and int(c.get("size", -1)) == size]
    state = "匹配且唯一" if (len(exact) == 1 and len(cell) == 1) else "**异常**"
    print("    %-14s %s（格内 %d 件: %s）" % (
        name, state, len(cell), ", ".join("%s(%s)" % (c.get("name"), c.get("size")) for c in cell)))
    if state != "匹配且唯一":
        ok = False

for k in ("题目方向", "文本", "Qwen分数", "opus分数", "状态"):
    v = idx.get(k)
    s = json.dumps(v, ensure_ascii=False)
    print("    %-10s = %s" % (k, s[:110]))

print("结论：", "三个附件均已上传且格内唯一" if ok else "**存在不一致**")
sys.exit(0 if ok else 1)
