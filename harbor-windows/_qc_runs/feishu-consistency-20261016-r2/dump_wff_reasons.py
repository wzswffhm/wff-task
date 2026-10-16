"""导出飞书 wff 五条记录的完整字段（尤其返修原因），供人工核对。"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "feishu-records.ndjson")
OUT = os.path.join(HERE, "feishu-wff-reasons.md")

F_ANN = "标注员"


def main():
    rows = [json.loads(l) for l in open(SRC, encoding="utf-8")]
    wff = [r for r in rows if "wff" in [a.get("name") for a in (r.get(F_ANN) or [])]]
    lines = ["# 飞书 wff 名下记录完整返修原因（快照时间见 manifest）", ""]
    for r in wff:
        att = r.get("作业压缩包") or []
        lines.append("## %s" % (att[0]["name"] if att else r["record_id"]))
        lines.append("")
        lines.append("- record_id: `%s`" % r["record_id"])
        lines.append("- 状态: %s" % (r.get("状态") or []))
        lines.append("- 甲方ID: %s" % r.get("甲方ID"))
        lines.append("- Qwen/Opus: %s / %s" % (r.get("Qwen分数"), r.get("opus分数")))
        if att:
            lines.append("- 附件: `%s` (%s B, token=%s)" % (att[0]["name"], att[0]["size"], att[0]["file_token"]))
        lines.append("")
        lines.append("### 返修原因全文")
        lines.append("")
        lines.append("```text")
        lines.append((r.get("返修原因") or "").strip())
        lines.append("```")
        lines.append("")
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    print("written:", OUT, os.path.getsize(OUT), "bytes")


if __name__ == "__main__":
    main()
