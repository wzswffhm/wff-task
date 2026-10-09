# wfflab__wchunk-216 交付包（v1.1.0）

- 交付日期：2026-10-10
- 题包：`harbor-windows/wfflab__wchunk-216`，`task_version = 1.1.0`
- `task_hash = 72ea01be25b665bfe548f71e0f57599a44fc86aaa19475227471667f910a0afb`
- 驱动口径：甲方质检包 `windows-harbor-qc`（`harbor-windows/_reference/`）
- 执行环境：Windows 宿主机 + Docker Desktop **Windows 容器模式** + Harbor CLI 0.22.0
- 资格 epoch：`2026-10-09T22:00:00+08:00`（v1.1.0 内容冻结之后；仅此后的轮次入正式集）

---

## 一、结论

**七项资格门禁全绿，甲方 QC 通过，可交付。**

| 门禁 | 读数 |
|---|---|
| `controls_passed` | ✅ true（no-change ×3 = 0、golden ×3 = 1） |
| `model_counts_complete` | ✅ true（QWEN 3/3、OPUS 3/3、GLM 1/1、KIMI 1/1） |
| `opus_sum_greater_than_qwen` | ✅ true（**2 > 0**） |
| `task_version_consistent` | ✅ true（全 1.1.0） |
| `epoch_pinned` | ✅ true |
| `agent_failures_excluded` | ✅ 0（无剔除轮，全部真实计分） |
| `qualified` | ✅ **true** |

模型得分：QWEN `[0,0,0]`=0 ｜ OPUS `[1,0,1]`=2 ｜ GLM `[0]`=0 ｜ KIMI `[0]`=0
（GLM / KIMI 按规范**只计有效场次、不参与区分度**。）

## 二、甲方 QC（对交付 ZIP 本体执行）

`run_qc.py --input wfflab__wchunk-216-v1.1.0-delivery.zip --attempts 3`

| 项 | 结果 |
|---|---|
| 静态结构 | ✅ PASS（errors 0、warnings 0） |
| Oracle ×3 | ✅ `VALID/1` ×3（18/18） |
| NOP ×3 | ✅ `VALID/0` ×3（10 F2P 全挂、P2P 8/8 全过） |
| 动态门禁 | ✅ PASS |
| 结论 | ✅ **PASS** |
| `input_sha256` | `d215e87f8039d0e7d4387400177f22f198c0b28bbfa65f56e23f45a9278e73f1` |

- **证据与交付物字节级绑定**：QC 的 `input_sha256` 与 `package/*.zip` 的 sha256 完全一致。
- ⚠️ QC 进程 `exit=1` 是甲方 `markdown_report` 的已知缺陷（`run_qc.py:427` 读 `task['static']`，
  实际字段平铺 → `KeyError`），`report.json` 在崩溃前已落盘，**结论 PASS 有效**（2026-10-08 已向甲方报备）。

## 三、交付物

| 文件 | 大小 | SHA256 |
|---|---|---|
| `package/wfflab__wchunk-216-v1.1.0-delivery.zip` | 121,982 B | `d215e87f8039d0e7d4387400177f22f198c0b28bbfa65f56e23f45a9278e73f1` |
| `package/wfflab__wchunk-216-v1.1.0.zip` | 118,672 B | `344d29c448319e4fa2e3b57ad0d6dc8e05a6baedbbb73bbb2fa486435f2f7ce2` |

- delivery.zip 平台布局：`outside_harbor/` + `outside_harbor-assets/` + `jobs/`（136 条目）
- package.zip 题包布局：`<task-id>/**`（130 条目），含甲方 QC 必备件
  （`source.json` / `solution/README.md` / `solution/solve.ps1|bat` / `tests/required_testcases.json`）
- 两包均**无** `extras/`、`__pycache__/`、`*.pyc` 泄漏

## 四、`jobs/` 构成（20 作业 + `_index`）

| 类别 | 数量 | 结果 |
|---|---|---|
| 控制组 no-change / golden | 3 + 3 | verdict 0 / 1，全 VALID |
| 模型轮 QWEN / OPUS / GLM / KIMI | 3 + 3 + 1 + 1 | 全 VALID，零剔除 |
| Harbor 实跑 golden-oracle / no-change-nop | 3 + 3 | verdict 1 / 0，全 VALID |

Harbor 6 轮由 `produce_jobs.py` 实跑写入（`source.runner = 0.22.0`），
`jobs/_index/qualification_summary.json` 为权威读数。

## 五、本轮题包改动（v1.0.1 → v1.1.0）

1. **去答案/去引导 10 处**：候选实现 5 个 docstring 里的「草稿 vs 真实差异清单」、
   `README.md` 的「判官如何验收」6 条、`FORMAT.md` changelog 的点名括注、
   `instruction.md` 现象 4 与 C 条的提示清单 —— 全部对齐 `wfflab__wfmt-215` 的中性基准。
2. **打 Qwen 弱点**：候选 `unpack` 不再自带 CRC 校验（复刻 215 失败机制，
   逼模型自行补校验、暴露其「先 CRC 后结构」的顺序错误）。
3. **Dockerfile 修 `import wfmt` → `import wchunk`**（v1.0.1 修复，镜像可构建）。

弱点验证：差分测试（`_qc_runs/tools/diff216_one.py`）显示 QWEN 三场全 0，
2 场挂 `truncated-container`（把截断误判为 `checksum`）、1 场样本逆向失手 —— 与 215 形态同构。

## 六、证据

- `evidence/qc-216d/`：QC `report.json` / `inventory.json` / `runs.json` /
  `commands.json` / `preflight.json` + 6 份 Harbor CLI 原始日志
- `evidence/images/score_summary.png`：模型评分与门禁读数
- `evidence/images/oracle_nop_controls.png`：控制组 3+3 读数
- 权威汇总：`harbor-windows/wfflab__wchunk-216/jobs/_index/qualification_summary.json`

## 七、复现

```powershell
$env:DOCKER_CONTEXT = 'desktop-windows'
# 甲方 QC（对交付 ZIP）
python harbor-windows\_reference\windows-harbor-qc\scripts\run_qc.py --input <delivery.zip> --out <空目录> --attempts 3
# 资格汇总
python <generate-win>\scripts\summarize_model_runs.py --workspace-root <runner> --task-id wfflab__wchunk-216 --after '2026-10-09T22:00:00+08:00' --control-runs 3 --output <out.json>
```

> **注意**：`tree_hash` 不排除 `__pycache__`。本地 import 题包会留下 `.pyc` 并使 hash 漂移，
> 打包前必须清掉任务目录内的 `__pycache__`（本轮已清，60 → 40 文件）。
