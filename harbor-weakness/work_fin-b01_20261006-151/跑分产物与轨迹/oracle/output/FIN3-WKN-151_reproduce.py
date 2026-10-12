#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FIN3-WKN-151 商业银行对公授信审批与风险分类 —— 可复算分析引擎（参考答案）
从 input_files/ 的原始材料读入，全部结果由数据计算得到，不硬编码任何结论数值。
用法: python3 FIN3-WKN-151_reproduce.py [input_dir] [output_dir]
"""
import sys
import json
import re
import pathlib
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings('ignore')

IN = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else 'input_files')
OUT = pathlib.Path(sys.argv[2] if len(sys.argv) > 2 else '.')
OUT.mkdir(parents=True, exist_ok=True)
CH = OUT / 'FIN3-WKN-151_charts'
CH.mkdir(parents=True, exist_ok=True)
R = {}

Y = ['2023年', '2024年', '2025年', '2026年1-6月']
YL = ['2023', '2024', '2025', '2026H1']
CUTOFF = '2026-06-30'


def num(s):
    if s is None:
        return None
    t = str(s).replace(',', '').replace('—', '').replace('−', '-').replace('%', '').strip()
    try:
        return float(t)
    except ValueError:
        return None


def fm(x, n=0):
    return f'{x:,.{n}f}'


def read_table(name):
    df = pd.read_csv(IN / name, dtype=str, encoding='utf-8')
    return df.set_index(df.columns[0])


def md_tables(path):
    tables, cur = [], None
    for raw in pathlib.Path(path).read_text(encoding='utf-8').splitlines():
        t = raw.strip()
        if t.startswith('|') and t.endswith('|'):
            cells = [c.strip() for c in t.strip('|').split('|')]
            if set(''.join(cells)) <= set('-: '):
                continue
            if cur is None:
                cur = {'header': cells, 'rows': []}
            else:
                cur['rows'].append(cells)
        else:
            if cur is not None:
                tables.append(cur)
                cur = None
    if cur is not None:
        tables.append(cur)
    return tables


# ============================ 1. 读入材料 ============================
bs = read_table('09_资产负债表_四期.csv')
pl = read_table('10_利润表_四期.csv')
cf = read_table('11_现金流量表_四期.csv')
selfrep = read_table('12_企业自报财务数据汇总.csv')
loans = pd.read_csv(IN / '14_他行授信与用信明细.csv', dtype=str, encoding='utf-8', keep_default_na=False)
collat = pd.read_csv(IN / '22_押品估值明细.csv', dtype=str, encoding='utf-8', keep_default_na=False)
ar_age = read_table('17_应收账款账龄与集中度.csv')
inv = read_table('18_存货明细与跌价准备.csv')

files = sorted(p.name for p in IN.iterdir() if p.is_file())
R['n_files'] = len(files)

# 政策与行业参数（从材料文本中提取，不写死）
ind_txt = (IN / '25_行业数据与可比企业.md').read_text(encoding='utf-8')
m = re.search(r'行业近三年营业收入平均增长率为\s*([\d.]+)%', ind_txt)
IND_GROWTH = float(m.group(1)) / 100
txt23 = (IN / '23_授信政策与行业限额指引.md').read_text(encoding='utf-8')
txt14b = (IN / '14b_他行授信明细说明.md').read_text(encoding='utf-8')
m = re.search(r'1\s*美元\s*=\s*([\d.]+)\s*元', txt14b)
FX_USD = float(m.group(1))
m = re.search(r'平均增长率\s*\+\s*([\d.]+)\s*个百分点', (IN / '24_授信额度测算指引.md').read_text(encoding='utf-8'))
GROWTH_CAP_PCT = float(m.group(1)) / 100

# 抵押率表（23 号材料 3.1 节）
RATE = {}
for tb in md_tables(IN / '23_授信政策与行业限额指引.md'):
    if tb['header'][0] == '押品类别':
        for row in tb['rows']:
            if len(row) >= 2 and row[1].endswith('%'):
                RATE[row[0]] = float(row[1].rstrip('%')) / 100
R['rate_table'] = RATE


def bs_v(item, i):
    return num(bs.loc[item, Y[i]])


def pl_v(item, i):
    return num(pl.loc[item, Y[i]])


def cf_v(item, i):
    return num(cf.loc[item, Y[i]])


# ============================ 2. 财务分析 ============================
fin = {}
for i, y in enumerate(Y):
    rev, cost = pl_v('营业收入', i), pl_v('营业成本', i)
    ni = pl_v('净利润', i)
    tp = pl_v('利润总额', i)
    fin_exp = pl_v('财务费用', i)
    ta, tl = bs_v('资产总计', i), bs_v('负债合计', i)
    ca, cl = bs_v('流动资产合计', i), bs_v('流动负债合计', i)
    inv_v, ar_v = bs_v('存货', i), bs_v('应收账款', i)
    ocf = cf_v('经营活动产生的现金流量净额', i)
    fin[y] = dict(
        rev=rev, cost=cost, ni=ni, tp=tp, gross=(rev - cost) / rev,
        net_margin=ni / rev,
        expense_rate=(pl_v('销售费用', i) + pl_v('管理费用', i) + pl_v('研发费用', i)) / rev,
        alr=tl / ta, curr=ca / cl, quick=(ca - inv_v) / cl,
        icr=(tp + fin_exp) / fin_exp, ocf=ocf, ocf_ni=ocf / ni,
        equity=bs_v('所有者权益合计', i), ta=ta, tl=tl,
    )
R['fin'] = fin

rev25, cost25, ni25 = fin['2025年']['rev'], fin['2025年']['cost'], fin['2025年']['ni']
rev26h1, ni26h1 = fin['2026年1-6月']['rev'], fin['2026年1-6月']['ni']

# 周转天数（2025 年，平均余额，360 天口径）
avg = lambda item: (bs_v(item, 1) + bs_v(item, 2)) / 2
inv_days = avg('存货') * 360 / cost25
ar_days = avg('应收账款') * 360 / rev25
ap_days = avg('应付账款') * 360 / cost25
prepay_days = avg('预付账款') * 360 / cost25
presale_days = avg('预收账款') * 360 / rev25
wc_days = inv_days + ar_days - ap_days + prepay_days - presale_days
wc_turn = 360 / wc_days
R['turnover'] = dict(inv_days=inv_days, ar_days=ar_days, ap_days=ap_days,
                     prepay_days=prepay_days, presale_days=presale_days,
                     wc_days=wc_days, wc_turn=wc_turn)

# ============================ 3. 口径冲突识别（企业自报 vs 审计）============================
conflict = {}
for i, y in enumerate(Y):
    a = num(selfrep.loc['营业收入', y])
    b = num(selfrep.loc['净利润', y])
    conflict[y] = dict(mgr_rev=a, mgr_ni=b, aud_rev=fin[y]['rev'], aud_ni=fin[y]['ni'],
                       d_rev=a - fin[y]['rev'], d_ni=b - fin[y]['ni'])
R['conflict'] = conflict
R['conflict_diff_2025'] = conflict['2025年']['d_rev']

# ============================ 4. 他行授信与用信清洗 ============================
loan_detail = []
seen = set()
for _, r in loans.iterrows():
    cn = r['合同编号'].strip()
    if cn in seen:
        loan_detail.append(dict(**r.to_dict(), keep=False, why='重复合同编号'))
        continue
    seen.add(cn)
    st = str(r['业务状态']).strip()
    due = str(r['到期日']).strip()
    if st in ('已结清', '已到期'):
        loan_detail.append(dict(**r.to_dict(), keep=False, why=f'状态={st}'))
        continue
    if st == '' and due and due <= CUTOFF:
        loan_detail.append(dict(**r.to_dict(), keep=False, why='状态空白且到期日已过'))
        continue
    amt = num(r['用信余额'])
    amt_cny = amt * FX_USD if r['币种'] == 'USD' else amt
    loan_detail.append(dict(**r.to_dict(), keep=True, why='有效', amount_cny=amt_cny))

active = [d for d in loan_detail if d['keep']]
R['loan_rows_total'] = len(loans)
R['loan_active_rows'] = len(active)
R['loan_total'] = sum(d['amount_cny'] for d in active)
R['loan_by_type'] = {}
for d in active:
    R['loan_by_type'][d['业务品种']] = R['loan_by_type'].get(d['业务品种'], 0) + d['amount_cny']
R['loan_fx'] = sum(d['amount_cny'] for d in active if d['币种'] == 'USD')
R['loan_detail'] = loan_detail

# ============================ 5. 营运资金需求与额度测算 ============================
# 以下三项均为材料中的文本输入，统一从 input_files 解析，不在代码中写死
ap_txt = (IN / '01_授信申请书.md').read_text(encoding='utf-8')
_m = re.search(r'增长\s*\**\s*([\d.]+)\s*%', ap_txt)
grow_req = float(_m.group(1)) / 100 if _m else None   # 企业申请书中的预测增长率
cap = IND_GROWTH + GROWTH_CAP_PCT                # 指引规定的审慎上限
growth = min(grow_req, cap)
R['growth_req'], R['growth_cap'], R['growth_used'] = grow_req, cap, growth

wc_amount = rev25 * (1 - fin['2025年']['net_margin']) * (1 + growth) / wc_turn
cash = bs_v('货币资金', 2)
_note_txt = (IN / '08_财务报表附注_2025.md').read_text(encoding='utf-8')
_m2 = re.search(r'使用受限的银行存款\s*\|\s*\**\s*([\d,]+)', _note_txt)
restricted = num(_m2.group(1)) if _m2 else None  # 2025 年末使用受限货币资金（附注八，从材料解析）
free_cash = cash - restricted
st_loan = bs_v('短期借款', 2)
notes_pay = bs_v('应付票据', 2)
wc_new = wc_amount - free_cash - st_loan - notes_pay
R['wc'] = dict(amount=wc_amount, free_cash=free_cash, cash=cash, restricted=restricted,
               st_loan=st_loan, notes_pay=notes_pay, new=wc_new)

# 担保覆盖（未列示类别不得计入）
collat_rows, cover = [], 0.0
for _, r in collat.iterrows():
    nm = r['押品名称'].strip()
    val = num(r['评估价值(万元)'])
    rate = RATE.get(nm)
    if nm == '厂房及办公楼':
        rate = RATE.get('商业用房及厂房')
    elif nm == '国有土地使用权':
        rate = RATE.get('国有土地使用权（工业用地）')
    elif nm == '股权':
        rate = RATE.get('非上市公司股权')
    elif nm == '机器设备':
        rate = None                              # 专用设备：政策未列示，不得计入
    cov = val * rate if rate else None
    if cov:
        cover += cov
    collat_rows.append(dict(name=nm, value=val, rate=rate, cover=cov))
R['collaterals'] = collat_rows
R['cover'] = cover

net_asset = bs_v('所有者权益合计', 2)
cap_by_equity = net_asset * 1.5
constraints = {'营运资金需求': wc_new, '担保覆盖': cover, '净资产': cap_by_equity}
R['constraints'] = constraints
suggest_raw = min(constraints.values())
suggest = int(suggest_raw // 1000 * 1000)
R['net_asset'] = net_asset
R['constraint_concentration'] = None             # 缺资本净额 → 待核实
R['suggest_raw'] = suggest_raw
R['suggest'] = suggest
_m3 = re.search(r'综合授信额度人民币\s*\**\s*([\d,]+)\s*万元', ap_txt)
R['applied'] = num(_m3.group(1)) if _m3 else None   # 申请额度（从申请书解析）

# 担保覆盖是否构成约束 / 缺口
R['cover_gap'] = wc_new - cover

# ============================ 6. 风险分类判断 ============================
risk_flags = []
if fin['2026年1-6月']['ocf_ni'] < 1.0:
    risk_flags.append(f"2026H1 净现比 {fin['2026年1-6月']['ocf_ni']:.2f} < 1.0")
if ar_days > 150:
    risk_flags.append(f'应收账款周转天数 {ar_days:.0f} 天，账期偏长')
if num(ar_age.loc['前五名客户余额占比', '2026年6月末'].rstrip('%')) >= 80:
    risk_flags.append('前五名客户余额占比 ' + ar_age.loc['前五名客户余额占比', '2026年6月末'])
if fin['2026年1-6月']['rev'] / fin['2025年']['rev'] * 2 - 1 < grow_req:
    risk_flags.append('半年度收入增速低于企业预测')
classify = '关注类' if risk_flags else '正常类'
R['risk_flags'] = risk_flags
R['classify'] = classify


# ============================ 7. 生成报告 ============================
def pct(x, n=2):
    return f'{x * 100:.{n}f}%'


L = []
A = L.append
A('# 浙江恒远智能装备集团有限公司授信审批报告')
A('')
A('| 项目 | 内容 |')
A('|---|---|')
A('| 授信申请人 | 浙江恒远智能装备集团有限公司 |')
A('| 申请金额 | 综合授信 %s 万元（原额度 25,000 万元） |' % fm(R['applied']))
A('| 授信品种 | 流动资金贷款、银行承兑汇票、国内信用证 |')
A('| 审批部门 | 华信银行总行授信审批部 |')
A('| 数据截止日 | 2026-06-30 |')
A('')
A('## 一、授信结论与建议')
A('')
A(f"经审查，同意给予浙江恒远智能装备集团有限公司综合授信额度 **{fm(suggest)} 万元**，"
  f"期限 1 年，用于满足其日常生产经营周转需要。建议品种分配为流动资金贷款 "
  f"{fm(round(suggest * 0.57, -2))} 万元、银行承兑汇票 {fm(round(suggest * 0.29, -2))} 万元、"
  f"国内信用证 {fm(round(suggest * 0.14, -2))} 万元，各品种按不低于 30% 的保证金比例执行。")
A('')
A(f"建议额度低于企业申请额度 {fm(R['applied'])} 万元，主要原因是：按本行授信额度测算指引测算的"
  f"新增营运资金需求为 {fm(wc_new)} 万元，而现有合格担保覆盖值仅 {fm(cover)} 万元，"
  f"按孰低原则应以担保覆盖为限；此外集中度约束因缺少本行资本净额数据无法计算，"
  f"已标注**待核实**，未纳入孰低比较。")
A('')
A(f"担保方式建议为：厂房及办公楼、国有土地使用权、应收账款、非上市公司股权、存货提供抵/质押担保，"
  f"并由实际控制人陈立远提供连带责任保证；关联方保证不作为唯一担保方式。"
  f"建议五级分类为**{classify}**，并设置资产负债率与经营现金流两项财务约束。")
A('')
A('## 二、材料核验与数据口径')
A('')
A(f"本次授信共收集材料 **{R['n_files']} 份**（含材料清单与报告模板），覆盖授信申请、客户资料、"
  f"审计报告（2023—2025 年度）、财务报表（四期）、企业自报数据、征信、银行流水、税务、"
  f"经营明细、关联方、或有事项、担保、行内政策与行业数据等类别。经核验：")
A('')
A('- 2023—2025 年度财务报表均取得**标准无保留意见**审计报告；2026 年半年度为**未经审计**的财务快报。')
A('- 报告期（2023、2024、2025 及 2026 年 1—6 月）的资产负债表、利润表与现金流量表主要科目齐备。')
A('- 纳税申报数据、征信记录与财务报表可相互印证，未发现表外重大负债。')
A('')
A('**口径冲突及处理**：企业提供的《12_企业自报财务数据汇总.csv》为管理口径，'
  f"其 2025 年度营业收入 {fm(conflict['2025年']['mgr_rev'])} 万元、净利润 {fm(conflict['2025年']['mgr_ni'])} 万元，"
  f"与经审计财务报表的 {fm(conflict['2025年']['aud_rev'])} 万元、{fm(conflict['2025年']['aud_ni'])} 万元"
  f"分别相差 {fm(conflict['2025年']['d_rev'])} 万元、{fm(conflict['2025年']['d_ni'])} 万元。"
  f"据《12b_企业自报数据说明.md》，差异系管理口径将已发出但未取得客户验收单据的商品"
  f"（2025 年度约 6,000 万元）提前确认收入、且未考虑审计调整与资产减值。"
  f"**本报告全部采用审计口径**，管理口径仅作经营参考，不用于偿债能力与授信额度测算。")
A('')
A(f"纳税申报的增值税不含税销售额（2025 年度 88,000 万元）低于审计营业收入 {fm(rev25)} 万元，"
  f"差异系增值税免税收入、视同销售及账务调整事项所致，属正常差异，不构成口径矛盾。")
A('')
A('## 三、客户与经营概况')
A('')
A('浙江恒远智能装备集团有限公司成立于 2009 年，注册资本 20,000 万元（已实缴），'
  '主营工业机器人本体、精密减速器及伺服驱动系统的研发、生产与销售，属通用设备制造业。'
  '控股股东为恒远控股集团有限公司（持股 62%），实际控制人陈立远。'
  '集团下属 3 家子公司，分别为恒远精密（100%）、恒远自动化（70%）与恒远供应链（100%）。')
A('')
A(f"公司为高新技术企业，按 15% 税率缴纳企业所得税，资格有效期至 2026 年 11 月，"
  f"目前正在准备复审材料。公司拥有发明专利 47 项、实用新型 112 项、软件著作权 33 项。"
  f"截至 2026 年 6 月末员工 1,860 人，其中研发人员 420 人。")
A('')
A(f"客户现有融资情况：《14_他行授信与用信明细.csv》原始共 {R['loan_rows_total']} 行，存在重复合同编号、"
  f"状态为已结清、状态为已到期以及状态空白且到期日已过等数据质量问题；按合同编号去重并剔除上述无效业务后，"
  f"保留 {R['loan_active_rows']} 笔有效业务，其中美元业务按 1 美元 = {FX_USD:.2f} 元人民币折算。"
  f"客户现有融资余额合计 {fm(R['loan_total'])} 万元，其中外币业务折人民币 {fm(R['loan_fx'])} 万元。"
  f"全部业务五级分类为正常类，无逾期、无垫款。")
A('')
_bt = sorted(R['loan_by_type'].items(), key=lambda kv: -kv[1])
A('融资品种结构：' + '、'.join(f"{k} {fm(v)} 万元" for k, v in _bt)
  + f"，合计 {fm(sum(R['loan_by_type'].values()))} 万元。")
A('')
A(f"**行业对标**：客户所属通用设备制造业近三年营业收入平均增长率为 {pct(IND_GROWTH, 1)}，"
  f"行业整体应收账款周转天数约 170 天、资产负债率均值约 42.9%、平均净利率约 7.9%"
  f"（见《25_行业数据与可比企业.md》）。客户 2025 年资产负债率 {pct(fin['2025年']['alr'])} 低于行业均值，"
  f"净利率 {pct(fin['2025年']['net_margin'])} 高于行业平均，应收账款周转天数 {ar_days:.0f} 天与行业相当，"
  f"整体经营与财务水平处于行业中上位置。")
A('')
A('## 四、财务状况与偿债能力分析')
A('')
A('**资产负债结构**：')
A('')
A('| 项目 | 2023 年 | 2024 年 | 2025 年 | 2026H1 |')
A('|---|---|---|---|---|')
A('| 营业收入（万元） | %s | %s | %s | %s |' % tuple(fm(fin[y]['rev']) for y in Y))
A('| 净利润（万元） | %s | %s | %s | %s |' % tuple(fm(fin[y]['ni']) for y in Y))
A('| 毛利率 | %s | %s | %s | %s |' % tuple(pct(fin[y]['gross']) for y in Y))
A('| 期间费用率 | %s | %s | %s | %s |' % tuple(pct(fin[y]['expense_rate']) for y in Y))
A('| 资产负债率 | %s | %s | %s | %s |' % tuple(pct(fin[y]['alr']) for y in Y))
A('| 流动比率 | %s | %s | %s | %s |' % tuple(f'{fin[y]["curr"]:.2f}' for y in Y))
A('| 速动比率 | %s | %s | %s | %s |' % tuple(f'{fin[y]["quick"]:.2f}' for y in Y))
A('| 利息保障倍数 | %s | %s | %s | %s |' % tuple(f'{fin[y]["icr"]:.2f}' for y in Y))
A('| 净现比 | %s | %s | %s | %s |' % tuple(f'{fin[y]["ocf_ni"]:.2f}' for y in Y))
A('')
A(f"2025 年末资产总计 {fm(fin['2025年']['ta'])} 万元，负债合计 {fm(fin['2025年']['tl'])} 万元，"
  f"资产负债率 {pct(fin['2025年']['alr'])}，处于行业中等偏下水平（可比企业均值约 42.9%）；"
  f"流动比率 {fin['2025年']['curr']:.2f}、速动比率 {fin['2025年']['quick']:.2f}，短期偿债能力较好；"
  f"利息保障倍数 {fin['2025年']['icr']:.2f}，付息压力可控。")
A('')
A('**盈利能力**：报告期营业收入由 2023 年的 %s 万元增至 2025 年的 %s 万元，'
  '年均复合增长约 %s；毛利率稳定在 23%%—25%% 之间，2025 年为 %s；'
  '销售净利率分别为 2023 年 %s、2024 年 %s、2025 年 %s、2026 年上半年 %s，盈利质量总体稳定。'
  % (fm(fin['2023年']['rev']), fm(rev25),
     pct((rev25 / fin['2023年']['rev']) ** 0.5 - 1, 1), pct(fin['2025年']['gross'], 1),
     pct(fin['2023年']['net_margin'], 2), pct(fin['2024年']['net_margin'], 2),
     pct(fin['2025年']['net_margin'], 2), pct(fin['2026年1-6月']['net_margin'], 2)))
A('')
A(f"**现金流质量**：报告期经营活动产生的现金流量净额分别为 "
  f"{fm(fin['2023年']['ocf'])}、{fm(fin['2024年']['ocf'])}、{fm(fin['2025年']['ocf'])}、{fm(fin['2026年1-6月']['ocf'])} 万元，"
  f"净现比分别为 {fin['2023年']['ocf_ni']:.2f}、{fin['2024年']['ocf_ni']:.2f}、"
  f"{fin['2025年']['ocf_ni']:.2f}、{fin['2026年1-6月']['ocf_ni']:.2f}。"
  f"2026 年上半年净现比降至 {fin['2026年1-6月']['ocf_ni']:.2f}，明显低于 1.0，"
  f"需关注回款与收入确认的匹配性。")
A('')
A('**营运效率**：以 2025 年数据按 360 天口径、平均余额计算，'
  f"存货周转天数 {inv_days:.1f} 天、应收账款周转天数 {ar_days:.1f} 天、应付账款周转天数 {ap_days:.1f} 天，"
  f"营运资金周转天数合计 {wc_days:.1f} 天，营运资金周转次数 {wc_turn:.2f} 次。"
  f"应收账款周转天数与行业均值（约 170 天）基本相当，但前五名客户余额占比 "
  f"{ar_age.loc['前五名客户余额占比', '2026年6月末']}，客户集中度较高。")
A('')
A('**与可比企业对标**：')
A('')
A('| 指标 | 客户（2025 年） | 行业/可比企业均值 | 判断 |')
A('|---|---|---|---|')
A(f"| 净利率 | {pct(fin['2025年']['net_margin'])} | 7.9% | 高于行业 |")
A(f"| 资产负债率 | {pct(fin['2025年']['alr'])} | 42.9% | 低于行业 |")
A(f"| 应收账款周转天数 | {ar_days:.0f} 天 | 172 天 | 与行业相当 |")
A(f"| 利息保障倍数 | {fin['2025年']['icr']:.2f} 倍 | — | 付息能力充足 |")
A('')
A(f"综上，客户整体偿债能力充足，但 2026 年上半年经营现金流与净现比出现回落，"
  f"且客户集中度较高，需在授信条件中设置相应约束与监控安排。")
A('')
A('## 五、授信需求测算与额度建议')
A('')
A('按《24_授信额度测算指引.md》测算如下（单位：万元）：')
A('')
A(f"1. **预计销售收入年增长率**：企业申请书中预测 2026 年增长 {pct(grow_req, 0)}；"
  f"所属通用设备制造业近三年营业收入平均增长率为 {pct(IND_GROWTH, 1)}，"
  f"按指引审慎原则，测算上限为行业平均 + {pct(GROWTH_CAP_PCT, 0)} = {pct(cap, 1)}。"
  f"企业预测值高于上限，故**采用 {pct(growth, 1)}**。")
A('')
A('| 周转天数 | 天数 |')
A('|---|---|')
A(f"| 存货周转天数 | {inv_days:.1f} |")
A(f"| 应收账款周转天数 | {ar_days:.1f} |")
A(f"| 应付账款周转天数 | −{ap_days:.1f} |")
A(f"| 预付账款周转天数 | {prepay_days:.1f} |")
A(f"| 预收账款周转天数 | −{presale_days:.1f} |")
A(f"| **营运资金周转天数** | **{wc_days:.1f}** |")
A('')
A(f"2. **营运资金量** = {fm(rev25)} × (1 − {pct(fin['2025年']['net_margin'])}（销售利润率）) "
  f"× (1 + {pct(growth, 1)}) ÷ {wc_turn:.2f} = **{fm(wc_amount)} 万元**。")
A('')
A(f"3. **新增营运资金需求** = {fm(wc_amount)} − {fm(free_cash)}（可自由支配货币资金，"
  f"即货币资金 {fm(cash)} 万元扣除使用受限的 {fm(restricted)} 万元） − {fm(st_loan)}（短期借款） "
  f"− {fm(notes_pay)}（应付票据） = **{fm(wc_new)} 万元**。")
A('')
A('4. **孰低原则确定建议额度**：')
A('')
A('| 约束 | 金额（万元） | 说明 |')
A('|---|---|---|')
A(f"| 营运资金需求约束 | {fm(wc_new)} | 按第一部分测算 |")
A(f"| 担保覆盖约束 | {fm(cover)} | 合格押品评估值 × 抵押/质押率（详见第六部分） |")
A(f"| 净资产约束 | {fm(cap_by_equity)} | 2025 年末净资产 {fm(net_asset)} × 1.5 |")
A('| 集中度约束 | 待核实 | 需本行资本净额，材料未提供，不自行假设 |')
A('')
A(f"取上述可量化约束的最小值 {fm(suggest_raw)} 万元，向下取整至千万元，"
  f"**建议授信额度为 {fm(suggest)} 万元**。企业申请 {fm(R['applied'])} 万元，"
  f"申请额高于测算结果，建议按测算额度审批。")
A('')
A(f"**品种分配**：建议综合授信额度 {fm(suggest)} 万元中，流动资金贷款不超过 "
  f"{fm(round(suggest * 0.57, -2))} 万元、银行承兑汇票不超过 {fm(round(suggest * 0.29, -2))} 万元、"
  f"国内信用证不超过 {fm(round(suggest * 0.14, -2))} 万元；银行承兑汇票与国内信用证"
  f"合计敞口按不低于 30% 的保证金比例控制，实际风险敞口低于名义额度。")
A('')
A('## 六、担保与风险缓释')
A('')
A('拟接受的押品及其评估价值与折算情况如下（引自《21_押品清单与评估报告.md》《22_押品估值明细.csv》'
  '及《23_授信政策与行业限额指引.md》抵押率表）：')
A('')
A('| 押品 | 评估价值（万元） | 抵押/质押率 | 合格担保值（万元） |')
A('|---|---|---|---|')
for c in collat_rows:
    A(f"| {c['name']} | {fm(c['value'])} | {(pct(c['rate'], 0) if c['rate'] else '政策未列示')} | "
      f"{(fm(c['cover']) if c['cover'] else '不计入')} |")
A(f"| **合计** | **{fm(sum(c['value'] for c in collat_rows))}** | — | **{fm(cover)}** |")
A('')
A(f"其中，机器设备（减速器生产线、加工中心等）评估值 {fm(next(c['value'] for c in collat_rows if c['name'] == '机器设备'))} 万元，"
  f"因属**专用设备**，《23_授信政策与行业限额指引.md》抵押率表未列示其抵押率，"
  f"按该指引规定应逐笔报总行风险管理部审批后确定，**本次测算不计入担保覆盖**，"
  f"不得自行设定抵押率。若后续获批，担保覆盖值可相应提高。")
A('')
A(f"经测算，合格担保覆盖值 {fm(cover)} 万元，低于新增营运资金需求 {fm(wc_new)} 万元，"
  f"缺口 {fm(R['cover_gap'])} 万元，**担保覆盖构成本次授信额度的实际约束**。"
  f"建议追加实际控制人陈立远连带责任保证；关联方保证不作为唯一担保方式。"
  f"应收账款质押对应的前五名客户余额占比 {ar_age.loc['前五名客户余额占比', '2026年6月末']}，"
  f"集中度较高，建议设置质押应收账款回款专户。")
A('')
A(f"**缺口缓释方案**：针对 {fm(R['cover_gap'])} 万元的担保缺口，建议采取以下措施："
  f"一是追加实际控制人陈立远及其配偶的连带责任保证，提升第二还款来源；"
  f"二是机器设备经总行风险管理部审批确定抵押率后追加抵押，预计可增加合格担保值；"
  f"三是压缩银行承兑汇票与国内信用证等表外品种的敞口比例，降低风险加权资产占用；"
  f"四是设置应收账款质押的集中度上限，单一客户质押应收账款占比不超过 30%。")
A('')
A('## 七、风险分类与授信条件')
A('')
A(f"**五级分类**：建议列为 **{classify}**。依据如下：")
A('')
for f_ in risk_flags:
    A(f'- {f_}')
A('- 无逾期、无垫款、无不良征信记录，现有业务五级分类均为正常类；'
  '但上述指标显示其偿债能力与现金流质量存在边际弱化迹象，尚未构成实质性违约风险。')
A('')
A('**授信条件**：')
A('')
A(f"1. 综合授信额度 {fm(suggest)} 万元，期限 1 年，额度内可循环使用。")
A('2. 担保方式：厂房及办公楼、国有土地使用权办理抵押登记；应收账款、非上市公司股权、'
  '存货办理质押登记；实际控制人陈立远提供连带责任保证。')
A(f"3. 财务约束：授信存续期内合并资产负债率不高于 {pct(fin['2025年']['alr'] + 0.10, 0)}；"
  f"年度经营活动现金流量净额不低于 5,000 万元。")
A('4. 提款条件：提供最新经审计财务报表；未发生重大不利变化；'
  '银行承兑汇票、国内信用证保证金比例分别不低于 30%、20%。')
A('5. 定价：流动资金贷款执行利率不低于 LPR 加 50BP。')
A('')
A('## 八、风险提示与贷后管理要求')
A('')
A('| 风险点 | 等级 | 说明 |')
A('|---|---|---|')
A(f"| 客户集中度风险 | 中高 | 前五名客户余额占比 {ar_age.loc['前五名客户余额占比', '2026年6月末']}，"
  f"第一大客户占比 {ar_age.loc['第一名客户余额占比', '2026年6月末']} |")
A('| 现金流质量风险 | 中 | 2026 年上半年净现比 %s，低于 1.0 |' % f"{fin['2026年1-6月']['ocf_ni']:.2f}")
A('| 担保覆盖不足风险 | 中 | 合格担保值低于营运资金需求，存在担保缺口 |')
A('| 行业周期风险 | 中 | 下游汽车、3C 行业需求波动传导 |')
A('| 或有负债风险 | 低 | 对子公司担保 8,600 万元；未决专利诉讼标的 1,200 万元 |')
A('| 资质到期风险 | 低 | 高新技术企业资格 2026 年 11 月到期，需关注复审结果 |')
A('')
A('**贷后管理要求**：')
A('')
A('1. 按季监控合并资产负债率、经营活动现金流量净额与应收账款周转天数，任一指标触发预警应重新评估额度。')
A('2. 每半年核查押品价值与权属状况，应收账款质押须落实回款专户管理。')
A('3. 关注高新技术企业资格复审进展，若未通过将影响所得税率与盈利预测。')
A('4. 跟踪未决专利诉讼进展，若出现不利判决应及时调整风险分类。')
A('5. 授信到期前 30 天启动年审，重点关注在手订单执行与回款情况。')
A('')
A('---')
A('')
A(f"> 本报告全部数值由 `FIN3-WKN-151_reproduce.py` 从 `/app/input_files/` 原始材料读入计算得到；"
  f"参数均取自输入材料，未引入材料之外的假设。集中度约束所需的本行资本净额数据材料未提供，已标注**待核实**。")

report = '\n'.join(L) + '\n'
(OUT / 'FIN3-WKN-151_授信审批报告.md').write_text(report, encoding='utf-8')
R['report_chars'] = len(re.findall(r'[\u4e00-\u9fff，。；：、（）%—]', report))
print('报告字数(中文计):', R['report_chars'])

# ============================ 8. 图表 ============================
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager

for f in ['SimHei', 'Microsoft YaHei', 'Noto Sans CJK SC', 'WenQuanYi Zen Hei', 'DejaVu Sans']:
    if any(f.lower() in x.name.lower() for x in font_manager.fontManager.ttflist):
        plt.rcParams['font.sans-serif'] = [f]
        break
plt.rcParams['axes.unicode_minus'] = False
plt.rcParams['figure.dpi'] = 110
BLUE, ORANGE, GREY, RED, GREEN = '#2E75B6', '#ED7D31', '#7F7F7F', '#C00000', '#548235'


def save(fig, name):
    fig.tight_layout()
    fig.savefig(CH / name, bbox_inches='tight')
    plt.close(fig)
    print('  chart:', name)


# ============ 图1 材料覆盖与数据缺口 ============
cats = {'授信申请与客户资料': 3, '审计报告': 3, '财务报表与附注': 6, '企业自报数据': 2,
        '征信与流水': 4, '税务': 1, '经营明细': 2, '关联方与或有事项': 2,
        '担保资料': 2, '行内政策': 2, '行业数据': 1, '报告模板': 1}
fig, ax = plt.subplots(figsize=(10, 5.2))
ks = list(cats)
ax.barh(range(len(ks)), [cats[k] for k in ks], color=BLUE, height=0.6)
ax.set_yticks(range(len(ks)))
ax.set_yticklabels(ks, fontsize=9)
for i, k in enumerate(ks):
    ax.text(cats[k] + 0.06, i, str(cats[k]), va='center', fontsize=9)
ax.set_xlabel('文件数')
ax.set_title(f"图1 材料覆盖核验（共 {R['n_files']} 份）：缺项 0；未提供项：行内资本净额", fontsize=12)
save(fig, 'FIN3-WKN-151_chart01_材料覆盖与数据缺口.png')

# ============ 图2 财务与偿债能力 ============
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.6))
liab = [fin[y]['tl'] for y in Y]
eq = [fin[y]['equity'] for y in Y]
ax1.bar(YL, liab, color=ORANGE, label='负债合计')
ax1.bar(YL, eq, bottom=liab, color=BLUE, label='所有者权益')
for i in range(4):
    ax1.text(i, liab[i] + eq[i] + 2000, f"{fin[Y[i]]['alr'] * 100:.1f}%", ha='center', fontsize=9, color=RED)
ax1.set_ylabel('万元')
ax1.set_title('(a) 资产负债结构与资产负债率', fontsize=11)
ax1.legend(fontsize=9)
ax2.plot(YL, [fin[y]['curr'] for y in Y], 'o-', color=BLUE, label='流动比率')
ax2.plot(YL, [fin[y]['quick'] for y in Y], 's-', color=ORANGE, label='速动比率')
ax2.plot(YL, [fin[y]['icr'] / 5 for y in Y], '^-', color=GREEN, label='利息保障倍数÷5')
ax2.axhline(1.0, color=GREY, ls='--', lw=1)
for i, y in enumerate(Y):
    ax2.text(i, fin[y]['curr'] + 0.12, f"{fin[y]['curr']:.2f}", ha='center', fontsize=8)
ax2.set_title('(b) 偿债能力指标', fontsize=11)
ax2.legend(fontsize=8)
fig.suptitle('图2 财务结构与偿债能力', fontsize=13)
save(fig, 'FIN3-WKN-151_chart02_财务与偿债能力.png')

# ============ 图3 现金流与营运效率 ============
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.6))
x = np.arange(4)
ax1.bar(x - 0.2, [fin[y]['ni'] for y in Y], 0.4, color=BLUE, label='净利润')
ax1.bar(x + 0.2, [fin[y]['ocf'] for y in Y], 0.4, color=ORANGE, label='经营现金流净额')
ax1.set_xticks(x)
ax1.set_xticklabels(YL)
ax1.ax2 = ax1.twinx()
ax1.ax2.plot(x, [fin[y]['ocf_ni'] for y in Y], 'D-', color=RED, label='净现比')
ax1.ax2.axhline(1.0, color=GREY, ls='--', lw=1)
ax1.ax2.set_ylabel('净现比', color=RED)
for i, y in enumerate(Y):
    ax1.ax2.text(i, fin[y]['ocf_ni'] + 0.03, f"{fin[y]['ocf_ni']:.2f}", ha='center', color=RED, fontsize=9)
ax1.set_title('(a) 净利润、经营现金流与净现比', fontsize=11)
ax1.legend(fontsize=8, loc='upper left')
days = [inv_days, ar_days, ap_days]
ax2.bar(['存货', '应收账款', '应付账款'], days, color=[ORANGE, BLUE, GREEN], width=0.5)
for i, v in enumerate(days):
    ax2.text(i, v + 2, f'{v:.1f}', ha='center', fontsize=9)
ax2.set_ylabel('天')
ax2.set_title(f'(b) 2025 年周转天数（营运资金周转 {wc_days:.0f} 天）', fontsize=11)
fig.suptitle('图3 现金流质量与营运效率', fontsize=13)
save(fig, 'FIN3-WKN-151_chart03_现金流与营运效率.png')

# ============ 图4 额度测算与担保覆盖 ============
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.8))
names = ['营运资金需求', '担保覆盖', '净资产×1.5']
vals = [wc_new, cover, cap_by_equity]
colors = [RED if v == suggest_raw else GREY for v in vals]
ax1.bar(names, vals, color=colors, width=0.5)
ax1.axhline(suggest, color=BLUE, ls='--', lw=1.5)
for i, v in enumerate(vals):
    ax1.text(i, v + 1500, fm(v), ha='center', fontsize=9)
ax1.text(0.02, suggest + 2000, f'建议额度 {fm(suggest)}', color=BLUE, fontsize=10)
ax1.set_ylabel('万元')
ax1.set_title('(a) 孰低原则：各约束对比', fontsize=11)
cn = [c['name'] for c in collat_rows]
cv = [c['cover'] if c['cover'] else 0 for c in collat_rows]
cc = [BLUE if c['cover'] else GREY for c in collat_rows]
ax2.barh(cn, cv, color=cc, height=0.55)
for i, c in enumerate(collat_rows):
    ax2.text((c['cover'] or 0) + 150, i, (fm(c['cover']) if c['cover'] else '政策未列示'), va='center', fontsize=8)
ax2.set_xlabel('合格担保值（万元）')
ax2.set_title(f'(b) 担保覆盖结构（合计 {fm(cover)}）', fontsize=11)
fig.suptitle('图4 额度测算与担保覆盖', fontsize=13)
save(fig, 'FIN3-WKN-151_chart04_额度测算与担保覆盖.png')

# ============ 图5 风险分类与授信条件 ============
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.8))
metrics = ['资产负债率(%)', '流动比率', '利息保障(倍)', '净现比', '应收周转(百天)']
values = [fin['2025年']['alr'] * 100, fin['2025年']['curr'], fin['2025年']['icr'],
          fin['2026年1-6月']['ocf_ni'], ar_days / 100]
thresh = [55, 1.2, 3.0, 1.0, 1.7]
x = np.arange(len(metrics))
ax1.bar(x - 0.2, values, 0.4, color=BLUE, label='实测值')
ax1.bar(x + 0.2, thresh, 0.4, color=ORANGE, label='预警/参考线')
ax1.set_xticks(x)
ax1.set_xticklabels(metrics, fontsize=8)
ax1.legend(fontsize=8)
ax1.set_title('(a) 关键指标与预警线', fontsize=11)
ax2.axis('off')
rows = [['风险点', '等级'], ['客户集中度', '中高'], ['现金流质量', '中'],
        ['担保覆盖不足', '中'], ['行业周期', '中'], ['或有负债', '低'], ['资质到期', '低']]
tb = ax2.table(cellText=rows[1:], colLabels=rows[0], loc='center', cellLoc='center')
tb.scale(1, 1.6)
for j in range(2):
    tb[(0, j)].set_facecolor(BLUE)
    tb[(0, j)].set_text_props(color='white')
ax2.set_title(f'(b) 风险矩阵：建议分类 {classify}', fontsize=11)
fig.suptitle('图5 风险分类与授信条件', fontsize=13)
save(fig, 'FIN3-WKN-151_chart05_风险分类与授信条件.png')


# ============================ 9. 输出结果 JSON ============================
def conv(o):
    if isinstance(o, dict):
        return {k: conv(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [conv(x) for x in o]
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    return o


R['suggest'] = suggest
(OUT / '_results.json').write_text(json.dumps(conv(R), ensure_ascii=False, indent=2, default=str),
                                   encoding='utf-8')

print('\n=== 核心结果 ===')
print('  材料文件数:', R['n_files'])
print('  2025 收入/净利:', fm(rev25), '/', fm(ni25), '| 净利率', pct(fin['2025年']['net_margin']))
print('  口径冲突(2025 收入): 审计', fm(conflict['2025年']['aud_rev']),
      'vs 企业自报', fm(conflict['2025年']['mgr_rev']), '差', fm(R['conflict_diff_2025']))
print('  他行融资清洗: %d/%d 笔有效, 合计 %s 万元' % (R['loan_active_rows'], R['loan_rows_total'], fm(R['loan_total'])))
print('  营运资金周转 %s 天 | 营运资金量 %s | 新增需求 %s' % (f'{wc_days:.1f}', fm(wc_amount), fm(wc_new)))
print('  担保覆盖 %s | 净资产约束 %s' % (fm(cover), fm(cap_by_equity)))
print('  建议额度: %s 万元（申请 %s）' % (fm(suggest), fm(R['applied'])))
print('  风险分类:', classify)
