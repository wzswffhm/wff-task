# -*- coding: utf-8 -*-
"""FIN3-WKN-153：把「考点信息（rubrics）」与「参考答案」写入已建行。

用途：① 补齐交付字段；② 顺带验证字段级写权限（题目/类型/难度/标注人已可写，
附件字段报 800020812，需判断是"仅附件字段受限"还是更广的权限问题）。

用法: python feishu_153_fill.py <record_id>
"""
import json
import os
import pathlib
import re
import subprocess
import sys
import tomllib

sys.stdout.reconfigure(encoding="utf-8")

LARK = r"C:\nvm4w\nodejs\node_modules\@larksuite\cli\bin\lark-cli.exe"
BASE = "QpzNb4fXSamfX6sLloBcPfHNnug"
TABLE = "tblPNrBtjFfwOowN"
F_REF = "fld2LBu2Ns"      # 参考答案
F_POINTS = "fldqj9Zstn"   # 考点信息（rubrics）

H = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-weakness")
TASK = H / "work_fin-b01_20261012-153" / "FIN3-WKN-153"

ANSWER = (
    "有效持仓口径：持仓原始记录 295 行，剔除重复上报 4 行、数据所属日期非估值日 6 行、"
    "证券主数据状态非 active 5 行，得有效记录 280 行；三类剔除对应市值影响分别为 "
    "11,554,917.40 元、25,774,234.50 元、25,142,250.00 元（须分列不得合并）。"
    "持仓与行情按 sec_code ↔ instrument_id 关联（对账指引指定的 wind_code 两侧均无该列，属死路），"
    "行情取估值日当日记录 126 行，剔除旧价记录 5 行；行情主件 valuation/price_feed_20260930.csv 为 0 字节，"
    "据 internal/ops_email_20261008.txt 改用 data/price_feed_20260930_repush.csv（重推件）。"
    "市值与净值：有效持仓市值 1,295,353,746.36 元，加现金及清算备付金 45,645,475.03 元、"
    "应收 4,278,200.00 元，减应付 2,763,450.00 元，得资产净值 1,342,513,971.39 元，"
    "除以总份额 1,250,000,000.00 份得单位净值 1.0740，与托管行报告差额 0.00bp；"
    "银行对账单各账户期末余额分列后与托管报告现金勾稽。"
    "投资监督（按现行有效条款、以计划资产净值为分母）：R-01 单一证券集中度 12.01%（按证券编码跨账户合并，超限）、"
    "R-02 单一发行人集中度 12.01%、R-03 非标资产比例 4.50%、R-05 现金类资产比例 3.40%、"
    "R-07 权益型基金比例 7.63%，除 R-01 外均合规；R-01 须在报告监督章节正文披露代码、名称、市值、占比、"
    "成因、整改动作与时限，并与 rules/liquidity_policy.md 交叉核对条文口径。"
    "材料清点：/app/input_files/ 共 25 个文件、7 个来源目录（compliance 3、data 3、internal 4、portfolio 2、"
    "reports 3、rules 4、valuation 4）＋根目录散件 2（00_README.md、manifest.csv）。"
    "条款版本：rules/ 下历史版限额不适用于本期，上期报告依已被替代条款或旧汇总口径形成的表述须逐条重述（≥3 条）。"
    "交付物 6 项：季度复核工作簿（八表）、季度投资运作报告（八章节、正文中文 ≤1,600 字）、"
    "可复算 reproduce.py（不得硬编码结论）、持仓覆盖表 CSV、数据问题台账 CSV（七要素）、复合图 PNG。"
)


def build_points() -> str:
    spec = tomllib.loads((TASK / "tests" / "rubrics.toml").read_text(encoding="utf-8"))["criterion"]
    lines = []
    for c in spec:
        body = re.sub(r"\s+", " ", c["description"].split("Deliverables to inspect:")[0]).strip()
        w = float(c["weight"])
        tag = "（负向扣分项）" if c.get("negate") else ""
        lines.append(f"{c['id']}｜{w:g}分{tag}｜{body}")
    return "\n".join(lines)


def main():
    if len(sys.argv) < 2:
        print("用法: python feishu_153_fill.py <record_id>")
        return 2
    rid = sys.argv[1]
    points = build_points()
    print(f"考点信息 {len(points)} 字 / 34 条；参考答案 {len(ANSWER)} 字")
    payload = {F_POINTS: points, F_REF: ANSWER}
    env = {**os.environ, "LARK_CLI_NO_PROXY": "1"}
    r = subprocess.run(
        [LARK, "base", "+record-upsert", "--base-token", BASE, "--table-id", TABLE,
         "--record-id", rid, "--json", json.dumps(payload, ensure_ascii=False),
         "--as", "user", "--format", "json"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
    print("rc =", r.returncode)
    print((r.stdout or "")[-1200:])
    if r.stderr.strip():
        print("[stderr]", r.stderr[-600:])
    return 0 if '"ok": true' in (r.stdout or "") else 1


if __name__ == "__main__":
    raise SystemExit(main())
