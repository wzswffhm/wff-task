# 十四项人工质量复核模板

复制本模板到质检输出目录的 `manual-review.md`。每项写 `PASS/FAIL/BLOCKED` 和可定位证据。
不能只写主观结论；至少给文件路径、testcase ID、关键行为或原始 job 路径。

同时必须完成 [采购手册接入规则](procurement-manual-integration.md) 中的 WIP 94 项和 D01–D20
逐项审计。可直接复用随 Skill 提供的原始
[证据模板](windows-procurement-qc-manual-20260927/04-逐项证据与报告模板.md)。

## 结论规则

- 自动报告是 `FAIL/BLOCKED` 时，人工复核不能升级；
- 自动报告为 `PASS` 且下列每项均为 `PASS`，最终才可写 `PASS`；
- 任一项 `FAIL`，最终为 `FAIL`；证据不足或无法复核写 `BLOCKED`。

## 复核表

| 项目 | 结论 | 证据与说明 |
|---|---|---|
| Golden/NOP 符合预期：Oracle 得分、NOP 不得分，并逐个 testcase 解释终态 |  |  |
| 逐项判分正确：每条评分标准和每个 testcase 的轨迹、结果、得分互相一致 |  |  |
| 题面与测试一致：双向映射完整，检查真实功能，不绑定 Golden 私有写法 |  |  |
| 无 Hack：没有联网取答案、git 拉答案、搜索 Golden/隐藏测试、改测试或 Verifier 骗分 |  |  |
| Windows 价值：离开目标 Windows Runtime 后核心行为会消失或实质变化 |  |  |
| 严格模型区分度：完整规定有效运行中 Qwen 正式分总和低于 Opus；平分、全零、双方满分均不能通过 |  |  |
| 范围、版本、公式、镜像、测试树、Task/ZIP Hash 和运行批次身份已冻结 |  |  |
| WIP 94 项完整登记，N/A 均有适用性依据 |  |  |
| D01–D20 全部有结论和原始证据 |  |  |
| 正式分已从 required testcase 和冻结公式独立复算 |  |  |
| 原始证据、历史结果、修改版本和干净复验完整闭环 |  |  |
| 镜像远端交付：实际镜像可拉取、甲方有访问权限、目标环境兼容、新容器就绪、同镜像 Harbor 执行成功 |  |  |
| 实际系统不早于 2019，优先 2025；不是 Nano Server/Server Core，基础来源可追踪且未额外裁剪 |  |  |
| 任务与执行链用到的工具在 Dockerfile 中可复现配置，每项均有安装/基础自检、版本和真实功能证据 |  |  |
| 实际嵌套虚拟化：外层 VM、扩展暴露、内层 hypervisor/Windows 启动和当前 Task/jobs 绑定均有原始证据 |  |  |
| `instruction.md` 的每项公开要求都能映射到 required testcase |  |  |
| 每个 required testcase 都能反向映射到题面或公开契约，没有事后隐藏要求 |  |  |
| P2P 在初始态通过且与修改范围相关；核心 F2P 在 NOP 失败、Golden 后通过 |  |  |
| 核心断言走真实生产路径，验证输入、输出、状态、副作用或 Windows 终态 |  |  |
| 测试接受独立等价实现；源码关键词、Diff、文件存在、日志和编译成功只作辅助证据 |  |  |
| 异步、子进程和负观察有完成回执或健康哨兵，无提前退出伪通过 |  |  |
| `prepare/restore/cleanup` 可重复执行，清除旧产物、驻留进程和系统残留 |  |  |
| Solution 幂等、可由标准 OracleAgent 调用且只修改生产代码 |  |  |
| Agent 工作区、镜像、挂载、Git 历史、缓存和日志未泄漏 Solution/隐藏测试/reward |  |  |
| 8 个模型 job 均逐份检查完整轨迹、命令、网络、workspace 与候选代码，能够排除绕过 |  |  |
| 四模型原始提示词为自然中文口语表达，未加“中文口语化提示：”标签 |  |  |
| Task、镜像、8 份模型轨迹、6 份 Oracle/NOP job 和最终证据引用同一冻结版本 |  |  |
| 来源、许可证、隐私和授权满足本批次要求；`source.json` 缺失本身不作一票否决 |  |  |

## 最终结论

新增项按 [image-delivery-gate.md](image-delivery-gate.md) 逐项填写
`quality-review.json.image_delivery`。缺证据写 BLOCKED，确认交付问题写 FAIL；不得仅凭镜像短名
认定未发布，也不得用本机已有镜像的成功日志作为甲方交付证明。

```text
自动结论：
人工结论：
最终结论：
复核人：
复核时间：
```

最新四项要求、六项简化必查表和两个新增结构化键见 [current-project-policy.md](current-project-policy.md)。

嵌套环境复核须填写 `nested_virtualization`，细节见 [nested-virtualization-gate.md](nested-virtualization-gate.md)。
