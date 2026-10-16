# 飞书交付附件 vs 本地题包：一致性核对 + QC 自检结论（2026-10-16）

> 检查性质：**只读检查**。未修改任何题包、未改动飞书记录、未重新上传附件。
> QC 自检调用的是甲方 `windows-harbor-qc` 的原始入口 `scripts/run_delivery_qc.py`（真实 Harbor Oracle×3 + NOP×3 + 十四项人工复核）。

## 一、检查范围与口径

| 项 | 取值 |
|---|---|
| 飞书来源 | base `EsJebL8JJaf7g4sIbItcnMFgnvg` / table `tblRDxcGkblflMBA`（harbor-windows 作业表） |
| 拉取时刻 | 2026-10-16 09:21（`rev=4078`，`records_count=5`，`has_more=false`） |
| 判定字段 | 只认交付附件字段 **`作业压缩包`**（README 铁律四第 6 条：`zhang质检`/`分数截图`/`oracle-nop截图` 属过程证据，不参与一致性判定） |
| 比对方法 | 下载附件 → ZIP 内唯一根目录名核对 → 解压后**逐文件 SHA256** 与本地 `harbor-windows/<附件名去 .zip>/` 比对 |
| QC 口径 | 交付目录 + 四模型门禁 + 四模型原始 jobs + Oracle/NOP 真实运行 + 十四项人工质量硬门禁 |

飞书当前 5 条记录**状态全部为「待返修」**，返修原因均为同一镜像硬项：`environment/Dockerfile` 运行层使用
`mcr.microsoft.com/windows/servercore:ltsc2022@sha256:76cf422c…`（Server Core 被明令禁止）。

## 二、一致性核对结论（飞书附件 vs 本地目录）

| 飞书交付附件 | 飞书记录状态 | ZIP/本地文件数 | 逐文件比对 | 结论 |
|---|---|---|---|---|
| `wfflab__wsparse-215-v1.0.0-delivery.zip` | 待返修 | 273 / 273 | 0 多 / 0 少 / 0 差异 | **一致** |
| `wfflab__wvas-216-v1.0.0-delivery.zip` | 待返修 | 259 / 261 | 0 多 / **本地多 2** / 0 差异 | **不一致** |
| `wfflab__wspawn-218-v1.0.0-delivery.zip` | 待返修 | 261 / 261 | 0 多 / 0 少 / **2 个同名文件内容不同** | **不一致** |
| `wfflab__wcancel-219-v1.0.0-delivery.zip` | 待返修 | 260 / 260 | 0 多 / 0 少 / 0 差异 | **一致** |
| `wfflab__wciocp-220-v1.0.0-delivery.zip` | 待返修 | 258 / 258 | 0 多 / 0 少 / 0 差异 | **一致** |

附件 SHA256（本次下载副本）：215 `a83f3622…`、216 `edea432c…`、218 `68c34d4c…`、219 `0ebe199e…`、220 `d637d595…`。
5 个 ZIP 的根目录名均与「附件名去 `.zip`」逐字一致。

### 差异明细

- **wvas-216**：本地比飞书附件多 2 个文件 —— `REFIT-2026-10-14.md`、`verifier/WINDOWS_VALUE.md`。
  这两个文件参与包身份计算：本地包 `harbor_task_checksum=253161fb…`，飞书附件版为 `80ae0a3d…`。
- **wspawn-218**：`environment/Dockerfile` 与 `task.toml` 内容不同 ——
  - 飞书附件版：`FROM mcr.microsoft.com/windows/servercore:ltsc2022@sha256:76cf422c…`，
    `task.toml` 的 `docker_image` 也 pin 到该 Server Core 摘要；
  - 本地版：`FROM mcr.microsoft.com/windows/server:ltsc2022`（完整 Windows Server 2022），
    `task.toml` 的 `docker_image` 指向成品镜像 `ghcr.io/wzswffhm/wfflab-windows:wspawn-218-1.0.0`。
  - 即本地已完成镜像合规改造，但**该改造尚未上传飞书**。

### 附件上传时间（取自飞书 Base 记录变更历史）

飞书附件对象本身只暴露 `file_token/name/size`，没有上传时间字段；下表时间来自
`base +record-history-list` 中「作业压缩包」字段的变更时间（即该附件写入记录的时点，北京时间）。

| 题包 | 当前在架附件（size） | **上传时间** | 记录 rev | 上传后是否再变动 |
|---|---|---|---|---|
| wsparse-215 | `wfflab__wsparse-215-v1.0.0-delivery.zip`（54,423,465） | **2026-10-16 07:59:54** | 4056 | 至 10-16 09:21 拉取时未再变动 |
| wvas-216 | `wfflab__wvas-216-v1.0.0-delivery.zip`（54,420,063） | **2026-10-16 08:00:43** | 4062 | 未再变动 |
| wspawn-218 | `wfflab__wspawn-218-v1.0.0-delivery.zip`（54,466,397） | **2026-10-14 19:02:26** | 3887 | 未再变动 |
| wcancel-219 | `wfflab__wcancel-219-v1.0.0-delivery.zip`（54,420,405） | **2026-10-16 08:01:16** | 4068 | 未再变动 |
| wciocp-220 | `wfflab__wciocp-220-v1.0.0-delivery.zip`（54,576,334） | **2026-10-16 08:01:51** | 4074 | 未再变动 |

即：**215 / 216 / 219 / 220 是 2026-10-16 早上 07:59–08:01 这一批集中重传的**（与
2026-10-16 08:02 的提交 `55f068ba`「215/216/219/220 四包重交付」时间吻合，上传略早于提交），
**218 停留在 2026-10-14 19:02 的旧版**（对应提交 `425315d8`「218 槽位交付完成…并上线飞书」）。

更早的上传/返修时间线（同一记录内被替换过的历史附件）：

| 题包 | 历史上架过的附件（时间） |
|---|---|
| wsparse-215 | `wfmt-215-v2.1.0`（10-13 20:45、10-13 22:40、10-14 16:27）→ 10-14 16:27 换成 `wsparse-215-v1.0.0` |
| wvas-216 | `wchunk-216-v1.2.0`（10-11 15:18，10-13 共 6 次替换）→ 10-14 17:44 换成 `wvas-216-v1.0.0` |
| wspawn-218 | `wlogseg-218-v1.0.0`（10-12 17:03、10-12 22:51）→ `wlogseg-218-v1.1.0`（10-13 23:32、10-13 23:33）→ 10-14 19:02 换成 `wspawn-218-v1.0.0` |
| wcancel-219 | `wpeimg-219-v1.4.0`（10-14 05:02）→ 10-14 22:30 换成 `wcancel-219-v1.0.0` |
| wciocp-220 | 仅 `wciocp-220-v1.0.0`（10-15 08:32，10-16 08:01 重传） |

状态侧时间线：5 条记录均在 **2026-10-15 13:36–13:37** 被置为「待返修」并一直保持至今
（返修原因即第一节所述的 Server Core 镜像硬项）。



- `wfflab__wtoken-221-v1.0.0-delivery`：飞书作业表**没有对应记录**（未提交），本地包内**缺 `jobs/`**；
  检查期间（09:2x 起）观察到 `_qc_runs/wtoken-build/run_wtoken_model_rounds.py` 正在跑 `model-qwen-2` 模型轮，属未完成状态。

## 三、QC 自检结论

### 3.1 本地当前内容（完整 QC 实跑）

| 包 | 交付目录 | 四模型门禁 | 四模型原始 jobs | Oracle/NOP（实跑） | 十四项人工复核 | **总结论** |
|---|---|---|---|---|---|---|
| wfflab__wsparse-215 | PASS | PASS | PASS | Oracle 3×`VALID/1`、NOP 3×`VALID/0` | PASS | **PASS** |
| wfflab__wvas-216 | PASS | PASS | PASS | Oracle 3×`VALID/1`、NOP 3×`VALID/0` | PASS | **PASS** |
| wfflab__wcancel-219 | PASS | PASS | PASS | Oracle 3×`VALID/1`、NOP 3×`VALID/0` | PASS | **PASS** |
| wfflab__wciocp-220 | PASS | PASS | PASS | Oracle 3×`VALID/1`、NOP 3×`VALID/0` | PASS | **PASS** |
| wfflab__wspawn-218 | PASS | PASS | **FAIL** | 未跑（前置门禁已失败） | 未提供 | **FAIL** |
| wfflab__wtoken-221 | **FAIL**（缺 `jobs/`） | — | — | — | — | **FAIL** |

218 的失败原因：`jobs/` 下 12 个原生 job 全部报
`was run against a different Task checksum` —— 包内 `environment/Dockerfile`、`task.toml` 已在
2026-10-16 08:02 改成完整镜像 + 成品镜像引用，但 `jobs/`（控制组 + 模型轮）仍是旧身份时代的产物，
未随新身份重跑（`jobs/ctl-oracle-*`、`jobs/model-*` 时间戳仍为 10-14 18:48）。

### 3.2 飞书附件本身能否通过 QC

| 飞书附件 | 静态门禁（实测） | 完整 QC | 判定 |
|---|---|---|---|
| wsparse-215 | 交付目录 ✔ / jobs ✔ / 模型门禁 ✔ | 与本地逐字节相同，本地完整 QC = PASS | **可通过** |
| wcancel-219 | 交付目录 ✔ / jobs ✔ / 模型门禁 ✔ | 同上 | **可通过** |
| wciocp-220 | 交付目录 ✔ / jobs ✔ / 模型门禁 ✔ | 同上 | **可通过** |
| wvas-216 | 交付目录 ✔ / **jobs ✘** / 模型门禁 ✔ | 实跑（含 Oracle/NOP）= **FAIL**，唯一失败项就是 jobs 身份不一致（12 个 job 的 `task_checksum=253161fb…` ≠ 附件包身份 `80ae0a3d…`） | **不可通过** |
| wspawn-218 | **交付目录 ✘** / jobs ✔ / 模型门禁 ✔ | 实跑 = **FAIL**，唯一实质错误仍是 `environment/Dockerfile:13` 的 Server Core 基础镜像（交付目录硬门禁） | **不可通过** |

- 216 的失败不是功能问题：该附件的 Oracle/NOP 实跑同样全部 `VALID`（Oracle 1/1/1、NOP 0/0/0），
  只是它上传的是**缺 `REFIT-2026-10-14.md` 与 `verifier/WINDOWS_VALUE.md` 的打包版本**，
  与包内 12 个 job 记录的 Task 身份对不上。
- 218 的失败是甲方明令的硬项：附件版仍是 Server Core 基础镜像（`Dockerfile:13`）。

### 3.3 与历史结论的差异说明

`_qc_runs/wcancel-build/qc/report.json`、`_qc_runs/wciocp-build/qc/report.json` 里各有一份 10-15 的 **PASS**
报告，但那是 Server Core 时代的包身份（219 `task_hash=d87e6766…`、220 `0443740b…`）；
当前包身份已变为 219 `919519bb…`、220 `55364aad…`，因此旧报告对当前内容**不再有效** ——
本次按当前内容重跑后才得到上表的 PASS。

## 四、结论

1. **一致性**：5 个飞书交付附件中，**215 / 219 / 220 与本地完全相同**；**216 缺 2 个文件**；
   **218 仍是 Server Core 旧版**（本地已改造但未上传）；**221 尚未在飞书建记录**。
2. **QC 自检**：本地 **215 / 216 / 219 / 220 四包在各自当前内容上完整 QC = PASS**
   （交付目录、四模型门禁、14 个原生 jobs、Oracle 3×1 / NOP 3×0、十四项人工复核全部通过）。
3. **飞书侧**：**215 / 219 / 220 三个附件可通过 QC 自检**（与本地同内容）；
   **216、218 两个附件不能通过**（216 为打包缺件导致 jobs 身份不一致；218 为 Server Core 硬项）。
4. **218 / 221 本地也尚未就绪**：218 需在新身份下重跑 12 轮 jobs；221 缺整套 `jobs/`（模型轮仍在跑）。
   以上仅为结论陈述，本次未做任何修改。

## 五、证据落点

- 报告（本文件）：[harbor-windows/_index/feishu-consistency-20261016.md](feishu-consistency-20261016.md)
- 一致性原始数据：[feishu-vs-local.json](../_qc_runs/feishu-consistency-20261016/feishu-vs-local.json)、
  [feishu-vs-local.md](../_qc_runs/feishu-consistency-20261016/feishu-vs-local.md)
- 飞书附件解压版静态门禁：[feishu-static-check.json](../_qc_runs/feishu-consistency-20261016/feishu-static-check.json)
- 本地四包完整 QC：`_qc_runs/feishu-consistency-20261016/qc-wsparse-215|qc-wvas-216|qc-wcancel-219-r2|qc-wciocp-220/`
- 飞书 216 附件版完整 QC（实测 FAIL）：`_qc_runs/feishu-consistency-20261016/qc-feishu-wvas-216/`
- 飞书 218 附件版完整 QC（实测 FAIL）：`_qc_runs/feishu-consistency-20261016/qc-feishu-wspawn-218/`
- 飞书本轮记录快照：`tblRDxcGkblflMBA_20261016_092147_829.ndjson`（rev 4078）
- 附件上传时间原始数据：`_qc_runs/feishu-consistency-20261016/feishu-upload-times.json`
  及各记录原文 `_qc_runs/feishu-consistency-20261016/history/<record_id>.json`
