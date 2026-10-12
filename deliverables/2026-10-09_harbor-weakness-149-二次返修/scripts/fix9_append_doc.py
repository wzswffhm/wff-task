# -*- coding: utf-8 -*-
"""交付文档新增 fix9 整改段（§8），顺延飞书回写为 §9，更新 §4.2 零分分布、日期。"""
import json
import pathlib
import sys

sys.stdout.reconfigure(encoding='utf-8')
DOC = pathlib.Path(r'C:\Users\Administrator\Desktop\wff-task\harbor-weakness'
                   r'\work_fin-b01_20261009_fix8-149\FIN3-WKN-149\交付文档.md')
ARCH = DOC.parent / '跑分产物与轨迹'


def stats(m):
    d = json.loads((ARCH / m / 'reward-details.json').read_text(encoding='utf-8'))['reward']
    cs = d['criteria']
    zs = [(it['id'], it.get('weight') or 0) for it in cs
          if abs(float(it.get('value') or 0.0)) < 1e-12]
    return d['score'], zs


rows = {m: stats(m) for m in ['oracle', 'qwen3.8-max-0902', 'gpt-5.6-sol', 'claude-opus-4-8']}
tri = [m for m in rows if m != 'oracle']
common = set.intersection(*[set(i for i, _ in rows[m][1]) for m in tri])
wmap = {i: w for i, w in rows[tri[0]][1]}


def zl(m):
    zs = rows[m][1]
    return ' '.join(f'`{i}`({w:g})' for i, w in zs) if zs else '—（无零分判据）'


raw = DOC.read_bytes()
t = raw.decode('utf-8')
NL = '\r\n' if '\r\n' in t else '\n'

# 1) §4.2 零分分布表更新
old_tbl = (
    '| oracle | 1.000000 | **0** | —（无零分判据） |' + NL +
    '| qwen3.8-max-0902 | 0.798600 | 7 | `R06`(3) `R07`(3) `R08`(7) `R13`(7) `R14`(7) `R15`(7) `R31`(7) |' + NL +
    '| gpt-5.6-sol | 0.642500 | 12 | `R05`(3) `R06`(3) `R07`(3) `R08`(7) `R09`(7) `R10`(7) `R13`(7) `R14`(7) `R15`(7) `R17`(7) `R18`(7) `R31`(7) |' + NL +
    '| claude-opus-4-8 | 0.676500 | 12 | `R05`(3) `R06`(3) `R07`(3) `R09`(7) `R13`(7) `R14`(7) `R15`(7) `R16`(7) `R18`(7) `R19`(7) `R28`(3) `R31**(7) |'
)
# 实际 fix8 文档的表可能略有不同，改用稳健的逐行匹配：以「### 4.2」段落内替换表体
idx42 = t.find('### 4.2 三模型判据零分分布')
idx42_end = t.find('## 5.', idx42)
seg = t[idx42:idx42_end]
# 替换表体内所有数据行（保留表头）
new_rows = []
for m in ['oracle', 'qwen3.8-max-0902', 'gpt-5.6-sol', 'claude-opus-4-8']:
    sc, zs = rows[m]
    if m == 'oracle':
        new_rows.append(f'| oracle | {sc:.6f} | **{len(zs)}** | {zl(m)} |')
    else:
        new_rows.append(f'| {m} | {sc:.6f} | {len(zs)} | {zl(m)} |')
# 表体 = 从第二行（数据首行）到表格结束（4 个数据行）
import re
tbl_lines = seg.split(NL)
data_start = next(i for i, l in enumerate(tbl_lines) if l.startswith('| oracle |'))
data_end = data_start + 4
tbl_lines[data_start:data_end] = new_rows
new_seg = NL.join(tbl_lines)
t = t[:idx42] + new_seg + t[idx42_end:]

# 共同行更新
old_common = '**三模型共同全零集合**：`R06`(3) / `R07`(3) / `R13`(7) / `R14`(7) / `R15`(7) / `R31`(7)，权重和 **34.0**。'
new_common = (f'**三模型共同全零集合**：{" / ".join(f"`{i}`({wmap[i]:g})" for i in sorted(common))}，'
              f'权重和 **{sum(wmap.get(i, 0) for i in common)}**。')
if old_common in t:
    t = t.replace(old_common, new_common, 1)
else:
    # 稳健：找该行替换
    for line in t.split(NL):
        if line.startswith('**三模型共同全零集合**'):
            t = t.replace(line, new_common, 1)
            break

# 2) 顺延 §8 飞书回写 -> §9（在 §8 前插入新段）
fix9_section = f'''## 8. 本轮（2026-10-11 金标三处计算修正）整改记录

甲方于 2026-10-11 出具**质检报告(2)**（结论：待改，返修类型「重跑判官」），指出金标 `reproduce.py` 存在**三处实质计算错误**与一处配置缺项；本轮**先实际修正标准答案/评分依据，再重跑受影响 job**（oracle 新跑 + 三模型重判官），非无改动原样重采样。

| # | 质检问题 | 处置 | 闭环证据 |
|---|---|---|---|
| **项2** | 金标 `reproduce.py:243` 把 `params_committee_shocks.csv` 的 `cgb_shock_bp` 数值**除 100**（按百分点处理）；题面与字段明确单位 **bp**，应**除 10000**。S4 五期限冲击 0.80/0.60/0.45/−0.45/−0.50bp 与久期 0.1/0.3/1.2/3.6/1.8 对应国债收益应为 **+0.0172%**（非 +1.72%） | `cgb_pnl` 内 `/ 100.0` → **`/ 10000.0`**（bp→小数）。仅此一处单位修正即联动重算：推荐方案 S4 沿用损益 **−5.0454% → −5.564754%**、方案B **−7.0300% → −7.4557%**（与报告期望逐字一致）；32 条正式压力结果中**沿用冲击**的国债贡献与合计、超限幅度、压力图、反向压力与马氏距离全部联动重算 | ① `max_stress` 推荐 −5.5648% / 方案B −7.4557% / 方案A −10.1574% / 当前持仓 −9.2566%；② `md_committee` **50.77 → 52.08**；③ `reverse_stress.loss` −0.050454 → **−0.055648**、`md` 15.19 → **18.38**；④ 金标备忘录/5 图全部由修复后脚本**重新生成**（非只改报告数字、保留错误代码） |
| **项3** | 金标 `reproduce.py:257` 历史校准分解把**境内三项权重合计**乘沪深300冲击，忽略中证500/创业板各自冲击。S1 推荐境内权益按 −1.20%/−1.04%/−3.35% 与 14.75%/8.85%/5.90% 复算应约 **−0.46669%**，金标给 −0.35% | 境内权益改为**逐项权重 × 各自冲击后相加**：`(w300×sh300 + w905×sh905 + w399006×sh399006)`。仅影响**历史校准冲击**的 16 条（沿用冲击不受影响） | ① S1 推荐历史校准境内权益贡献由 −0.003545 → **−0.004670**（≈−0.467%，与报告 −0.46669% 吻合）；② 32 条正式结果中 historical 分量全部按各自因子重算；③ 金标备忘录第 3/4 章历史校准数据全部更新 |
| **项4** | 金标 `reproduce.py:253` 历史校准已保存标普500**人民币**收益，却用 `h['SPX']/(1+h['USD_CASH'])` 当美元收益、之后又复合汇率，反向换算**缺 +1 及 −1** | 改为 **`(1+人民币收益)/(1+汇率收益) − 1`**（正确反算）。同步 32 条正式压力结果、8 条基准、图3/图4 及相关判据 | ① 历史校准 `SPX_USD` 分量按正确反算重算；② 8 条基准的 historical 合计全部更新；③ 图3（两套冲击对比）、图4（最大压力损失/反向压力）由修复后脚本重新生成 |
| **项7** | `tests/rubrics.toml` 可解析但**缺少 `[scoring] aggregation = "weighted_mean"`**（rewardkit 原规范 §6.3 固定项） | 补齐显式聚合配置；`rubrics.json` 的 `metadata.scoring` 同步补 `aggregation = "weighted_mean"`（两侧同义） | ① TOML 末尾新增 `[scoring] aggregation = "weighted_mean"`（36 条判据不变）；② `check_rubrics.py` **[PASS]**、`validate_rubrics.py` **FAIL=0**、`check_rubric_style.py --strict` **FAIL=0**（门禁未破坏）；③ 报告要求「与第 2–4 项修订完成后一起核对聚合及受影响判分」已一并核对 |
| **项1/5/6**（报告判【正确】项，本轮复核未回退） | 项1 四执行体轨迹/36 判据/分池 204 属实；项5 业务输入/规则可读、2044 交易日、20.5% 换手率、现金路径可复核；项6 ZIP 结构/CRC/权限正常 | 本轮全部复核**维持正确**：oracle 零分空集（36/36 满分）、三模型 `criteria_counted=36`、`verifier_error=0`；批次包结构与权限位不变 | 见 §3.1 / §3.2 / §4 |

### 8.1 fix9 验证结论

- **G4（oracle）**：`reward = 1.000000`（36/36，`verifier_error=0`，零分空集）——修复后金标通过参考答案预检。
- **G5（三模型均分）**：`(0.850490 + 0.649510 + 0.589461) / 3 = 0.696487 < 0.70` → **PASS**；三模型均有得分（最低 gpt 0.589461 > 0），非死题。
- **定档**：0.696487 ∈ A1 ∈ [0.60, 0.70) → **A1**（`task.toml` 三处已为 A1）。距 0.70 门禁仅 **0.35pp**，越档风险**极高**（判官两轮均分可差 ±0.04），据实披露。
- **静态门禁**：`check_rubrics.py` PASS / `validate_rubrics.py` FAIL=0 / `check_rubric_style.py` FAIL=0。

### 8.2 判分对照（fix8 → fix9）

| 执行体 | fix8 reward | fix9 reward | 变化 | 说明 |
|---|---|---|---|---|
| oracle | 1.000000 | **1.000000** | ±0 | 金标修正后新跑，仍满分 |
| qwen3.8-max-0902 | 0.781863 | **0.850490** | +0.069 | 同一交付物重判官（LLM 采样波动） |
| claude-opus-4-8 | 0.649510 | **0.649510** | ±0 | 同上 |
| gpt-5.6-sol | 0.612745 | **0.589461** | −0.023 | 同上 |
| **三模型均分** | 0.681373 | **0.696487** | +0.015 | 仍 < 0.70，PASS |

> 三模型产物（备忘录/复算脚本/5 图）为 fix8 agent 原生产物（agent 输入与规则本轮未变，报告定性「重跑判官」），故分数变化源于**金标修正 + 判官 LLM 采样波动**的合成效应；各模型判据零分分布见 §4.2。

---

'''

# 找原 §8（飞书记录回写）位置，顺延为 §9，并在其前插入 fix9 段
old_h8 = '## 8. 飞书记录回写'
if old_h8 in t:
    t = t.replace(old_h8, fix9_section + '## 9. 飞书记录回写', 1)
else:
    print('[ERR] 未找到 §8 飞书记录回写')
    sys.exit(1)

# 更新日期行
old_date = t.split(NL)[-2] if t.split(NL)[-1] == '' else None
for line in t.split(NL):
    if line.startswith('*文档生成：'):
        new_line = ('*文档生成：2026-10-09；fix8 跑分与归档：2026-10-10；'
                    '**fix9 金标三处修正与重跑：2026-10-11**（FIN3-WKN-149 二次返修重交版 **1.0.8**，'
                    '批次 `work_fin-b01_20261009_fix8-149`）；验证环境：WSL Ubuntu + Docker Engine 29.x.*')
        t = t.replace(line, new_line, 1)
        break

DOC.write_bytes(t.encode('utf-8'))
print(f'[OK] 已插入 fix9 整改段（§8）、飞书回写顺延为 §9；更新日期')
print(f'[OK] 文档大小 {len(t.encode("utf-8")):,} B')
print(f'[OK] 零分分布共同全零={sorted(common)} 权重和={sum(wmap.get(i,0) for i in common)}')
# 检查占位/未替换
import re as _re
ph = _re.findall(r'\{\{[A-Z_]+\}\}', t)
print(f'[检查] 残留占位符: {ph or "无"}')
print(f'[检查] 章节: {[l for l in t.split(NL) if l.startswith("## ")][:15]}')
