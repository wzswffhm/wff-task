# 飞书作业表自动回写（对照 zq2026080704332）

原先需人工编辑/上传的字段与状态，**由 agent 用 `lark-cli` 自动完成**。用户说停或鉴权失败时除外。

成功行实况（`recuXofnjTeLmx`）：已填 `状态/四列元数据/instruction/task.toml/zip/标注员/修改日期`；**`标注日期` 为空**；**`质检员` 为空**（质检侧填写，agent 不写）。

## 表定位（本工作流默认）

| 项 | 值 |
|----|-----|
| Base token | `M9y1bDK1da7wXQshh8xcAuhbnYb` |
| Table id | `tblIESQ5DH2KzEyl` |
| 身份 | `--as user`（当前标注账号，如向威） |
| 查作业 | `--search-field 作业ID文本 --keyword <zq…>` |
| 环境 | `export LARK_CLI_NO_PROXY=1` |

鉴权：`lark-cli auth status` 须为正确标注员且 `status=ready`；记录当前账号的 `openId` 用于写 `标注员`，不要硬编码他人 openId。

## 完整自动写入清单（对照成功题）

### 必须写（交付闭环缺一不可）

| 字段 | 何时 | 写法 / 示例 |
|------|------|-------------|
| `标注员` | 开做认领时；交付前再确认一次 | User 字段：`[{"id":"<当前 auth openId>"}]`，与登录标注员一致（本队列为向威） |
| `任务类型` | 选题确认 / 变更 / 交付 | 与 toml `task_type` 一致，如 `"feature"` |
| `应用领域` | 同上 | 与 `domain` 一致，如 `"存储"` |
| `子领域` | 同上 | 与 `subdomain` 一致，如 `"文件存储"` |
| `编程语言` | 同上 | 与 `language` 一致，如 `"c"` |
| `instruction.md文本内容` | 交付前覆盖终稿 | **本题** `instruction.md` 全文（勿贴错题/自检清单/其它作业正文） |
| `task.toml 文本内容` | 交付前覆盖终稿 | **本题** `task.toml` 全文 |
| `harbor format task（Zip文件包）` | checklist PASS 后 | **仅 1 个**合规 zip（含 jobs）；`+record-upload-attachment` |
| `状态` | 开做 / 交卷 | 开做→`已领取`；交卷→`已提交` |
| `修改日期` | 每次回写或重传 zip | 当天，如 `"2026-08-08 00:00:00"` |

交卷后公式须满足：

- `task.toml 是否正确` = `✅与任务类型，应用领域，编程语言对应正确`
- `instruction.md文本内容是否重复` = `无重复`（若显示重复：改写 instruction 去重后再回写）

### 禁止写入

| 字段 | 原因 |
|------|------|
| `标注日期` | **不要填**（成功题即为空；用户明确要求不写） |
| `质检员` | 质检流程填写；agent 不写、不清空 |
| `作业ID` / `作业ID文本` | 系统/公式 |
| `instruction.md文本内容处理` / `是否重复` / `task.toml 是否正确` | 公式自动算 |
| `提交` | Button，OpenAPI 不支持；以 `状态=已提交` 代替 |

## 状态机

```text
未领取 →（认领：写标注员 + 状态）→ 已领取
已领取 →（全套文本+zip+修改日期）→ 已提交
待返修 →（改完重传）→ 已返修 →（再交）→ 已提交
已通过 / 质检中 → 不擅自改回
```

## 命令模板

### 1) 取 record_id + 当前标注员 openId

```bash
export LARK_CLI_NO_PROXY=1
# openId
lark-cli auth status --json   # identities.user.openId / userName

lark-cli base +record-search \
  --base-token M9y1bDK1da7wXQshh8xcAuhbnYb \
  --table-id tblIESQ5DH2KzEyl \
  --keyword "$ASSIGN_ID" \
  --search-field '作业ID文本' \
  --limit 1 --as user --format json
# → data.record_id_list[0]
```

### 2) 开做认领（标注员 + 已领取）

```bash
python3 - <<'PY'
import json, subprocess
record_id="rec…"
open_id="ou_…"   # 当前 auth
payload={
  "标注员": [{"id": open_id}],
  "状态": "已领取",
}
subprocess.check_call([
  "lark-cli","base","+record-upsert",
  "--base-token","M9y1bDK1da7wXQshh8xcAuhbnYb",
  "--table-id","tblIESQ5DH2KzEyl",
  "--record-id",record_id,"--as","user",
  "--json", json.dumps(payload, ensure_ascii=False),
])
PY
```

### 3) 交卷回写（全套，不含标注日期）

```bash
python3 - <<'PY'
import json, pathlib, subprocess, datetime, re
record_id="rec…"
open_id="ou_…"
task_dir=pathlib.Path("task/…")
ins=(task_dir/"instruction.md").read_text(encoding="utf-8")
toml=(task_dir/"task.toml").read_text(encoding="utf-8")

def meta(key):
    m=re.search(rf'^{key}\s*=\s*\"([^\"]+)\"', toml, re.M)
    return m.group(1) if m else ""

payload={
  "标注员": [{"id": open_id}],
  "instruction.md文本内容": ins,
  "task.toml 文本内容": toml,
  "任务类型": meta("task_type"),
  "应用领域": meta("domain"),
  "子领域": meta("subdomain"),
  "编程语言": meta("language"),
  "状态": "已提交",
  "修改日期": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
  # 绝不写「标注日期」
}
subprocess.check_call([
  "lark-cli","base","+record-upsert",
  "--base-token","M9y1bDK1da7wXQshh8xcAuhbnYb",
  "--table-id","tblIESQ5DH2KzEyl",
  "--record-id",record_id,"--as","user",
  "--json", json.dumps(payload, ensure_ascii=False),
  "--format","json",
])
PY
```

### 4) 上传唯一 zip

```bash
# 若已有旧附件需替换：先 +record-remove-attachment 再传
lark-cli base +record-upload-attachment \
  --base-token M9y1bDK1da7wXQshh8xcAuhbnYb \
  --table-id tblIESQ5DH2KzEyl \
  --record-id "$RECORD_ID" \
  --field-id 'harbor format task（Zip文件包）' \
  --file "task/<task-name>.zip" \
  --as user --format json
```

### 5) 交卷校验（投影这些列）

```bash
lark-cli base +record-get \
  --base-token M9y1bDK1da7wXQshh8xcAuhbnYb \
  --table-id tblIESQ5DH2KzEyl \
  --record-id "$RECORD_ID" \
  --field-id '状态' --field-id '标注员' --field-id '质检员' \
  --field-id '任务类型' --field-id '应用领域' --field-id '子领域' --field-id '编程语言' \
  --field-id 'instruction.md文本内容' --field-id 'task.toml 文本内容' \
  --field-id 'task.toml 是否正确' --field-id 'instruction.md文本内容是否重复' \
  --field-id 'harbor format task（Zip文件包）' \
  --field-id '标注日期' --field-id '修改日期' \
  --as user --format json
```

验收：

- [ ] `标注员` = 当前登录用户（非空）  
- [ ] `标注日期` = **null / 空**（未误写）  
- [ ] `质检员` 保持原样（通常 null）  
- [ ] 四列元数据 + toml 公式 ✅  
- [ ] instruction / toml 为本题终稿  
- [ ] zip 唯一且 size>0  
- [ ] `状态`=`已提交`，`修改日期` 有值  

全部通过 → 飞书侧完成 → 才开下一题。

## 衔接顺序

1. 本地 P0 + checklist PASS，生成 zip  
2. upsert：标注员 + 四列 + instruction + toml + 修改日期 + 状态已提交（**不写标注日期**）  
3. 上传 zip（保证单元格仅 1 个包）  
4. 投影校验  
5. 短汇报 → **零确认**立刻领下一题（仅 **标注员=向威 且 状态=已领取**）；无则停止挂机循环，禁止刷表 / 等用户确认  
 

## 权限与安全

- 写表前确认 `userName` 是本作业标注员，openId 与 `标注员` 一致  
- 不把 API Key 写入任何飞书字段  
- 不上传未脱敏 zip  
- 不改写、不清空他人的 `质检员`
