# 镜像远端交付与甲方目标环境门禁

本规则同时用于做题、返修和正式质检。口语化理解：你电脑上能跑，还要证明甲方能拿到同一镜像，
并在甲方实际环境中启动和执行题目。只看本地已有镜像、Dockerfile、Oracle/NOP 成功日志不足以通过。
同时按 [current-project-policy.md](current-project-policy.md) 满足系统至少 2019、优先 2025、
禁止 Nano Server/Server Core 和 Dockerfile 工具配置要求。甲方兼容性与完整系统要求必须同时满足；还须按 [nested-virtualization-gate.md](nested-virtualization-gate.md)
证明实际嵌套执行，不能把甲方兼容性检查当作非嵌套出题的豁免。

## 1. 冻结目标环境和配置

- 登记甲方 Windows 宿主 build、CPU 架构、容器隔离方式（process/Hyper-V）、是否允许现场构建、
  镜像仓库访问条件和运行权限，并引用甲方环境说明或实际探测证据。
- 2026-10-14 镜像清单中的目标是 `windows-dinp-2025`、宿主 build `20348/ltsc2022`，主 pod
  没有 Docker daemon，不能现场构建。这是该批次环境，不能泛化为所有 Windows 平台都必须同 build。
- 核对 `task.toml` 顶层和 `[environment]` 的 `docker_image`；两处同时存在时必须一致。平台确实
  使用 `instance.json.docker_image` 时，也须核对平台侧值。不要为此向直接 Harbor 题包新增平台 JSON。
- `Dockerfile FROM` 是基础镜像；复制工具链和 workspace 后的成品镜像不是同一个东西。不能把
  成品镜像字段直接替换成官方基础镜像，省略题目需要的依赖和源码。

## 2. 验证远端获取，排除本地缓存

- 对实际配置的成品镜像显式执行 `docker pull`，保存命令、开始/结束时间、退出码和原始 stdout/stderr。
  即使本地已有该镜像，也要访问仓库；仅 `docker image inspect` 或直接运行缓存镜像不是远端交付证据。
- 优先使用独立 Docker daemon/干净验证主机。无须清空现有镜像，也不得通过全局 prune 或删除他人资源
  来证明没有缓存。记录实际 Docker endpoint，避免误测其他 daemon。
- 拉取后记录 Image ID、RepoDigests、`Os`、`OsVersion`、`Architecture`，把远端身份与后续运行镜像绑定。
  Dockerfile 不 pin digest 仍不单独返修；记录本次解析得到的 digest 是运行证据要求。
- 短镜像名可能是 Docker Hub 的公开镜像，不能只凭名称判定“未发布”；完整仓库地址也不能证明已发布。
  必须以实际远端解析和拉取结果为依据。
- 私有仓库必须有甲方可拉取的权限依据或甲方身份下的验证。作者账号登录成功不等于甲方有权限。
  不得保存密码、token 或 Docker `config.json` 的认证内容到报告或题包。
- 目标不允许现场构建时，缺镜像字段、仅本地 build 的镜像或只有 Dockerfile 均不能交付。
  目标明确允许构建时，必须按目标同等构建流程实测，并符合当前项目镜像字段要求；不能默认支持 fallback。

只读/拉取示例（先把 `$qcImage` 设置成题包的实际镜像引用，不使用示例值冒充执行）：

```powershell
docker info --format '{{.OSType}}'
docker version
docker pull $qcImage
docker image inspect $qcImage --format '{{json .}}'
```

保留完整退出码和日志，再执行与目标实际隔离方式一致的启动及任务验证。

## 3. 验证启动和真实任务

- 根据目标宿主 build、镜像 `OsVersion`、架构和实际隔离方式验证 Windows 兼容性。不得仅因版本数字
  不同就判失败；Hyper-V 和 process 的兼容规则不同，最终需有目标同等环境的启动证据。
- `docker pull` 成功只证明获取成功。必须从新容器启动到就绪，再通过标准 Harbor 执行 Oracle/NOP，
  检查工具链、setup、参考解、测试、cleanup/restore 全流程；启动成功或一次参考解成功不能替代
  原有 Oracle/NOP 三轮门禁和其他质检要求。
- 本地 Hyper-V 成功不能替代甲方 process 隔离下的验证。如果无法得到同等环境或可靠甲方执行证据，
  本地结果单列，最终交付结论为 `BLOCKED`，不能写成甲方可运行。
- 更换基础/成品镜像、环境文件或实际运行环境后，冻结新版本、Task Hash 和镜像 digest，并干净复验。
  旧环境的模型或 Oracle/NOP 日志不能证明新环境通过。按当次用户授权的模型范围重跑，不擅自增加模型。

## 4. 判定和归因

| 实测情况 | 镜像门禁结论 |
|---|---|
| 配置缺失或互相冲突；确认镜像不存在；甲方无拉取权限且无认可替代交付方式；目标不支持构建却只提供本地镜像/Dockerfile | `FAIL`，交付问题 |
| 已在目标同等环境确认镜像架构/OS/隔离不兼容，或容器、依赖、setup 无法执行 | `FAIL`，环境交付问题 |
| 质检机网络故障、仓库临时不可用、质检账号权限不足、未知甲方环境/权限，或证据不足 | `BLOCKED`，继续归因；不能直接说作者未发布 |
| 远端获取、甲方访问依据、目标兼容、新容器启动和真实任务执行均有当前版本证据 | 本门禁 `PASS`；其余门禁仍须全部通过 |

本项引起的运行无效必须记 `INVALID`、可信模型分数 `null`，不能消费为模型正式 0 分。

## 5. 结构化证据与做题顺序

`quality-review.json` 必须新增 `image_delivery`。要声明 `PASS`，必须填写实际 `configured_image`、
`resolved_image_digest`、`target_profile`（`windows_build`、`architecture`、`isolation`、
`can_build_images`），以及下列五项 `checks`。每项都必须 `PASS` 并列出原始证据：

- `remote_pull`：仓库获取日志、退出码和远端 digest；
- `recipient_access`：公开可拉取或甲方权限/身份验证依据；
- `target_compatibility`：目标环境说明、镜像 inspect 与兼容性实测；
- `clean_start`：新容器启动、就绪和实际隔离方式；
- `task_execution`：同一镜像身份下的标准 Harbor Oracle/NOP 结果和逐 testcase 证据。

声明 `FAIL/BLOCKED` 时写清当前实测现象、证据和归因，不得编造成功字段。自动入口检查结构与镜像引用
绑定，不会因为填了 PASS 字样就证明远端执行发生；审核者仍必须逐项查看原始日志。

做新题或返修时，先确认目标环境、制作并发布可访问的镜像，完成拉取/权限/兼容/启动和控制验证，
再按用户授权运行模型。镜像门禁没有通过，不能标记完整质检通过或作为合格作业上传。外部发布仍按
用户授权和实际执行权限处理；缺仓库或权限时记录阻塞，不推到未经授权的公共仓库。
