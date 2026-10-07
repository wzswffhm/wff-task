# 09 · 飞书作业表交付物回传（实际操作）

> 本文件记录 **甲方「作业表」的领取与回传操作**，属工程操作说明，**不是**生产规范。
> 生产规范见 `references/01–08` 与 `delivery/00–08`。

## 1. 作业表坐标

| 项 | 值 |
|---|---|
| 表 URL | `https://vcnuhsx1gwu0.feishu.cn/wiki/S4dVwTGtviikDPkF0wycdMernKf?table=tblPNrBtjFfwOowN` |
| `base_token` | `QpzNb4fXSamfX6sLloBcPfHNnug` |
| `table_id` | `tblPNrBtjFfwOowN` |

解析任意表 URL：`lark-cli base +url-resolve --url "<url>" --as user`（返回 `base_token`）。

## 2. 字段 id（**一律用 id，不要用中文名**）

| `field_id` | 名称 | 类型 | 回传时填 |
|---|---|---|---|
| `fld5kMM38p` | 序号 | number | — |
| `fld1bfmLqv` | 题目 | text | 甲方已给 |
| `fld1qchbC1` | 原工作表 | text | 甲方已给 |
| `fldgADMj3N` | 标注人 | user | 认领时填自己（`wff`） |
| `fldYA4iRaD` | 题目难度 | select | **`A1` / `A2` / `A3`**（按 G5 均分落区） |
| `fld6ND5UZL` | 类型 | select | `weakness` / `RL` |
| `fld8TMUhqI` | **交付物** | **attachment** | **批次 zip** |
| `fld2LBu2Ns` | 参考答案 | text | 考点清单 |
| `fldqj9Zstn` | 考点信息（rubrics） | text | — |
| `fld6ae02rH` | 做答思路 | text | 可选 |
| `fld92VdQU6` | **质检报告** | **attachment** | 质检方上传（质检清单 xlsx），标注人只读 |
| `fldKFzG0cA` | **状态** | select | 领取 / 质检 / 同步 / 一审不通过 / 通过（质检方流转） |
| `fldf8Ymaw2` | 题目附件信息 | attachment | 题目 task.zip |
| `fld2TmGhqt` | 标准答案附件信息 | attachment | 标准答案 answer.zip |

> ⚠️ **字段可写性（2026-10-05 实测更正）**：旧版本文档称「参考答案」「考点信息」为只读，**实测不成立**。
> 标注人账号 `wff` 的实际权限如下（同表内逐字段探测，非猜测）：
>
> | 可写 ✅ | 不可写 ❌（`permission_denied` 800020812） |
> |---|---|
> | 题目 `fld1bfmLqv`、类型 `fld6ND5UZL`、题目难度 `fldYA4iRaD`、标注人 `fldgADMj3N`、考点信息 `fldqj9Zstn`、参考答案 `fld2LBu2Ns`、做答思路 `fld6ae02rH` | **序号 `fld5kMM38p`**、**原工作表 `fld1qchbC1`**、**状态 `fldKFzG0cA`**、质检报告 `fld92VdQU6`（附件字段） |
>
> 即：**序号 / 原工作表 由甲方分配（标注人不可写）**，状态 / 质检报告由质检方流转。附件字段一律走 `+record-upload-attachment`。

> ⚠️ **中文参数经命令行会被破坏编码**（`--keyword "中文"`、`--search-field 题目` 均会失败）。
> 改用 `field_id`，或把参数写进脚本/Python 文件再执行。

## 3. 命令（全部前置 `export LARK_CLI_NO_PROXY=1`，并带 `--as user`）

> **lark-cli 实际位置**（不在 PATH，需用绝对路径或 export）：
> `E:\nvm\v24.3.0\node_modules\@larksuite\cli\bin\lark-cli.exe`（Windows 全局安装）。
> 旧 shim `cli-connector-packages` 已不存在。auth 配置 `~/.lark-cli/config.json`（appId `cli_aa0b761941b8dd14`，身份 wff）。

```bash
# 鉴权（身份 = wff，token 自动刷新）
lark-cli auth status --json

# 读字段定义 / 找自己认领的行
lark-cli base +field-list  --base-token <bt> --table-id <tid> --as user --format json
lark-cli base +record-list --base-token <bt> --table-id <tid> --page-size 100 --as user --format json

# 读取单行 / 变更溯源（who·when，epoch 秒）
lark-cli base +record-get           --base-token <bt> --table-id <tid> --record-id <rid> --as user --format json
lark-cli base +record-history-list  --base-token <bt> --table-id <tid> --record-id <rid> --as user --format json

# 上传交付物（默认**追加**语义；`record-get` 返回的即为上传后的单元格内容）
lark-cli base +record-upload-attachment --base-token <bt> --table-id <tid> \
  --record-id <rid> --field-id fld8TMUhqI --file <batch>.zip --as user --format json
```

> ⚠️ **`--file` 有路径白名单**（lark-cli 高版本新增，低版本无）：只允许
> **当前工作目录（cwd）**、**账户临时目录**（`%TEMP%` / `$TMPDIR`）、**账户 home 下的 `files/`**。
> 传仓库里（如 `Desktop\wff-task\...`）的 zip 会直接报
> `unsafe file path: ... is outside the built-in allowlist`（rc=2，**字段保持空**，不会部分写入）。
> **对策**：先把 zip `cp` 到临时目录（或进程 cwd）再传；`+record-upsert --json` 不受此限制。
> ⚠️ 移附件的 `--yes` 是 high-risk-write；上传命令 rc=0 才代表成功，须逐条看 rc。

```bash

# 移除旧附件（high-risk-write，须 --yes）
lark-cli base +record-remove-attachment --base-token <bt> --table-id <tid> \
  --record-id <rid> --field-id fld8TMUhqI --file-token <token> --as user --yes

# 下载核对（read）
lark-cli base +record-download-attachment --base-token <bt> --table-id <tid> \
  --record-id <rid> --file-token <token> --output <dir>/ --overwrite
```

### 3.1 新建行（当表中无对应行时）

`+record-upsert` **不带 `--record-id` 即新建**（本表无 `+record-create`）：

```bash
lark-cli base +record-upsert --base-token <bt> --table-id <tid> \
  --json '{"fld1bfmLqv":"<题目>","fld6ND5UZL":["weakness"],"fldYA4iRaD":["A1"],"fldgADMj3N":[{"id":"ou_..."}]}' \
  --as user --format json
```

建行后**再分开写长文本字段**（考点信息 / 参考答案）与上传附件（附件不能作 CellValue）。

**必守铁律（本轮踩坑）**：

1. **建行本身允许**，但 payload **含任一不可写字段（序号 / 原工作表 / 状态）即整条失败**（原子，不部分写入）。
2. **探测字段可写性绝不能用「新建」试探** —— 一次 `--json '{"fld1bfmLqv":"探测"}'` 会**真实建行**；
   而 `+record-delete` 同为 `permission_denied`，**误建行无法自行删除**，只能：
   （a）用 `+record-upsert --record-id` 把它**改造成正式行**（推荐，无副作用）；或（b）请甲方删除。
   **正确做法**：拿一条**已存在的自有行**做 `--record-id` 更新探测。
3. **机器人身份不可用于建行**：`--as bot` 报 `app_scope_not_applied`，缺 scope `base:record:create`（code 99991672）。
4. **序号 / 原工作表 不可写** → 新建行这两列只能留空，交甲方分配；须在交付文档/记录中如实说明。

## 4. 安全顺序（务必遵守）

1. **默认「先传新附件，再移除旧附件」** —— 若反序，单元格会瞬时为空；上传中途失败即丢交付物。
   - **同名替换的例外**：若新旧附件**文件名相同**（如 `FIN3-WKN-149_task.zip`、`FIN3-WKN-149_answer.zip` 只改内容不改名），先传新会得到**两条同名记录**，只能靠 `file_token` 区分、极易删错；此时应 **先删旧、再传新**（删后字段为空属预期中间态，须立即上传并逐条核对 rc，失败即刻重传）。
   - 实操：先 `+record-get` 记下各字段的 `file_token` 与 `size`，删/传后 `+record-get` 用 `size` 字段二次确认落到的是新包。
1b. ⚠️ **`file_token` 会被重新签发（本轮 149 fix6 实测踩坑）**：往某附件字段 `+record-upload-attachment` 后，该字段内**既有的**附件 token 可能被静默重签 —— **同一文件、同 `size`，token 却变了**。此时用上传前抓到的旧 token 去 `+record-remove-attachment`，**rc=0 但实际是 no-op**（未删），字段残留**两条同名附件**。
   - **对策（必守）**：① **每次上传后立即重新 `+record-get`** 取该字段**当前** token 列表，再挑非目标项删除；② 删除动作**不得**复用上传前抓取的 token；③ 删完**必须再 `+record-get` 复核该字段附件数 = 1**（本例最终 `rev` 211、交付物仅剩 1 份），仅凭 `rc=0` 不算完成。
   - 判别残留：`+record-get` 交付物字段返回 **2 个条目且 size 不同**（`8368600` / `8368652`）即说明旧包未删干净。
1c. ⚠️ **`+record-upload-attachment` 的响应里，旧附件排在前面（本轮 149 再次实测）**：同名重传后，命令回显会列出该字段**全部**条目，顺序为 **旧在前、新在后**。若用 `head -1` / `[0]` 取"刚上传的新 token"，实际拿到的是**旧 token**，随后删除就会**把刚传的新包删掉、留下旧包**（`rc=0`、字段数=1，看起来"成功"，实则内容回退）。
   - **对策（必守）**：**只按 `size` 认新**——上传前记下新包字节数 `NEW`，上传后重读该字段，令 `待删 = [x for x in items if x['size'] != NEW]`；**绝不**依赖下标/顺序。
   - 复核口径：终态该字段应**恰为 1 条且 `size == NEW`**；若 `size` 是旧值，立即重传。
1d. **别名/空白**：附件名含全角字符时 `+record-get` 可能回显为别名，一律以 `size` 为唯一权威判据。
1e. ⚠️ **交付文档里不得写"会被本次操作改变的值"（本轮 151 实测的死循环）**：批次包内含 `交付文档.md`；若文档里写死了**交付物附件的 `file_token` / 批次包 `size` / 表 `rev`**，就会形成自失效循环 —— 改文档 ⇒ 重建 zip ⇒ 体积与 token 变 ⇒ 文档内容既不实 ⇒ 再改 ⇒ …… 永远收敛不了。
   - **对策（必守）**：文档只写**稳定事实**——记录 ID、字段 id、附件**文件名**、"该字段恰好 1 个文件"、题目/难度/类型；**易变值（`file_token`、批次包字节数、`rev`）一律不写入文档**，改为一句"以飞书行终态为准"。
   - 题目 zip / 答案 zip **不含交付文档**，其 size 稳定，可写；**只有批次包的 size 是易变值**。
   - 实操顺序：**先把文档定稿 → 再重建 zip → 最后上传/替换附件**；避免"传完又改文档"。
2. 移除属 high-risk-write，**必须经用户确认后**才加 `--yes`；目标 `file_token` 必须来自操作前刚读到的快照，避免删到别人新传的附件。
3. 全部完成后 `+record-get` **复核终态**（附件名、size、是否只剩一份，`rev` 应递增）。


## 5. 打包前必查（本次踩过的坑）

zip 内容对比**只比文件清单不够**，必须同时核对**层级**（`delivery/04-package-and-checklist.md` §2）：

```
<批次目录>/                     ← 顶层必须是批次目录
├── 交付文档.md                 ← 必交，放批次根（自检 #17）
└── <题目编号>/                 ← 题目目录
    ├── instruction.md / task.toml / rubrics.json
    ├── environment/ solution/ tests/
    └── model_runs/             ← G5 归档（delivery/06 §4）
```

**反例（本次修正）**：把 `FIN3-WKN-149/` 直接压成 zip 根 → 文件清单逐条正确，但
**缺 `交付文档.md`、缺批次目录层**，违反 §2 与 #17。修正后
`work_fin-b01_20261001.zip`（顶层=批次目录，127 文件 / ≈10 MB）。

**打包脚本要点**：先扫描 `.git/ __pycache__/ .venv/ __MACOSX/ reward*.json logs/ jobs/` 与符号链接；
用 `zipfile` 逐个 `writestr/write`（显式保留目录项、不跟随符号链接）；打完复核 `namelist()` 的**顶层集合**。
