# 通过 lark-cli 发布审核意见

用户要求将审查结果写到飞书文档时执行本流程。有指定文档则更新指定文档；
没有指定则新建。仅安装/注册 Skill 不创建文档。
使用本机已配置的 `lark-cli`，无需 LangChain 或另配飞书 MCP。
本流程根据 lark-cli 1.0.41 的 v2 帮助与 dry-run 验证，真实读写是否可用以运行结果为准。

## 1. 准备完整批次意见

逐题执行主流程，每题保存 evidence.json / review.json / result.json / result.md。
用 index.json 对照实际发现的所有 proposal.json，不能悄悄略过失败题。
每处理完一题更新本地进度；恢复任务时核验已保存证据，再处理未完成题。
个别取证失败可以继续其他题，汇总必须标出该题未完成以及失败原因。
`valid=false` 的结果不能作为有效审核结论；修复后重跑或列为“审查未完成”。

在批次输出目录生成 UTF-8 `batch-report.md`，内容包括：

- 一级标题：OBM 审核意见 + 批次名称 + 审查日期。
- 范围：输入目录、规则版本、预检情况、发现/完成/未完成题数。
- 汇总表：真实题目路径、对照 Benchmark/任务、领域分数、核心能力分数、最终结论。
- 每题正文：结论和理由、两侧原文、Source 处置、commit/PR 链接与判断、
  Proposal/Verify/Skill 问题、覆盖限制、具体整改动作。
- 本地证据目录及每题 packet_id；公开来源保留可访问 URL。

确认 H02 的题只写实际做过的拒收判断，后续评分标为“因 H02 停止”。
其他缺分数写“缺证据”，不要以零代替。飞书读者无法访问本机文件，
因此不能只贴 file:// 链接，应把关键证据摘录写入正文。
无需上传所有原始 Source 或在文档中粘贴整包 JSON。

## 2. 核对 CLI

```bash
lark-cli --version
lark-cli auth status
lark-cli docs +create --api-version v2 --help
lark-cli docs +update --api-version v2 --help
lark-cli docs +fetch --api-version v2 --help
```

使用 `--as user` 明确以当前登录用户操作。auth status 中 `needs_refresh` 不等于未登录，
CLI 会在下一次 API 调用尝试刷新；刷新失败或接口缺权限时保留本地结果并报告具体错误。
不将凭证、完整认证状态或用户身份信息放入审核文档。

## 3. 新建或更新

先生成实际报告，再使用 `--dry-run` 检查同一份文件的请求。
先切换到批次输出目录，`--content` 用 `@./batch-report.md`。
当前 CLI 拒绝绝对路径及越出当前目录的文件路径；用相对文件路径传入，
避免将整篇报告拼入 shell。不在命令中提供 access token。

未指定文档，默认在当前用户云文档空间新建：

```bash
cd '/绝对路径/批次输出目录'
lark-cli docs +create --api-version v2 --as user \
  --doc-format markdown --content '@./batch-report.md' \
  --parent-position my_library --dry-run

lark-cli docs +create --api-version v2 --as user \
  --doc-format markdown --content '@./batch-report.md' \
  --parent-position my_library
```

文档标题写在报告的一级标题中。用户指定父文件夹/知识库节点时，用
`--parent-token <实际token>` 替代 `--parent-position my_library`，不要猜 token。
解析成功响应中的实际文档 URL/token 并立即保存到本地 `publish-state.json`。
不自行拼接或虚构文档链接。

指定了已有文档时，先 fetch 查看它的当前内容。默认追加本批次意见，保留原内容：

```bash
cd '/绝对路径/批次输出目录'
lark-cli docs +update --api-version v2 --as user \
  --doc '实际文档URL或token' --command append \
  --doc-format markdown --content '@./batch-report.md' --dry-run

lark-cli docs +update --api-version v2 --as user \
  --doc '实际文档URL或token' --command append \
  --doc-format markdown --content '@./batch-report.md'
```

只有明确授权替换整份文档时才用 overwrite。
多批次共用文档时通过批次标题定位本批次区块；修改已发布内容先 fetch full 取得实际
block ID 与 revision，再按当前 CLI 帮助选择相应区块更新，不能猜 ID 或删除其他批次。

## 4. 回读与恢复

```bash
lark-cli docs +fetch --api-version v2 --as user \
  --doc '返回的真实文档URL或token' --doc-format markdown
```

核对标题、题数、每题结论和两项分数、关键证据、整改意见均实际存在。
仅拿到 create/update 的成功响应还不算完成验证；内容较长时按 CLI 分段读取核对。
返回用户文档链接、题目数量与结论分布，以及未解决的限制。

本地 `publish-state.json` 至少记录：

- 输入目录、Skill 版本、各题 packet_id。
- batch-report.md 的 SHA-256。
- 实际文档 URL/token、创建/更新操作、写入完成与回读验证状态。

重跑时先读该状态并 fetch：相同报告已写入且回读一致则不重复新建或追加。
网络超时、写入结果不明确时先核对服务端状态；不能盲目重试 create/append。
未能完成写入时明确报告“本地审核已完成，飞书发布失败/待核实”，保留可重试结果。
不得声称文档已发布，或自动变更分享权限、发送消息。
