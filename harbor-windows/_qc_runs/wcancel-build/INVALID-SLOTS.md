# 无效槽位记录 — wfflab__wcancel-219

> 依据：`references/11-latest-qc-requirements.md` §2「API 失败必须单列无效槽位，不得计入能力分」
> 冻结身份：`harbor_task_checksum = 69d80a258ea2e0642f95a4d0cfeb5f7d4a357fee75f8b5a2322fd62b590d9e28`

## 最终结论

**12 个计划槽位全部有效**，2 次无效尝试均已通过替代轮解决：

| 槽位 | 结果 | 判定 |
|---|---|---|
| `ctl-oracle-1/2/3` | 1 / 1 / 1 | VALID |
| `ctl-nop-1/2/3` | 0 / 0 / 0 | VALID |
| `model-qwen-1/2/3` | 0 / 1 / 0 （总分 1） | VALID |
| `model-opus-1/2/3` | 1 / 1 / 1 （总分 3） | VALID |

区分度：`sum(opus)=3 > sum(qwen)=1`，testcase 累计亦为 Opus 更多 ⇒ 成立。

## 无效尝试明细（`model-opus-3` 槽位）

| 尝试 | trial | 耗时 | 判定 | 原因 |
|---|---|---|---|---|
| `original` | `…__Ano6iPA` | 54 s | INVALID | `http_403` 提供商配额故障：`预扣费额度失败, 用户剩余额度: ¥0.075214, 需要预扣费额度: ¥0.094598`（request id `20261014140026489040224k20DrA2G`）；`agent_result` 空、`verifier_result: null` |
| `replacement-1-stale-trial` | 同名 `Ano6iPA` | 8 s | INVALID | 旧失败 job 目录未清除，**Harbor 复用了同名 trial**（request id 与原始轮逐字相同），并未真正发起新调用 |
| `replacement-2-fresh-trial` | `…__rGGyKrh` | 1131 s | **VALID** | 归档旧失败 job 后以新 trial 重跑；端点返回 HTTP 200，该轮得分 **1** |

### 判据命中（原始轮）

1. 该轮 `agent_result` 为空，从未进入 `completed`；
2. 错误文本是**提供商侧的配额故障**（HTTP 403 / 预扣费额度不足）；
3. `verifier_result: null` —— 验证器从未在候选修订上运行。

### 归档与公平性

- 原始失败证据（`exception.txt` / `trial.log` / `result.json`）逐字节保留，整体移入
  `_qc_runs/wcancel-build/invalid-slots-archive/model-opus-3-attempt-original/`；
  无效性只在**本注解层**表达，不改写任何已归档结果。
- 替代轮**绑定同一计划槽位**（同 alias `opus`、同计划顺序、每槽位一轮），Opus 未获得任何额外加权；
  最终统计只使用每个槽位**一次**有效运行。

## 复现命令

```powershell
$env:PYTHONIOENCODING='utf-8'; $env:no_proxy='*'
# 若旧失败 job 仍存在，先归档（否则 Harbor 会复用同名 trial）
Move-Item harbor-windows\_qc_runs\wcancel-build\model-rounds\jobs\model-opus-3 `
          harbor-windows\_qc_runs\wcancel-build\invalid-slots-archive\model-opus-3-attempt-original
& $py harbor-windows\_qc_runs\wcancel-build\run_wcancel_model_rounds.py --only opus --index 3 --max-steps 40
```

（`--index` 补跑单个计划槽位，并把替代轮**合并**进 `rounds_summary.json`，不覆盖其它轮次。）
