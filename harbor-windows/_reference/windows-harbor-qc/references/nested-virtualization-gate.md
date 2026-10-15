# 嵌套虚拟化硬门禁（2026-10-15）

本项目不允许使用非嵌套虚拟化环境出题。做题、返修、模型运行、Oracle/NOP 和完整本地质检必须
使用实际嵌套虚拟化的 Windows 执行环境，并保留与当前题目和 jobs 绑定的原始证据。

## 什么算实际使用

典型链路是外层 hypervisor/L0 → Windows 虚拟机/L1 → 由 L1 内的 hypervisor 启动的
Windows VM 或 Hyper-V 隔离容器/L2，题目实际在 L2 执行。其他提供商的等价嵌套虚拟化链路
也可使用，但必须证明实际执行层，而非只写产品名称。

- 普通 process 隔离容器、裸机执行、WSL/Linux 模拟和只有一层 Windows VM，不构成嵌套虚拟化。
- `--isolation=hyperv` 只证明容器隔离方式，不自动证明嵌套。在物理宿主直接跑 Hyper-V 容器仍
  只有一层；必须证明其 Docker/hypervisor 宿主本身位于外层 VM 中。
- 如果 L2 是已实测的内层 Windows VM，再在其中运行 process 容器，须保留完整 L0→L1→L2
  链路和任务身份；不能只凭 process 参数认定合格或不合格。关键是实际任务是否位于嵌套层。
- CPU 显示 VT-x/AMD-V、启用 Hyper-V 功能、Docker 配置或“供应商支持 nested”都是准备条件，
  不能替代内层真实启动和题目执行证据。

## 每题核验

1. 记录外层 hypervisor、L1 虚拟机标识和配置，证明 L1 确实是外层 VM，并向 L1 暴露了虚拟化
   扩展。Hyper-V 可查外层 `Get-VMProcessor -VMName <实际VM>` 的
   `ExposeVirtualizationExtensions`；其他平台查等价配置。只读探测不得擅自启停或修改宿主。
2. 在 L1 核验虚拟化能力和内层 hypervisor 的实际启用状态，记录 Windows 版本、架构、Docker
   endpoint、hypervisor 版本和权限。能力检测还要与外层配置对照。
3. 实际启动内层 Windows VM/Hyper-V 隔离容器，保留创建命令、退出码、完整启动日志、VM/容器
   ID、Windows 实际终态和隔离信息。必须证明内层完成启动和执行，不能只截图配置开关。
4. 将当前冻结 Task 的模型、Oracle/NOP 和动态审计 jobs 关联到该执行拓扑、镜像身份和实际
   VM/容器 ID，保留标准 Harbor 原始命令、日志、逐 testcase 结果。旧的非嵌套运行证据不能
   当作本项通过证据；更换环境后冻结新身份并按当前用户授权的范围干净复验。
5. 甲方交付环境兼容性门禁仍要同时满足。甲方环境仅允许非嵌套路径时，不能静默退回裸机或
   普通 process 环境；记兼容性阻塞并说明实际缺少的嵌套能力。

## 判定

- 已确认实际执行使用非嵌套环境：`FAIL`，不满足本项目出题/运行环境要求。
- 外层配置无法访问、拓扑不明、未证实扩展暴露或未完成内层启动：`BLOCKED`，不得写 PASS。
- 能力未启用或启动失败造成运行无效：`INVALID/BLOCKED`、可信正式分 `null`；不能计作模型 0。
- 当前题目的外层 VM、扩展暴露、内层 hypervisor 和实际任务执行均有可信证据：本项 `PASS`；
  其他镜像、工具、功能、分数和质检门禁仍需全部通过。

`quality-review.json` 新增 `nested_virtualization`。PASS 必须填写实际 `configured_image`、
`task_id`、`task_version`、`task_hash`、`virtualization_depth`（至少 2）、`outer_guest_id`、
`outer_hypervisor`、`inner_hypervisor`，以及真实的 `virtualization_extensions_exposed=true`、
`inner_virtualization_enabled=true`、`task_runtime_in_nested_layer=true`。还需以下四项 checks，
每项 PASS 并引用原始证据：`outer_guest`、`capabilities_exposed`、`inner_runtime`、`job_binding`。

自动入口只校验结构、声明和当前 Task/镜像身份，不能仅凭这些字段证明嵌套虚拟化发生。审核者
必须打开外层配置、内层启动和 jobs 原始证据确认链路；禁止复制模板填 true 冒充实测。
