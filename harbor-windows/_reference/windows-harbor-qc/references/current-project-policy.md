# 当前项目质检口径（2026-10-15）

本文件适用于后续做题、返修和质检，是用户本次更新的规则。若旧项目摘要、历史示例或手册快照与
本文件冲突，以本文件的当前项目口径判定，同时在 WIP 94 项中保留原口径与适配说明。不得修改
手册历史原文，也不得用本简化清单代替完整目录、证据、镜像交付、WIP 94 项和 D01–D20 检查。

## 五项新增硬门禁

1. **Windows 镜像不早于 2019，优先 2025，禁止裁剪系统。** “19/25”指系统版本，不是 Docker
   软件版本或镜像上传年份。核对实际 `OsVersion`、版本发布来源和家族；Windows Server 2019
   对应最低 build 17763。用户已明确 Nano Server、Server Core 都禁止；给它们补装 PowerShell
   不会变成合格的完整系统。最终运行层及其基础镜像不得来自这两类或自定义额外裁剪系统。
   完整 Windows/Windows Server 容器镜像仍需确认实际组件和甲方兼容性，不能只凭自定义名称或
   标签“full/2025”通过。2019/2022 并非因为不是 2025 就失败；2025 是优先项，甲方实际可运行
   是硬门禁。甲方仅支持 2022 时选用兼容的完整镜像并记录依据，不能强上 2025。
2. **任务用到的工具必须在 Dockerfile 中可复现地配置。** 盘点 instruction、workspace、环境
   脚本、Solution 和 Tests 实际依赖的 PowerShell、Excel、编译器、运行库及其他工具。新增工具
   必须由 Dockerfile 的安装、离线安装脚本或完整复制部署步骤提供，固定版本和构建来源；不能
   依赖作者宿主机、临时手工安装、host mount 或模型运行时下载。基础完整镜像已自带的系统工具
   不要求破坏性重复安装，但 Dockerfile 必须有明确的版本/可用性自检，并保留基础来源与构建
   证据。每项都要在成品新容器内验证版本和题目实际功能，PATH 或文件存在不能代替功能验证。
   需要真实 Excel/COM 时，必须使用真实工具及其功能探针；Python 表格库、CSV 或 Mock 不能冒充
   Excel。若目标 Windows 容器确实无法安装或运行所需工具，记环境不适配/阻塞并调整选题或按
   用户认可方式执行，不能伪装已经支持。
3. **题目核心必须依赖真实 Windows 语义。** 仅调用 PowerShell、换成 Windows 工具、使用盘符、
   生成 `.bat` 文件或处理普通表格均不足以通过。写出 Windows 反事实：离开 Windows 后哪个核心
   行为无法等价处理。可选注册表键/值类型和视图、NTFS/ACL/重解析点、Windows 文件锁、命名
   对象、Win32 进程与安全语义、`cmd.exe`/BAT 的真实解析、引号、变量展开、退出码等。测试必须
   执行相应真实路径和终态，不能只验证调用了某个工具或代码包含某个 Windows 关键词。
4. **模型正式分必须拉开差距。** 同一冻结 Task、同一 required 集合、规定的 Qwen/Opus 各三轮
   全部有效，要求 `Qwen model_score_sum < Opus model_score_sum`；各三轮平均分结论相同。
   比较整批有效正式二值 reward，不是选一轮、按 testcase 比例当模型分数或只看截图。
   正式总分相等，即使 Opus testcase 通过更多仍失败；全零分平局也失败；两边全满分失败。
   testcase 表现仍须逐项审计，但不用于挽救正式总分平局。此规则替代之前的平分二级判据和
   全模型零分例外。不得修改 reward、削弱测试或择优重跑制造差距；改题后提升版本并重跑授权范围。

5. **必须实际使用嵌套虚拟化，不允许非嵌套环境出题。** 做题、返修、模型和 Oracle/NOP 执行以及
   完整本地质检须保留外层虚拟机、虚拟化扩展暴露、内层 Windows 启动和实际任务执行链。
   裸机、普通 process 容器、单层 VM、CPU 能力声明或物理机直接 Hyper-V 容器不能代替嵌套。
   详见 [nested-virtualization-gate.md](nested-virtualization-gate.md)。缺证据 BLOCKED，确认非嵌套
   FAIL，执行链路故障为 INVALID/null。甲方兼容性规则仍须同时满足，不擅自降级运行方式。

## 六项简化检查必须逐项达标

| 必查项 | 达标标准与证据 |
|---|---|
| 1. Golden path 与空跑 | Oracle 三轮 `VALID/1`、required 全 PASS；NOP 三轮 `VALID/0`、P2P 全 PASS、核心 F2P 因缺陷 FAIL。给出逐项原始日志，基础设施异常为 INVALID/null。 |
| 2. Windows 价值 | 题面、生产路径和核心 testcase 共同证明 Windows 专项行为，写出具体反事实。仅使用 PowerShell/Windows 工具不通过。 |
| 3. Testcase 对应题面并检查功能 | 题面与 required 双向映射；执行输入、输出、状态、副作用与 Windows 终态；接受等价实现，不绑定私有函数名、固定代码布局、算法或题面未公开的签名约定。公开必要接口也必须有行为测试，不能只验签名。 |
| 4. 每个 case 判分正确 | 逐模型、逐轮、逐 case 对齐实际下发要求、候选 SHA、完整轨迹、断言、Windows 命令与退出码、expected/actual、终态和独立复算贡献，得分和未得分都有明确证据。不能只查总分或抽查几个 case。 |
| 5. 无 Hack | 检查网络取答案、websearch、git pull/fetch/clone、源码下载、搜索/读取 Golden patch、隐藏测试/reward、改评分器和复用旧产物。区分访问尝试与实际获取/使用；仅合法依赖下载或命令关键词不能直接定罪，必须看目的、内容、权限和实际影响。无法排除绕过为 BLOCKED，确认取答案/绕过为 FAIL。 |
| 6. Opus/Qwen 区分度 | 当前版本全部规定有效运行严格满足 `Qwen model_score_sum < Opus model_score_sum`，原始 reward、完整 testcase 和独立复算互相一致；INVALID 不算 0。 |

## 如何接入执行

- `quality-review.json` 原有十一项继续执行，增加 `windows_image_policy`、`toolchain_in_image`
  和 `nested_virtualization`，共十四项。新增项缺证据/字段只能 BLOCKED；已确认系统、安装或运行缺陷记 FAIL。主模型区分度
  是独立的自动硬门禁，人工 PASS 不能覆盖失败。
- `windows_image_policy` 的 PASS 必须记录 `configured_image`、实际 `windows_build`、
  `release_year`、`family`（`windows` 或 `windows-server`）、`untrimmed=true`，以及每项
  `runtime_bases` 的 `image`、版本、家族和原始证据。自定义镜像必须能追溯到实际基础层；不能
  用包装名称隐藏 Nano Server/Server Core。
- `toolchain_in_image.tools` 每项记录 `name`、`version`、`required_by`、`dockerfile_location`、
  `provisioning_kind`（`installed` 或 `base_inherited`）、`provisioning_evidence`、
  `functional_probe`、`runtime_evidence` 和 `status`。从实际调用逐项核对清单是否完整。
- `nested_virtualization` 必须按 [嵌套门禁](nested-virtualization-gate.md) 填写实际拓扑、至少两层
  虚拟化、当前 Task/镜像身份、能力启用和内层真实运行的四项原始证据。
- 自动模板由 `run_delivery_qc.py` 生成。脚本会检查结构、引用、已知禁止基础镜像和严格分差，但
  结构完整不等于真实执行，仍必须打开所引用的原始构建、镜像 inspect、工具功能和轨迹证据。
- 做新题先验选题 Windows 价值，再确认嵌套执行链、完整镜像版本、甲方可获取/可运行、工具安装和控制门禁，
  最后 Qwen 先跑，再按已授权范围运行 Opus 等模型。Qwen 三轮全 1 时无需消耗 Opus，必须实质
  升级任务或换题；升级后冻结新版本、Hash 和全批证据。合格前不上传为完成作业。
