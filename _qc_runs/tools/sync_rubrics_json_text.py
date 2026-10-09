# -*- coding: utf-8 -*-
"""把 tests/rubrics.toml 的 R29/R30 锚点同步到设计态 rubrics.json（精确文本替换，不重排文件）。

同步两处：
  1. description（与 toml 逐字一致）
  2. levels（gradient 锚点的结构化表达，与 toml 锚点语义一致）

只替换目标 JSON 字符串，其余字节（缩进/行尾/键序）保持不变。
"""
import json
import pathlib
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

W = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-weakness\FIN3-WKN-150")
TOML = W / "tests" / "rubrics.toml"
TARGET = W / "rubrics.json"
DRY = "--dry-run" in sys.argv

# R29/R30 新 levels（键: 1=满分5档 ... 0=1档），语义与 toml 锚点逐档对应
NEW_LEVELS = {
    "R29": {
        "1": "两法结构完整、交叉验证与差异归因均清晰，且对两法估值差异给出量化拆解——把差异分解为流动性折价贡献与标的自身现金流/成长性预测贡献两部分并给出具体数值（须能由 10% 折价率与 DCF/市场法中间值复核）",
        "0.75": "两法结构完整、归因清晰但差异仅定性说明、未量化拆解",
        "0.5": "仅一种方法完整或未做交叉验证",
        "0.25": "两种方法均不完整",
        "0": "未给出可复核的估值路径",
    },
    "R30": {
        "1": "四项判断齐备，且每项均给出至少 2 个独立数据点交叉支撑（至少含 1 个跨期变化的量化幅度，如毛利率 2023→2026H1 累计变动 pp、应收周转天数区间跨度、净现比逐年序列）并附文件/图表引用",
        "0.75": "四项齐备且均有数据支撑，但有 1 项仅罗列单期数值、未给跨期量化幅度或缺引用",
        "0.5": "覆盖三项或有一项仅结论无依据",
        "0.25": "仅覆盖两项或大量结论无依据",
        "0": "几乎未做趋势判断",
    },
}


def toml_desc():
    txt = TOML.read_text(encoding="utf-8")
    out = {}
    for b in re.split(r"\[\[criterion\]\]", txt)[1:]:
        mid = re.search(r'^\s*id\s*=\s*"([^"]+)"', b, re.M)
        md = re.search(r'^\s*description\s*=\s*"((?:[^"\\]|\\.)*)"', b, re.M | re.S)
        if mid and md:
            out[mid.group(1)] = md.group(1).replace('\\"', '"').replace("\\\\", "\\")
    return out


def jstr(s):
    """JSON 字符串字面量（不含外层键名）。"""
    return json.dumps(s, ensure_ascii=False)


def process(text, tdesc):
    """在 text 中定位 R29/R30 块并替换 description + levels，返回 (新文本, 报告)。"""
    report = []
    # 定位每个 id 的块：从 '"id": "Rxx"' 到下一个 '"id": "' 或文件尾
    ids = ["R29", "R30"]
    pos = {}
    for cid in ids:
        m = re.search(r'"id"\s*:\s*"%s"' % cid, text)
        if not m:
            raise SystemExit(f"json 中未找到 {cid}")
        pos[cid] = m.start()
    # 块结束 = 下一个 id 出现处（R31 在 R30 后）
    m31 = re.search(r'"id"\s*:\s*"R31"', text)
    bounds = {"R29": (pos["R29"], pos["R30"]), "R30": (pos["R30"], m31.start())}

    # 从后往前替换，避免位置偏移
    for cid in ["R30", "R29"]:
        a, b = bounds[cid]
        block = text[a:b]
        orig = block

        # 1) description
        dm = re.search(r'"description"\s*:\s*("(?:[^"\\]|\\.)*")', block)
        if not dm:
            raise SystemExit(f"{cid} 块内无 description")
        old_d = dm.group(1)
        new_d = jstr(tdesc[cid])
        block = block[:dm.start(1)] + new_d + block[dm.end(1):]

        # 2) levels（gradient）—— 整体替换含括号，重建换行/缩进
        lm = re.search(r'"levels"\s*:\s*\{(.*?)\}', block, re.S)
        if lm:
            body = lm.group(1)
            nl = NEW_LEVELS[cid]
            keys_in_file = re.findall(r'"((?:0|1|0\.25|0\.5|0\.75))"\s*:', body)
            # 键缩进 = 原 body 第一个键的缩进；闭括号缩进 = 原 body 末尾空白
            fm = re.search(r'[ \t]*"', body)
            ind_key = fm.group(0)[:-1] if fm else "       "
            cm = re.search(r"(\s*)$", body)
            ind_close = cm.group(1) if cm else "\n      "
            lines = []
            for k in keys_in_file:
                lines.append(f'{ind_key}"{k}": {jstr(nl[k])}')
            new_body = "\n" + ",\n".join(lines) + ind_close
            block = block[:lm.start(1)] + new_body + block[lm.end(1):]

        changed = block != orig
        report.append((cid, changed, len(old_d), len(new_d)))
        text = text[:a] + block + text[b:]
    return text, report


def main():
    tdesc = toml_desc()
    text = TARGET.read_text(encoding="utf-8")
    new_text, report = process(text, tdesc)
    for cid, ch, lo, ln in report:
        print(f"  {cid}: changed={ch}  desc {lo} -> {ln}")
    if DRY:
        print("[dry-run] 不写入")
        return
    TARGET.write_text(new_text, encoding="utf-8", newline="")  # 保留原文本内的 \n
    print(f"  已写入 {TARGET}")

    # 复检
    j = json.loads(TARGET.read_text(encoding="utf-8"))
    for cid in ("R29", "R30"):
        for it in j["items"]:
            if it["id"] == cid:
                ok_d = it["description"] == tdesc[cid]
                ok_l = it.get("levels") == NEW_LEVELS[cid]
                print(f"  复检 {cid}: description一致={ok_d}  levels一致={ok_l}")
    # 结构复检
    print(f"  items 数={len(j['items'])}  顶层键={list(j.keys())}")


if __name__ == "__main__":
    main()
