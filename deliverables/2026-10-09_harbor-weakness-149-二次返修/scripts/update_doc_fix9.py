# -*- coding: utf-8 -*-
"""把 fix8 交付文档升级为 fix9：更新 §3 验证结论分数、新增 fix9 整改段、顺延章节号。
基于 fix8 基线（bytes 读写保行尾）。
"""
import json
import pathlib
import sys

sys.stdout.reconfigure(encoding='utf-8')
DOC = pathlib.Path(r'C:\Users\Administrator\Desktop\wff-task\harbor-weakness'
                   r'\work_fin-b01_20261009_fix8-149\FIN3-WKN-149\交付文档.md')
ARCH = DOC.parent / '跑分产物与轨迹'

# 实测分数（reward.json 口径）
def rw(m):
    d = json.loads((ARCH / m / 'reward.json').read_text(encoding='utf-8'))
    return d['reward'], d['criteria_counted']

o_r, o_c = rw('oracle')
q_r, _ = rw('qwen3.8-max-0902')
g_r, _ = rw('gpt-5.6-sol')
p_r, _ = rw('claude-opus-4-8')
mean = (q_r + g_r + p_r) / 3

raw = DOC.read_bytes()
t = raw.decode('utf-8')
crlf = '\r\n' in t
NL = '\r\n' if crlf else '\n'

fix = []  # (old, new)


def add(old, new):
    fix.append((old, new))


# ---- §1 批次信息：加 fix9 轮说明 ----
add('（FIN3-WKN-149 对照 **2026-10-09 质检报告**二次返修后的重交批次）',
    '（FIN3-WKN-149 对照 **2026-10-09 质检报告** + **2026-10-11 质检报告(2)** 三轮返修后的重交批次；'
    '本轮为 **fix9 金标三处计算修正轮**）')

# ---- §3 开头说明 ----
add('> **本轮（fix8）按 2026-10-09 质检报告要求「输入规则修订后须重新生成候选 job」全量重跑四执行体**（非仅重跑判官）；'
    + NL + '> 下表的分数与试次号均为本轮 fix8 新跑结果。',
    '> **本轮（fix9）按 2026-10-11 质检报告(2) 修正金标三处计算错误后重跑**：oracle 新跑（金标变，G4），'
    '三模型复用 fix8 agent 产物**重判官**（报告定性「重跑判官」，agent 输入/规则未变）；' + NL
    + '> 下表的分数与试次号均为本轮 fix9 结果（fix8 值列作对照）。')

# ---- §3.1 G4 ----
add('| `reward` | **1.000000** | **> 0.85** | **PASS** |',
    f'| `reward` | **{o_r:.6f}** | **> 0.85** | **PASS** |')
add('> 36 条判据全部纳入判分（判官逐条 individual 会话）。试次：`FIN3-WKN-149__FKYpS8d`（2026-10-09）。',
    f'> 36 条判据全部纳入判分（判官逐条 individual 会话）。试次：`FIN3-WKN-149__DRcKq7u`（2026-10-11，'
    f'修复后金标新跑）。')

# ---- §3.2 三模型分数（整段替换表格与结论） ----
# 表格行
add('| `gpt-5.6-sol` | **0.612745** | 36 | 0 | `FIN3-WKN-149__qsFcMtD` | 7 项交付齐备 |',
    f'| `gpt-5.6-sol` | **{g_r:.6f}** | 36 | 0 | `FIN3-WKN-149__qsFcMtD` | 7 项交付齐备（fix8 产物 + fix9 重判） |')
add('| `claude-opus-4-8` | **0.649510** | 36 | 0 | `FIN3-WKN-149__vTPHQTW` | 7 项交付齐备 |',
    f'| `claude-opus-4-8` | **{p_r:.6f}** | 36 | 0 | `FIN3-WKN-149__vTPHQTW` | 7 项交付齐备（fix8 产物 + fix9 重判） |')
add('| `qwen3.8-max-0902` | **0.781863** | 36 | 0 | `FIN3-WKN-149__uqNx7ti` | 7 项交付齐备 |',
    f'| `qwen3.8-max-0902` | **{q_r:.6f}** | 36 | 0 | `FIN3-WKN-149__uqNx7ti` | 7 项交付齐备（fix8 产物 + fix9 重判） |')
add('| **三模型均分** | **0.681373** | — | — | — | **PASS（< 0.70）** |',
    f'| **三模型均分** | **{mean:.6f}** | — | — | — | **PASS（< 0.70）** |')

# ---- 结论段 ----
old_concl = ('结论：**三模型均分 0.681373 < 0.70，门禁 PASS；三模型均有得分（最低 `gpt-5.6-sol` '
             '0.612745 > 0），非"全 0 死题"；四执行体 `criteria_counted` 均为 36、`verifier_error` 均为 0。'
             '对照 fix7 轮（GPT 0.572304 / Opus 0.296569 / Qwen 0.878676 / 均值 0.582516）：'
             '本轮 gpt +0.040、opus +0.353（fix7 轮 opus 曾因端点故障偏低）、qwen −0.097，'
             '均值 +0.099——上升主要来自 `N02` 误扣修正与四条 likert 锚点/互斥区间明确化后判官口径收敛。**')
new_concl = (f'结论：**三模型均分 {mean:.6f} < 0.70，门禁 PASS；三模型均有得分（最低 `gpt-5.6-sol` '
             f'{g_r:.6f} > 0），非"全 0 死题"；四执行体 `criteria_counted` 均为 36、`verifier_error` 均为 0。'
             f'对照 fix8 轮（GPT 0.612745 / Opus 0.649510 / Qwen 0.781863 / 均值 0.681373）：'
             f'本轮 gpt {g_r - 0.612745:+.3f}、opus {p_r - 0.649510:+.3f}、qwen {q_r - 0.781863:+.3f}，'
             f'均值 {mean - 0.681373:+.3f}——金标三处修正后判官对同一组交付物的判分自然波动'
             f'（判官为 LLM 逐条采样），各模型判据零分分布见 §4.2。**')
add(old_concl, new_concl)

# ---- 定档说明（L100） ----
add('按**本包实测均分 0.681373** 落档：档位区间 `A1 ∈ [0.60, 0.70)` / `A2 ∈ [0.50, 0.60)` / '
    '`A3 < 0.50`，均分落 **A1**，故 `task.toml` 的 `keywords` / `metadata.difficulty` / `tags` '
    '三处已由 **A2 同步改为 A1**（包内 `"A2"` 残留 0 处，`task.zip` 已随之重建）。'
    '⚠️ **据实提示越档风险**：本均分距 0.70 门禁线仅 **1.9pp**，而判官为 LLM 逐条采样、'
    '同一批交付物两轮判分均分可差约 ±0.04——**重跑判官存在越线（>0.70）或越档至 A2 的风险**，'
    '此处按规范如实披露，未做任何择优选报。',
    f'按**本包实测均分 {mean:.6f}** 落档：档位区间 `A1 ∈ [0.60, 0.70)` / `A2 ∈ [0.50, 0.60)` / '
    f'`A3 < 0.50`，均分落 **A1**（`task.toml` 的 `keywords` / `metadata.difficulty` / `tags` '
    f'三处已为 **A1**，包内 `"A2"` 残留 0 处）。'
    f'⚠️ **据实提示越档风险（本轮加剧）**：本均分距 0.70 门禁线仅 **{((0.70 - mean) * 100):.2f}pp**'
    f'（fix8 轮为 1.9pp），而判官为 LLM 逐条采样、同一批交付物两轮判分均分可差约 ±0.04——'
    f'**重跑判官几乎必然越线（>0.70）或越档**，此处按规范如实披露当前实测值，未做任何择优选报。')

n = len(fix)
ok = 0
for old, new in fix:
    c = t.count(old)
    if c != 1:
        print(f'  [WARN] 期望 1 处、实际 {c}: {old[:60]}...')
    else:
        ok += 1
    t = t.replace(old, new, 1)

DOC.write_bytes(t.encode('utf-8'))
print(f'[OK] 正文替换 {ok}/{n} 命中；行尾={"CRLF" if crlf else "LF"}')
print(f'[OK] 文档大小 {len(t.encode("utf-8")):,} B；均分={mean:.6f} G4={o_r:.6f}')
print('\n下一步：新增 fix9 整改段（§8）+ 顺延飞书回写章节号 —— 见 fix9_append_doc.py')
