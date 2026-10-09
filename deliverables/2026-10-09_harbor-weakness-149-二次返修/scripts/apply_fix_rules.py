# -*- coding: utf-8 -*-
"""FIN3-WKN-149 二次返修 —— 项2/3（窗口口径统一）：
以字节级精确替换修改 rules_windows.csv 与 reproduce.py，逐条报告替换次数，不改动行尾。

口径裁定依据（实测，见 probe_windows.py 输出）：
  「窗口内逐日收益全部为负」口径下 S1–S4 的合格窗口数均为 0 个 → 校准冲击不可计算、题目崩塌；
  故采用「窗口整体累计收益为负」，与 R17/golden/判据原有实际实现一致，并去掉规则中不可达的「不少于 20 个」数量下限。
"""
import pathlib
import sys

sys.stdout.reconfigure(encoding='utf-8')
ROOT = pathlib.Path(r'C:\Users\Administrator\Desktop\wff-task')
PKG = ROOT / 'harbor-weakness' / 'FIN3-WKN-149'

EDITS = []


def edit(rel, old, new, note):
    EDITS.append((rel, old, new, note))


# ---------------------------------------------------------------- A. rules_windows.csv
edit('environment/input_files/rules_windows.csv',
     'window_rule,仅保留窗口内 10 个交易日的组合日收益全部为负且累计跌幅最大的窗口；'
     '同类窗口按累计跌幅排序取前若干（不少于 20 个）用于校准冲击计算',
     'window_rule,合格窗口判定：窗口内 10 个交易日按方案权重每日再平衡计算的组合累计收益为负即合格'
     '（以窗口整体的累计收益为准，不要求窗口内逐日收益均为负）；合格窗口按累计跌幅从大到小排序后'
     '全部用于校准冲击计算，不设数量下限；某情景没有合格窗口时须如实报告该情景无历史校准窗口，'
     '不得回退到未筛选的候选窗口、不得伪报窗口数量',
     'A1 window_rule 改为累计收益口径并去掉不可达的 20 个下限')

edit('environment/input_files/rules_windows.csv',
     'calibration,校准冲击 = 全部合格窗口内各风险因子在 10 个交易日内的累计变动中位数',
     'calibration,校准冲击 = 全部合格窗口内各风险因子在 10 个交易日内的累计变动中位数；'
     '某情景无合格窗口时其历史校准冲击按 0 计并在结论中说明',
     'A2 calibration 补充无合格窗口的合法处理')

# ---------------------------------------------------------------- B. reproduce.py
edit('solution/golden_output/FIN3-WKN-149_reproduce.py',
     '    仅保留窗口内 10 个交易日组合**累计收益为负**的窗口；\n'
     '    按累计跌幅排序取前 topn 个，不足 topn 个时全部保留——**不做任何回退、不伪报数量**。',
     '    合格窗口 = 窗口内 10 个交易日按方案权重每日再平衡计算的组合**累计收益为负**'
     '（以窗口整体的累计收益为准，不要求逐日收益均为负）；\n'
     '    合格窗口按累计跌幅排序后**全部保留**（规则不设数量下限）——**不做任何回退、不伪报数量**。',
     'B1 build_windows docstring 与 rules_windows.csv 同义')

edit('solution/golden_output/FIN3-WKN-149_reproduce.py',
     "R['window_rule_read'] = ('窗口起点取 rules_windows.csv 明示的「情景合格月份的次月第一个上交所交易日」；'\n"
     "                         '筛选条件取「窗口内 10 个交易日的组合收益为负」；'\n"
     "                         '排序取累计跌幅；对「不少于 20 个」的上限要求，实测各情景可保留窗口均少于 20 个，'\n"
     "                         '按规则「没有符合筛选条件的窗口时不得静默回退」的要求如实报告实际数量。')",
     "R['window_rule_read'] = ('窗口起点取 rules_windows.csv 明示的「情景合格月份的次月第一个上交所交易日」；'\n"
     "                         '合格窗口取「窗口内 10 个交易日按方案权重每日再平衡计算的组合累计收益为负」'\n"
     "                         '（以窗口整体的累计收益为准，不要求逐日收益均为负）；'\n"
     "                         '合格窗口按累计跌幅从大到小排序后全部保留，规则不设数量下限；'\n"
     "                         '若某情景无合格窗口则如实报告该情景无历史校准窗口、校准冲击按 0 计，'\n"
     "                         '不得回退到未筛选的候选窗口、不得伪报窗口数量。')",
     'B2 window_rule_read 文本同步')

edit('solution/golden_output/FIN3-WKN-149_reproduce.py',
     "print(f\"  {k}: 候选 {v['n_candidates']} 负收益 {v['n_negative']} 保留 {v['n_windows']} "
     "首个 {v['window_start']}~{v['window_end']} 达到20下限={v['floor_met']}\")",
     "print(f\"  {k}: 候选 {v['n_candidates']} 合格 {v['n_negative']} 采用 {v['n_windows']} "
     "首个 {v['window_start']}~{v['window_end']}\")",
     'B3 控制台输出去掉 20 下限字样')

edit('solution/golden_output/FIN3-WKN-149_reproduce.py',
     "A('**历史窗口构造（严格按 `rules_windows.csv`）**：窗口起点取**合格月份的次月第一个上交所交易日**，'\n"
     "  '窗口长度 10 个上交所交易日；仅保留窗口内组合**累计收益为负**的窗口；再按累计跌幅排序，'\n"
     "  '规则要求数量「不少于 20 个」，**不足 20 个时全部保留并如实报告实际数量，不做任何静默回退**'\n"
     "  '（本项口径下四个情景的可保留窗口均少于 20 个，成因是「次月首个交易日」这一锚定方式每个合格月份只产生 1 个候选窗口）：')",
     "A('**历史窗口构造（严格按 `rules_windows.csv`）**：窗口起点取**合格月份的次月第一个上交所交易日**，'\n"
     "  '窗口长度 10 个上交所交易日；**合格窗口的判定依据是窗口整体按方案权重每日再平衡计算的组合累计收益为负**'\n"
     "  '（不要求窗口内 10 个交易日的收益逐日均为负）；合格窗口按累计跌幅从大到小排序后**全部保留**'\n"
     "  '用于校准冲击计算，规则不设数量下限，报告如实给出各情景的候选窗口数与合格窗口数，不对候选窗口做静默回退：')",
     'B4 备忘录第四章窗口构造段同步')

edit('solution/golden_output/FIN3-WKN-149_reproduce.py',
     "A('| 情景 | 合格月份数 | 候选窗口数 | 组合累计收益为负的窗口数 | 实际保留窗口数 | 是否达到 20 个下限 | 选定窗口（起—止） | 窗口内最深累计跌幅 |')",
     "A('| 情景 | 合格月份数 | 候选窗口数 | 累计收益为负的合格窗口数 | 实际用于校准的窗口数 | 无合格窗口时的处理 | 选定窗口（起—止） | 窗口内最深累计跌幅 |')",
     'B5 备忘录窗口表头同步')

edit('solution/golden_output/FIN3-WKN-149_reproduce.py',
     "    A(f'| {k} | {len(R[\"scenario_months\"][k])} | {v[\"n_candidates\"]} | {v[\"n_negative\"]} | {v[\"n_windows\"]} | '\n"
     "      f'{\"是\" if v[\"floor_met\"] else \"否（规则下限不可达）\"} | {ws} | {dp} |')",
     "    A(f'| {k} | {len(R[\"scenario_months\"][k])} | {v[\"n_candidates\"]} | {v[\"n_negative\"]} | {v[\"n_windows\"]} | '\n"
     "      f'{\"—\" if v[\"n_windows\"] else \"如实报告无合格窗口，校准冲击按 0 计\"} | {ws} | {dp} |')",
     'B6 备忘录窗口表体同步')

edit('solution/golden_output/FIN3-WKN-149_reproduce.py',
     "A('**校准冲击（保留窗口内各风险因子 10 个交易日累计变动的中位数）**：')",
     "A('**校准冲击（合格窗口内各风险因子 10 个交易日累计变动的中位数）**：')",
     'B7 备忘录校准冲击小标题同步')


def main():
    changed = 0
    for rel, old, new, note in EDITS:
        p = PKG / rel
        data = p.read_bytes()
        ob, nb = old.encode('utf-8'), new.encode('utf-8')
        n = data.count(ob)
        if n != 1:
            print(f'  [FAIL] {note}: 命中 {n} 次（期望 1）  file={rel}')
            continue
        p.write_bytes(data.replace(ob, nb))
        changed += 1
        print(f'  [OK]   {note}')
    print(f'\n完成 {changed}/{len(EDITS)} 项字节级替换')
    return 0 if changed == len(EDITS) else 2


if __name__ == '__main__':
    sys.exit(main())
