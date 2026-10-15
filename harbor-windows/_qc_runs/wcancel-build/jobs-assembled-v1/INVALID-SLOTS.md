# 无效槽位记录 — wfflab__wcancel-219

> 依据：`references/11-latest-qc-requirements.md` §2「API 失败必须单列无效槽位，不得计入能力分」
> 冻结身份：`harbor_task_checksum = 69d80a258ea2e0642f95a4d0cfeb5f7d4a357fee75f8b5a2322fd62b590d9e28`

## 结论

12 个计划槽位中，**11 个有效、1 个无效**：

| 槽位 | 结果 | 判定 |
|---|---|---|
| `ctl-oracle-1/2/3` | 1 / 1 / 1 | VALID |
| `ctl-nop-1/2/3` | 0 / 0 / 0 | VALID |
| `model-qwen-1/2/3` | 0 / 1 / 0 | VALID |
| `model-opus-1/2` | 1 / 1 | VALID |
| **`model-opus-3`** | **无正式分** | **INVALID（提供商配额故障）** |

## 无效槽位详情

- 计划槽位：`model-opus-3`（同 alias `opus`、同计划顺序、每槽位一轮）
- 原始轮 trial：`wfflab__wcancel-219-v1.0.0-deliv__Ano6iPA`，耗时 54 秒
- 终止原因：`RuntimeError: http_403`，提供商原文
  `预扣费额度失败, 用户剩余额度: ¥0.075214, 需要预扣费额度: ¥0.094598 (request id: 20261014140026489040224k20DrA2G)`
- 判据命中（三条同时成立）：
  1. 该轮 `agent_result` 为空，从未进入 `completed`；
  2. 错误文本是**提供商侧的配额故障**（HTTP 403 / 预扣费额度不足）；
  3. `verifier_result: null` —— 验证器从未在候选修订上运行。
- 替代轮：`replacement-1` 于 22:01:40 绑定同一槽位重跑，端点余额仍未恢复，8 秒后再次 403，同样记 INVALID。
- 归档纪律：原始 `exception.txt` / `trial.log` / `result.json` **逐字节未改**；无效性只在本注解层表达。

## 影响与阻塞

- `validate_model_gate.py` 的 `REQUIRED_COUNTS = {"qwen":3,"opus":3}` 要求 Opus 有 3 次**有效**运行；当前仅 2 次有效，**交付门禁在此项阻塞**。
- 区分度本身在已有有效轮上成立：`sum(opus)=2 > sum(qwen)=1`，且 Opus 的 testcase 累计通过数亦高于 Qwen。
- 解除条件：为 Opus 端点充值，或提供另一条可用凭据/端点，然后补跑 `model-opus-3` 一轮。

## 复现命令

```powershell
$env:PYTHONIOENCODING='utf-8'; $env:no_proxy='*'
& $py harbor-windows\_qc_runs\wcancel-build\run_wcancel_model_rounds.py --only opus --index 3 --max-steps 40
```

（`--index` 支持补跑单个计划槽位，并把替代轮**合并**进 `rounds_summary.json`，不覆盖其它轮次。）
