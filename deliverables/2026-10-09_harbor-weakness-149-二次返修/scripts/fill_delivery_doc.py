# -*- coding: utf-8 -*-
"""回填 FIN3-WKN-149 fix8 交付文档：G5 分数 / 试次号 / 零分分布 / 定档说明 / 飞书包大小。
同时据实改写 3 处正文（opus 端点、未采用试次口径、文档日期），并把 L23 硬编码 A2 改为 A1。
bytes 读写保持原行尾。
"""
import json
import pathlib
import sys

sys.stdout.reconfigure(encoding='utf-8')
DOC = pathlib.Path(r'C:\Users\Administrator\Desktop\wff-task\harbor-weakness'
                   r'\work_fin-b01_20261009_fix8-149\FIN3-WKN-149\交付文档.md')
ARCH = DOC.parent / '跑分产物与轨迹'
SZ_FILE = pathlib.Path(r'C:\Users\Administrator\Desktop\wff-task\harbor-weakness'
                       r'\work_fin-b01_20261009_fix8-149.zip')


def stats(m):
    d = json.loads((ARCH / m / 'reward-details.json').read_text(encoding='utf-8'))['reward']
    cs = d['criteria']
    zs = [(it['id'], it.get('weight') or 0) for it in cs
          if abs(float(it.get('value') or 0.0)) < 1e-12]
    return d['score'], zs


SLOTS = {}
for m, key in [('oracle', 'ORACLE'), ('qwen3.8-max-0902', 'QWEN'),
               ('gpt-5.6-sol', 'GPT'), ('claude-opus-4-8', 'OPUS')]:
    sc, zs = stats(m)
    SLOTS[f'RD_{key}'] = f'{sc:.6f}'
    SLOTS[f'Z_{key}'] = str(len(zs))
    SLOTS[f'ZL_{key}'] = ' '.join(f'`{i}`({w:g})' for i, w in zs) if zs else '—（无零分判据）'

SLOTS.update({
    'G5_GPT': '**0.612745**',
    'G5_OPUS': '**0.649510**',
    'G5_QWEN': '**0.781863**',
    'G5_MEAN': '0.681373',
    'G5_VERDICT': '**PASS**（< 0.70）',
    'TRIAL_GPT': '`FIN3-WKN-149__qsFcMtD`',
    'TRIAL_OPUS': '`FIN3-WKN-149__vTPHQTW`',
    'TRIAL_QWEN': '`FIN3-WKN-149__uqNx7ti`',
    'G5_CONCLUSION': (
        '三模型均分 **0.681373 < 0.70**，门禁 **PASS**；三模型均有得分（最低 `gpt-5.6-sol` '
        '0.612745 > 0），非"全 0 死题"；四执行体 `criteria_counted` 均为 **36**、`verifier_error` 均为 **0**。'
        '对照 fix7 轮（GPT 0.572304 / Opus 0.296569 / Qwen 0.878676 / 均值 0.582516）：'
        '本轮 gpt +0.040、opus +0.353（fix7 轮 opus 曾因端点故障偏低）、qwen −0.097，'
        '均值 +0.099——上升主要来自 `N02` 误扣修正与四条 likert 锚点/互斥区间明确化后判官口径收敛。'),
    'DIFFICULTY_NOTE': (
        '按**本包实测均分 0.681373** 落档：档位区间 `A1 ∈ [0.60, 0.70)` / `A2 ∈ [0.50, 0.60)` / '
        '`A3 < 0.50`，均分落 **A1**，故 `task.toml` 的 `keywords` / `metadata.difficulty` / `tags` '
        '三处已由 **A2 同步改为 A1**（包内 `"A2"` 残留 0 处，`task.zip` 已随之重建）。'
        '⚠️ **据实提示越档风险**：本均分距 0.70 门禁线仅 **1.9pp**，而判官为 LLM 逐条采样、'
        '同一批交付物两轮判分均分可差约 ±0.04——**重跑判官存在越线（>0.70）或越档至 A2 的风险**，'
        '此处按规范如实披露，未做任何择优选报。'),
    'COMMON_ZERO': '`R06`(3) / `R07`(3) / `R13`(7) / `R14`(7) / `R15`(7) / `R31`(7)，权重和 **34.0**',
    'SZ_BATCH': f'{SZ_FILE.stat().st_size:,}' if SZ_FILE.exists() else '（打包后回填）',
})

TEXT_FIX = [
    ('| FIN3-WKN-149 | `FIN3-WKN-149/` | A2 | C5 |',
     '| FIN3-WKN-149 | `FIN3-WKN-149/` | A1 | C5 |'),
    ('| `claude-opus-4-8` | `4router.net` | 原 `api.ebondai.com` 端点本轮返回 `INSUFFICIENT_BALANCE`（余额不足），改用 4router 网关；**响应体 `model` 字段经探测确认为 `claude-opus-4-8` 本体**（非模型替换） |',
     '| `claude-opus-4-8` | `https://4router.net` | 端点择优实测选定：`api.ebondai.com` 返回 HTTP 401 `INVALID_API_KEY`、'
     '`fanrenapi.com` 返回 HTTP 503 `model_not_found`（该分组无 opus 通道）、aliyun MaaS 返回 HTTP 400 `Model not exist`，'
     '**仅 4router 握手成功**且**响应体 `model` 字段经探测确认为 `claude-opus-4-8` 本体**（非模型替换）。'
     '本轮该执行体**一次跑通**（`num_turns=66`、`is_error=false`、23.8 min），无中断重试 |'),
    ('4. **无 `_prev` 冗余**：本轮不再携带历史轮次副本目录（fix7 包内的 `_prev/`、`summary_prev.json` 已移除），历史轮次仅在 `summary.json` 的 `invalid_runs` 中原样留证。',
     '4. **无 `_prev` 冗余**：本轮不再携带历史轮次副本目录（fix7 包内的 `_prev/`、`summary_prev.json` 已移除）；'
     '同执行体未采用的试次仅在 `summary.json` 的 `notes` 中记录试次号，**其产物与轨迹均不入包**（采用轮轨迹完整保留）。'),
    ('*文档生成：2026-10-09（FIN3-WKN-149 二次返修重交版 **1.0.8**，批次 `work_fin-b01_20261009_fix8-149`）；验证环境：WSL Ubuntu + Docker Engine 29.x。*',
     '*文档生成：2026-10-09；四执行体跑分与归档完成：2026-10-10（FIN3-WKN-149 二次返修重交版 **1.0.8**，'
     '批次 `work_fin-b01_20261009_fix8-149`）；验证环境：WSL Ubuntu + Docker Engine 29.x。*'),
]

raw = DOC.read_bytes()
t = raw.decode('utf-8')
crlf = '\r\n' in t

n_slot = 0
for k, v in SLOTS.items():
    a = '{{' + k + '}}'
    c = t.count(a)
    if c == 0:
        print(f'  [WARN] 占位符未找到: {a}')
    t = t.replace(a, v)
    n_slot += c

n_fix = 0
for a, b in TEXT_FIX:
    c = t.count(a)
    if c != 1:
        print(f'  [WARN] 正文替换期望 1 处、实际 {c} 处: {a[:50]}...')
    t = t.replace(a, b)
    n_fix += c

left = [x for x in t.split('{{') if '}}' in x]
DOC.write_bytes(t.encode('utf-8'))
print(f'[OK] 占位符替换 {n_slot} 处；正文替换 {n_fix} 处；行尾={"CRLF" if crlf else "LF"}')
print(f'[OK] 剩余未填占位符: {[x.split("}}")[0] + "}}" for x in left] or "无"}')
print(f'[OK] 文档大小: {len(t.encode("utf-8")):,} B')
