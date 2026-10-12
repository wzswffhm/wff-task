# FIN3-WKN-153 飞书作业表回传记录（2026-10-12）

## 一、坐标与身份

| 项 | 值 |
|---|---|
| 表 | `https://vcnuhsx1gwu0.feishu.cn/wiki/S4dVwTGtviikDPkF0wycdMernKf?table=tblPNrBtjFfwOowN` |
| `base_token` / `table_id` | `QpzNb4fXSamfX6sLloBcPfHNnug` / `tblPNrBtjFfwOowN` |
| 身份 | user = **wff**（`ou_f4e4bc01ed9be1ef4cbaedcdf8f19d45`），token 有效 |
| 依据 | `skills/harbor-weakness/references/09-feishu-worksheet-delivery.md` |

## 二、已完成：新增一行

- **`record_id = reczz28MYNlN7r8R`**（`+record-upsert` 新建，2026-10-12 23:46；rev 由 693 → 694）
- 已成功写入的字段：

| 字段 | field_id | 值 |
|---|---|---|
| 题目 | `fld1bfmLqv` | FIN3-WKN-153 完整题面（`instruction.md` 去 markdown 标记，129 行原文） |
| 类型 | `fld6ND5UZL` | `weakness` |
| 题目难度 | `fldYA4iRaD` | **`A1`**（三模型实测均分 0.675824 落 A1 区间） |
| 标注人 | `fldgADMj3N` | **`wff`**（`ou_f4e4bc01ed9be1ef4cbaedcdf8f19d45`） |

- **序号 `fld5kMM38p` 不可写**（09 文档 §3 铁律 4），新行该列留空，待甲方分配。

## 三、未完成：附件与两个长文本（权限阻塞，非脚本问题）

以下写入**全部**返回 `permission_denied`（`code 800020812`，`user lacks permission for the requested resource`）：

| 目标字段 | field_id | 待写内容 |
|---|---|---|
| 交付物 | `fld8TMUhqI` | `work_fin-b01_20261012-153.zip`（4,126,193 B） |
| 题目附件信息 | `fldf8Ymaw2` | `FIN3-WKN-153_task.zip`（81,276 B） |
| 标准答案附件信息 | `fld2TmGhqt` | `FIN3-WKN-153_answer.zip`（240,798 B） |
| 考点信息（rubrics） | `fldqj9Zstn` | 34 条判据摘要（7,974 字，由 `rubrics.toml` 生成） |
| 参考答案 | `fld2LBu2Ns` | 结论摘要（1,107 字） |

**诊断过程（已排除的假设）**：

1. 路径白名单不是原因 —— 附件已复制到 `%TEMP%\lark153` 并在该 cwd 下上传（否则会报 `unsafe file path`）；
2. 不是「附件字段专属」—— **长文本字段（考点信息/参考答案）同样被拒**；
3. 不是权限同步延迟 —— 建行 2 分钟后延迟 20 s 重试仍失败；
4. `--as bot` 不可用 —— `app_scope_not_applied`，缺 scope `base:field:read`（code 99991672）；
5. `+record-history-list` 查询 149 行返回服务内部错误（code 1），无法据此溯源。

→ 结论：**该账号对本表当前只有「新增记录」权限，没有「编辑记录」权限**。同表 149 / 239 / 267 / 282 行的附件是早前权限尚可时上传的（09 文档记录的 `file_token` 重签、同名替换等踩坑即当时留下）。

## 四、脚本已就绪（权限到位后可一键重放）

```bash
PY=C:\Users\Administrator\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe
$PY harbor-weakness\_qc_runs\tools\feishu_153_upsert.py attach reczz28MYNlN7r8R   # 3 个附件
$PY harbor-weakness\_qc_runs\tools\feishu_153_fill.py   reczz28MYNlN7r8R          # 考点信息 + 参考答案
$PY harbor-weakness\_qc_runs\tools\feishu_153_upsert.py get reczz28MYNlN7r8R      # 复核终态（逐字段）
```

- 为什么用 Python（而非 PowerShell 直接调）调 lark-cli：题面是 10 KB 中文长文本，经 Windows 命令行 → `.ps1` shim 会破坏编码（09 文档 §2 警告）；Python `subprocess` 走 `CreateProcessW`（UTF-16），中文与长参数均安全。
- 上传前表快照：`_qc_runs/feishu_153_before.json`（`+record-list` 原始输出，74 行 / 996 KB，**含他人题目内容，不入库**）。
- 本地三个附件副本：`_qc_runs/packages/`（`work_fin-b01_20261012-153.zip`、`FIN3-WKN-153_task.zip`、`FIN3-WKN-153_answer.zip`）。

## 五、待办

1. 请甲方为 `wff` 开通该表**编辑记录**权限（或加为协作者），随后重放 §4 的两条写入命令；
2. 序号由甲方分配后回填；
3. 状态 / 质检报告由质检方流转，标注人不写（09 文档 §2 字段可写性表）。
