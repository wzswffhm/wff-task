# 飞书提交

本流程只在题目已经完成全部生产和验证后执行。目标是向用户指定的飞书 Base 新增或续传一条记录，并用飞书 CLI 上传正式题包和最终检查截图。

本文件描述的是配置中的 `submission` 交付表。生产前的场景去重使用配置中的 `scene_dedup` 表，必须按 [scene-dedup.md](scene-dedup.md) 运行 `register_scene_dedup.py`。两张表的 Base、table、view、唯一键、人员字段名称和状态语义不同，不得复用坐标或字段映射。

## 提交前门槛

开始写入前必须同时满足：

- `EXPERIMENT_RESULT.json` 明确记录 no-skill `reward=0`、with-skill `reward=1`；
- `FINAL_CHECK.json` 的 `ok` 为 `true`；
- 正式题包目录和同名 ZIP 均已生成，ZIP 解压后的根目录名与正式题包文件夹名一致；
- `FINAL_CHECK.png` 来自这次题包的 `capture_final_check.py`，不是烟雾测试、旧题或手工编辑图片；
- ZIP 不含 `model.env`、API key、no-skill、with-skill、Seed 轨迹、私有 verifier 日志、参考答案、缓存或内部工作目录。

任一条件不满足时继续返修，不创建飞书记录。

## 身份和目标核对

只使用项目飞书配置 `feishu-gsb.toml`（项目根目录或 `--config` 指定路径）。从该文件读取 CLI 路径和当前目标，不读取其他飞书配置。Windows 上 CLI 必须指向直连 `node` 的转发可执行（shim），不能经 `cmd.exe` 调 `.cmd` 包装。

1. 运行 `lark-cli auth status --json --verify`，确认 `identity=user`、用户身份可用且 `verified=true`。返回的 `appId` 和 `openId` 必须与唯一配置一致；配置的账号所有者以用户当前确认为准（不同项目可能是不同标注员），`openId` 用于`标注人`。
2. 使用 `base +url-resolve --as user` 解析配置中的 `wiki_url`。把返回的真实 `base_token`、`table_id` 和 `view_id` 与配置核对。
3. 依次运行 `base +base-get`、`base +table-get`、`base +view-get` 和 `base +field-list`，确认 Base、表、视图和字段真实存在。
4. 如果用户身份返回 `131006`、`91403` 或其他资源无权访问错误，停止写入。请用户把目标 Wiki/Base 分享给当前验证用户，或让正确账号重新登录。不得改用 bot、网页提交或另一份本地配置绕过权限。
5. 解析成功后才把真实坐标和已验证状态写回唯一配置。没有真实 `base_token` 时不得沿用旧 Base 的 token。

## 固定字段映射

写入前以 `base +field-list` 的真实返回确认名称、字段 ID、类型、是否多选和选项。字段不匹配时停止，不猜值、不擅自改表结构。

- `题目名or编号`：正式题包文件夹名，例如 `deepSWE_2026-09-24-1-description`，不写 ZIP 扩展名。
- `关联benchmark`（`fld4WBbnp5`）：单选字段，写入已有选项`deepSWE`。
- `标注人`（`fldsN2in6z`）：单值人员字段，写入配置中已验证用户的`openId`，格式为`[{"id":"ou_xxx"}]`。
- `交付压缩包`：附件字段，上传与正式题包目录同名的 ZIP。
- `最终检测skill的检测结果截图`（`fldGG5rJo1`）：附件字段，上传这道题对应且检查通过的`FINAL_CHECK.png`。
- `状态`：写入已有选项 `待质检`。只在两个附件均上传成功并核对后更新。

不要额外写入用户没有要求的内部实验信息。Base 若有只读、公式、lookup 或系统字段，不要尝试写入。

## 新增、续传和附件

飞书 CLI 的文件参数只接受当前工作目录下的相对路径。执行附件命令前进入 ZIP 与截图共同父目录，或把两个文件放入同一个安全的提交暂存目录；不得复制 `model.env` 或内部日志。

1. 使用 `base +record-search` 按 `题目名or编号` 精确查询正式题包文件夹名。
2. 没有同名记录时，用 `base +record-batch-create --as user` 创建一条记录，只填写`题目名or编号`、`关联benchmark`和`标注人`，保存返回的`record_id`。
3. 只有一条同名记录时，读取该记录并继续缺失步骤。不要重复新增。
4. 出现多条同名记录时停止，报告重复记录 ID，不能任意挑选或再新增。
5. 使用 `base +record-upload-attachment --as user`，把 ZIP 上传到`交付压缩包`，把 PNG 上传到`最终检测skill的检测结果截图`。两个字段分别调用，保留返回的`file_token`。
6. 上传命令不确定、超时或失败时，先用 `base +record-get` 读取该记录，确认附件是否已写入。已写入的附件不重复上传，只补缺失项。
7. 读回记录，核对题目名、benchmark、标注人、ZIP 文件名和 PNG 文件名。确认无误后，用 `base +record-batch-update --as user` 把`状态`更新为`待质检`。
8. 再读回一次记录，确认状态和两个附件都存在。最终报告题包名、记录 ID、两个附件文件名和状态，不输出 token、密钥或内部轨迹。

如果记录已经是 `待质检` 且字段与附件完整，视为提交完成，不再创建或重复上传。

## 失败处理

- 权限或账号错误：停止，保留本地交付物，等待用户修复访问权限。
- **附件上传被拒但记录可写**（如 `800020812 permission_denied` 只发生在 `+record-upload-attachment`）：该表开启了高级权限并对附件字段/media 上传单独控权。不要反复重试或改用 bot 身份（应用通常缺 `base:record:create`、`base:field:read` 等 scope，必然失败）。正确做法：保留 `record_id` 和状态为非`待质检`，请用户手动把 ZIP 与 PNG 拖入对应附件字段，或在表中给已验证用户放开附件上传权限后重试。
- **状态字段可能锁定其他字段**：`状态`一旦改为`待质检`，部分表配置会锁定该行其他字段。因此状态必须是最后一步；若已误设，先把它改回`已领取`解锁，补齐内容后再设回。
- 字段、字段类型或选项不匹配：停止，不创建字段或选项，报告真实结构差异。
- 创建记录成功但附件失败：保留 `record_id`，下次续传同一记录；状态不得改为 `待质检`。
- ZIP 或截图内容与当前题目不对应：重新打包或重跑最终检查后再提交。
- 最终读回不一致：不要重复建行，继续检查并修复同一记录。
