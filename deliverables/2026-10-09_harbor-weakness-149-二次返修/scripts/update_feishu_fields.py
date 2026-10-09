# -*- coding: utf-8 -*-
"""同步飞书文本/选择字段与包内最终口径：
  ① 考点信息（rubrics）考点7 改为「累计负 + 取消 20 个下限」口径，与包内 R17 一致
  ② 题目难度 A2 -> A1（均分 0.681373 落 [0.60,0.70)）
用法: python update_feishu_fields.py [--apply]
"""
import json
import os
import pathlib
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding='utf-8')
LARK = r"C:\nvm4w\nodejs\lark-cli.cmd"
BT, TB, REC = "QpzNb4fXSamfX6sLloBcPfHNnug", "tblPNrBtjFfwOowN", "rec28himvkSA77"
F_QD, F_DIFF = "fldqj9Zstn", "fldYA4iRaD"
APPLY = "--apply" in sys.argv
env = dict(os.environ)
env["LARK_CLI_NO_PROXY"] = "1"

NEW_R7 = (
    "考点7：回答严格按 rules_windows.csv 构造历史窗口——窗口起点为合格月份的**次月第一个上交所交易日**"
    "（每个合格月份产生 1 个候选窗口），长度 10 个上交所交易日；合格判定以**窗口整体累计收益为负**为准"
    "（窗口内 10 个交易日按方案权重每日再平衡计算的组合累计收益，不要求窗口内逐日收益均为负），"
    "合格窗口按累计跌幅从大到小排序后**全部用于校准，规则不设保留数量下限**；"
    "给出四个情景的候选窗口数与合格窗口数分别为 23/6、5/3、26/8、5/1，并**如实报告实际数量**"
    "（不得静默回退到未筛选的候选窗口，也不得伪报数量；某情景无合格窗口时须如实报告该情景无历史校准窗口、"
    "其校准冲击按 0 计）；给出合格窗口的起止日（S1 最深 2024-08-01 至 2024-08-14、累计 −2.65%；"
    "S2 2023-10-09 至 2023-10-20；S3 2023-10-09 至 2023-10-20；S4 2021-07-01 至 2021-07-14）"
    "与窗口内最深累计跌幅；校准冲击取合格窗口内各风险因子 10 个交易日累计变动的中位数"
    "（S1 沪深300 −1.20%、中证500 −1.04%、创业板 −3.35%、国债 −0.15%、标普500 −0.83%、"
    "USD/CNH +0.25% 等）。窗口起点使用错误、出现静默回退或校准冲击未取中位数的不满足。"
)


def lark(*args):
    p = subprocess.run([LARK] + list(args), capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=env)
    return p.returncode, (p.stdout or ""), (p.stderr or "")


rc, out, err = lark("base", "+record-list", "--base-token", BT, "--table-id", TB,
                    "--page-size", "100", "--as", "user", "--format", "json")
dd = json.loads(out)["data"]
idx = {n: i for i, n in enumerate(dd["fields"])}
row = dd["data"][dd["record_id_list"].index(REC)]
cur_qd = row[idx["考点信息（rubrics）"]]
cur_diff = row[idx["题目难度"]]

lines = cur_qd.split('\n')
n7 = [i for i, l in enumerate(lines) if l.startswith('考点7：')]
print(f'考点信息 行数={len(lines)}  考点7 命中行={n7}')
print(f'  旧考点7 含「20 个下限」={"20 个下限" in cur_qd}')
print(f'  当前题目难度 = {cur_diff}')

new_lines = list(lines)
for i in n7:
    new_lines[i] = NEW_R7
new_qd = '\n'.join(new_lines)

print(f'\n新考点7 字数={len(NEW_R7)}  新考点信息总字数={len(new_qd)}')
print(f'  新文本含「20 个下限」={"20 个下限" in new_qd}  含「不设保留数量下限」={"不设保留数量下限" in new_qd}')
print(f'  新文本含「累计收益为负」={"累计收益为负" in new_qd}')

if not APPLY:
    print('\n（DRY-RUN；加 --apply 执行写入）')
    sys.exit(0)

payload = {"update_records": {REC: {"考点信息（rubrics）": new_qd, "题目难度": ["A1"]}}}
rc, out, err = lark("base", "+record-batch-update", "--base-token", BT, "--table-id", TB,
                    "--json", json.dumps(payload, ensure_ascii=False),
                    "--as", "user", "--format", "json")
print(f'\n[写入] rc={rc}  {(out or err)[:200]}')

rc, out, err = lark("base", "+record-list", "--base-token", BT, "--table-id", TB,
                    "--page-size", "100", "--as", "user", "--format", "json")
dd = json.loads(out)["data"]
idx = {n: i for i, n in enumerate(dd["fields"])}
row = dd["data"][dd["record_id_list"].index(REC)]
v_qd, v_diff = row[idx["考点信息（rubrics）"]], row[idx["题目难度"]]
print('\n=== 复核 ===')
print(f'  题目难度 = {v_diff}  {"✅" if v_diff == "A1" else "⚠"}')
print(f'  考点信息含「20 个下限」={"20 个下限" in v_qd}  '
      f'含「不设保留数量下限」={"不设保留数量下限" in v_qd}  '
      f'含「累计收益为负」={"累计收益为负" in v_qd}')
print(f'  考点信息字数={len(v_qd)}')
