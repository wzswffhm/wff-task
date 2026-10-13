# FIN3-WKN-153 飞书作业表回传记录（2026-10-12 建行 / 2026-10-13 补齐）

## 一、坐标与身份

| 项 | 值 |
|---|---|
| 表 | `https://vcnuhsx1gwu0.feishu.cn/wiki/S4dVwTGtviikDPkF0wycdMernKf?table=tblPNrBtjFfwOowN`（表名「RL&weakness作业表0929」） |
| `base_token` / `table_id` | `QpzNb4fXSamfX6sLloBcPfHNnug` / `tblPNrBtjFfwOowN`（2026-10-13 经 `base +url-resolve` 复核，与建行时一致） |
| 目标行 | `record_id = reczz28MYNlN7r8R` —— 全表 75 行中「标注人 = wff 且 状态 = 领取」**唯一**一行（2026-10-13 全表扫描确认） |
| 身份 | user = **wff**（`ou_35041bb28c45c5be1213b2b1af040d90`），token 有效 |
| 依据 | `skills/harbor-weakness/references/09-feishu-worksheet-delivery.md` |

## 二、已完成：该行终态（`rev = 700`）

| 字段 | field_id | 值 | 写入时间 |
|---|---|---|---|
| 题目 | `fld1bfmLqv` | 4,232 字题面（`instruction.md` 去 markdown 标记） | 2026-10-12 |
| 类型 | `fld6ND5UZL` | `weakness` | 2026-10-12 |
| 题目难度 | `fldYA4iRaD` | **`A1`**（三模型实测均分 0.675824 落 A1 区间） | 2026-10-12 |
| 标注人 | `fldgADMj3N` | **`wff`** | 2026-10-12 |
| **交付物** | `fld8TMUhqI` | `work_fin-b01_20261012-153.zip`（**4,132,173 B**，file_token `CEJjbY2JcodlaCxw8OEctCKlntH`） | **2026-10-13** |
| **题目附件信息** | `fldf8Ymaw2` | `FIN3-WKN-153_task.zip`（81,276 B，file_token `RMzrbbl9boC9QdxBVVEcRaxGnbe`） | **2026-10-13** |
| **标准答案附件信息** | `fld2TmGhqt` | `FIN3-WKN-153_answer.zip`（240,798 B，file_token `Avx6brAjZoxSShxazdmcM2Alnle`） | **2026-10-13** |
| **考点信息（rubrics）** | `fldqj9Zstn` | 7,974 字 / 34 条判据（由 `tests/rubrics.toml` 生成） | **2026-10-13** |
| **参考答案** | `fld2LBu2Ns` | 1,107 字结论摘要（口径与金标一致，含 12.01% 修正值） | **2026-10-13** |
| 状态 | `fldKFzG0cA` | `领取`（甲方侧流转，本人未写） | — |
| 序号 / 原工作表 / 质检报告 / 做答思路 | `fld5kMM38p` / `fld1qchbC1` / `fld92VdQU6` / `fld6ae02rH` | 留空（序号由甲方分配；其余非标注人职责或不可写） | — |

## 三、回验（2026-10-13）

1. **附件可用性**：`+record-download-attachment` 把三个附件取回本地，与 `_qc_runs/packages/` 下的交付包
   **SHA-256 逐字节一致**（4,132,173 / 81,276 / 240,798 B），排除 `file_token` 失效、同名替换、上传截断等问题；
2. **字段落库**：`+record-get` 回读 5 个新增字段均有值，`rev` 由 696 → **700**；
3. **目标行唯一性**：`+record-list` 全表 75 行扫描，`标注人 = wff 且 状态 = 领取` 仅 `reczz28MYNlN7r8R` 一行，
   不存在误写他行的风险。

## 四、脚本（已执行，可重放）

```bash
PY=C:\Users\Administrator\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe
$PY harbor-weakness\_qc_runs\tools\feishu_153_upsert.py attach reczz28MYNlN7r8R   # 3 个附件（2026-10-13 已成功）
$PY harbor-weakness\_qc_runs\tools\feishu_153_fill.py   reczz28MYNlN7r8R          # 考点信息 + 参考答案（2026-10-13 已成功）
$PY harbor-weakness\_qc_runs\tools\feishu_153_upsert.py get reczz28MYNlN7r8R      # 复核终态
```

- 为什么用 Python（而非 PowerShell 直接调）调 lark-cli：题面是 10 KB 中文长文本，经 Windows 命令行 → `.ps1` shim 会破坏编码（09 文档 §2 警告）；Python `subprocess` 走 `CreateProcessW`（UTF-16），中文与长参数均安全。
- **路径白名单**：lark-cli 的 `--file` / `--output` 只接受**当前目录下的相对路径**（`unsafe output path` 校验）。
  附件上传前先复制到 `%TEMP%\lark153` 并以该目录为 cwd；下载同理，以目标目录为 cwd 传 `--output .`。
- 上传前表快照：`_qc_runs/feishu_153_before.json`（`+record-list` 原始输出，74 行 / 996 KB，**含他人题目内容，不入库**）。

## 五、2026-10-12 权限阻塞诊断（已于 2026-10-13 解除）

当时 5 个字段写入全部返回 `permission_denied`（`code 800020812`，`user lacks permission for the requested resource`）。
已排除的假设：① 路径白名单（已在合法 cwd 下执行）；② 附件字段专属（长文本同样被拒）；③ 权限同步延迟（延迟 20 s 重试仍失败）；
④ `--as bot` 不可用（`app_scope_not_applied`，缺 scope `base:field:read`，code 99991672）；⑤ `+record-history-list` 返回服务内部错误（code 1）。
→ 结论为「该账号对本表只有新增记录权限，没有编辑记录权限」。**2026-10-13 甲方开通后重放，全部一次通过。**

## 六、待办

1. 序号 `fld5kMM38p` 由甲方分配后回填（标注人不可写该列）；
2. 状态 / 质检报告由质检方流转，标注人不写（09 文档 §2 字段可写性表）；
3. 若后续还需补「做答思路」`fld6ae02rH`，该字段为可写 text，当前留空。
