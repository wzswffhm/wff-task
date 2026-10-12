# -*- coding: utf-8 -*-
"""更新飞书考点信息中受 fix9 金标修正影响的数值（考点8/9/10/11/14）。
用法: python update_feishu_rubrics_fix9.py [--apply]
"""
import json
import os
import pathlib
import subprocess
import sys

sys.stdout.reconfigure(encoding='utf-8')
LARK = r"C:\nvm4w\nodejs\lark-cli.cmd"
BT, TB, REC = "QpzNb4fXSamfX6sLloBcPfHNnug", "tblPNrBtjFfwOowN", "rec28himvkSA77"
F_QD = "fldqj9Zstn"
APPLY = "--apply" in sys.argv
env = dict(os.environ)
env["LARK_CLI_NO_PROXY"] = "1"

# (旧文本片段, 新文本片段)
FIXES = [
    # 考点8：方案A 沿用/历史校准冲击损失
    ('给出方案A在沿用冲击下的损失 7.22%、5.44%、8.67%、9.90%（S1–S4），在历史校准冲击下为 0.72%、1.51%、1.43%、1.09%',
     '给出方案A在沿用冲击下的损失 7.02%、5.52%、8.59%、10.16%（S1–S4），在历史校准冲击下为 0.90%、1.45%、1.57%、0.11%'),
    # 考点9：推荐方案沿用/历史校准冲击损失
    ('指出推荐方案在四个情景下沿用冲击损失（−4.36%、−2.81%、−4.92%、−5.05%）均大于历史校准冲击（−0.43%、−0.58%、−0.75%、−0.24%）',
     '指出推荐方案在四个情景下沿用冲击损失（−3.96%、−2.97%、−4.77%、−5.56%）均大于历史校准冲击（−0.57%、−0.59%、−0.86%、+0.27%）'),
    # 考点10：各方案最大损失
    ('分别为方案A 9.902%、方案B 7.030%、方案C 6.650%、推荐方案 5.045%（当前持仓基准 8.916%）；方案A 有 2 个结果超过 8% 上限（外部冲击沿用 8.67%、信用收缩沿用 9.90%）',
     '分别为方案A 10.157%、方案B 7.456%、方案C 6.957%、推荐方案 5.565%（当前持仓基准 9.257%）；方案A 有 2 个结果超过 8% 上限（外部冲击沿用 8.59%、信用收缩沿用 10.16%）'),
    # 考点11：九项约束判定与超限幅度
    ('判定方案A未通过第 8、9 项（9.902% 超出 8.0% 上限 1.902 个百分点），方案B只未通过第 9 项（7.030% 超出 7.0% 缓冲线 0.030 个百分点）',
     '判定方案A未通过第 8、9 项（10.157% 超出 8.0% 上限 2.157 个百分点），方案B只未通过第 9 项（7.456% 超出 7.0% 缓冲线 0.456 个百分点）'),
    # 考点14：推荐方案损失/裕度/放大倍数 + 反向压力情景 + 马氏距离
    ('回答测算推荐方案在信用收缩与资金面收紧情景的委员会沿用冲击下损失 5.045%，距 8% 上限裕度 2.955 个百分点、冲击放大 1.59 倍即触及 8% 上限；',
     '回答测算推荐方案在信用收缩与资金面收紧情景的委员会沿用冲击下损失 5.565%，距 8% 上限裕度 2.435 个百分点、冲击放大 1.44 倍即触及 8% 上限；'),
    ('最可能情景为沪深300 −13.60%、中证500 −15.81%、创业板 −20.52%、国债 +0.35%、标普500（美元计）−6.30%、USD/CNH +0.93%，最小马氏距离 15.19；同一协方差口径下委员会信用收缩冲击的马氏距离为 50.77、该情景历史校准窗口为 6.70',
     '最可能情景为沪深300 −14.97%、中证500 −17.41%、创业板 −22.63%、国债 +0.38%、标普500（美元计）−6.99%、USD/CNH +1.02%，最小马氏距离 18.38；同一协方差口径下委员会信用收缩冲击的马氏距离为 52.08、该情景历史校准窗口为 6.70'),
]


def lark(*args):
    p = subprocess.run([LARK] + list(args), capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=env)
    return p.returncode, (p.stdout or ""), (p.stderr or "")


rc, out, err = lark("base", "+record-list", "--base-token", BT, "--table-id", TB,
                    "--page-size", "100", "--as", "user", "--format", "json")
dd = json.loads(out)["data"]
idx = {n: i for i, n in enumerate(dd["fields"])}
row = dd["data"][dd["record_id_list"].index(REC)]
cur = row[idx["考点信息（rubrics）"]]

t = cur
hit = 0
for old, new in FIXES:
    c = t.count(old)
    print(f'  {"OK " if c == 1 else "WARN"} 命中 {c} 处: {old[:48]}...')
    if c == 1:
        hit += 1
    t = t.replace(old, new, 1)

print(f'\n命中 {hit}/{len(FIXES)}；新文本 {len(t)} 字（原 {len(cur)} 字）')
for bad in ['9.902', '7.030', '5.045', '8.916', '6.650', '15.19', '50.77', '1.59 倍', '2.955']:
    print(f'  旧值「{bad}」残留: {t.count(bad)}')
for good in ['10.157', '7.456', '5.565', '9.257', '6.957', '18.38', '52.08', '1.44 倍', '2.435']:
    print(f'  新值「{good}」出现: {t.count(good)}')

if not APPLY:
    print('\n（DRY-RUN；加 --apply 执行写入）')
    sys.exit(0)

payload = {"update_records": {REC: {"考点信息（rubrics）": t}}}
rc, out, err = lark("base", "+record-batch-update", "--base-token", BT, "--table-id", TB,
                    "--json", json.dumps(payload, ensure_ascii=False),
                    "--as", "user", "--format", "json")
print(f'\n[写入] rc={rc} {(out or err)[:180]}')

rc, out, err = lark("base", "+record-list", "--base-token", BT, "--table-id", TB,
                    "--page-size", "100", "--as", "user", "--format", "json")
dd = json.loads(out)["data"]
idx = {n: i for i, n in enumerate(dd["fields"])}
row = dd["data"][dd["record_id_list"].index(REC)]
v = row[idx["考点信息（rubrics）"]]
print(f'[复核] 字数={len(v)}  含 10.157={ "10.157" in v }  含 5.565={ "5.565" in v }  '
      f'旧 9.902 残留={ "9.902" in v }')
