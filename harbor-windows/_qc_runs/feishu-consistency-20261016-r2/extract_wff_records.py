"""从飞书全表快照中提取标注员 = wff 的记录（只读，不改飞书）。"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "feishu-records.ndjson")

F_ANN = "标注员"
F_ZIP = "作业压缩包"
F_TEXT = "文本"
F_STATUS = "状态"
F_REASON = "返修原因"
F_ZQ = "甲方ID"


def main():
    rows = [json.loads(l) for l in open(SRC, encoding="utf-8")]
    print("total records:", len(rows))
    wff = []
    for r in rows:
        names = [a.get("name") for a in (r.get(F_ANN) or [])]
        if "wff" in names:
            wff.append(r)
    print("wff records:", len(wff))

    out = []
    for r in wff:
        att = r.get(F_ZIP) or []
        out.append({
            "record_id": r["record_id"],
            "text": r.get(F_TEXT),
            "status": r.get(F_STATUS),
            "zq": r.get(F_ZQ),
            "qwen": r.get("Qwen分数"),
            "opus": r.get("opus分数"),
            "glm": r.get("glm分数"),
            "kimi": r.get("Kimi分数"),
            "attachments": [{"name": a["name"], "token": a["file_token"], "size": a["size"]} for a in att],
            "reason_head": (r.get(F_REASON) or "")[:300],
        })
    with open(os.path.join(HERE, "feishu-wff-records.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)
    for o in out:
        print(json.dumps(o, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
