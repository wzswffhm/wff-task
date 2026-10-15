# 十四项质量门禁：语义与手册、镜像交付、完整系统、工具与嵌套虚拟化

前五项直接决定题目和评分是否可信，中间五项保证 2026-09-27 Windows 采购质检手册得到完整执行，
第十一项核验镜像远端交付，第十二/十三项核验完整系统与工具，第十四项核验实际嵌套虚拟化；
不改变 WIP 94 项的编号和数量。
十四项都不是建议项，也不能因为目录完整、Harbor 能运行、
最终 reward 看起来正常或模型分差达标而忽略。每项都必须给出可定位证据并写成
`PASS/FAIL/BLOCKED`；任何一项不是 `PASS`，整题都不能最终通过。

## 1. Golden 与 NOP 的得分符合预期

口语化理解：标准答案确实应该拿满分，什么都不做确实应该拿不到分，而且两边的每个
testcase 都要呈现合理结果。

必须核对：

- 3 次 Oracle 都是 `VALID/1`，required testcase 全部 `PASS`；
- 3 次 NOP 都是 `VALID/0`，P2P 全部 `PASS`，至少一个核心 F2P 因目标功能未实现而 `FAIL`；
- Oracle/NOP 的失败或通过来自真实功能行为，不能来自环境、权限、依赖、解析、零测试或旧产物；
- 逐个比较 Oracle 与 NOP 的 testcase 终态，解释为什么该项应得分或不应得分。

标准解不通过、空跑也通过、空跑因基础设施故障得 0，或结果无法解释，均为 `FAIL`。

## 2. 每项评分标准和每个 testcase 判分正确

口语化理解：不能只看总分。要把评分规则、实际执行结果、模型轨迹和每个 testcase 对起来，
确认该给的分给了、不该给的分没有给。

必须逐项建立至少包含以下内容的证据表：

```text
评分项 / testcase ID
题面依据
实际执行行为与终态
对应轨迹或日志路径
预期是否得分
实际是否得分
复核结论
```

需要同时排除：

- 功能没有完成却被判 `PASS` 的漏判；
- 功能已经完成却被判 `FAIL` 的误杀；
- testcase 已通过，但聚合器、reward 或评分项没有正确计分；
- testcase 已失败，但正式分数仍错误地给成 1；
- 评分项重复计算、漏算，或者评分标准本身与题面冲突。

只抽查部分 testcase、只看总分或只看 `reward.txt` 都不足以通过本项。

## 3. Testcase 严格对应题面并检查功能

口语化理解：测试应该检查“程序做对了没有”，不能检查“代码是不是照标准答案那样写”。

必须完成题面与 testcase 的双向映射：

- 题面每项公开要求至少有一个 required testcase 覆盖；
- 每个 required testcase 都能回到题面、公开接口或公开约束；
- 核心断言走真实生产路径，检查输入、输出、状态、副作用或 Windows 终态；
- 测试接受独立等价实现，不绑定 Golden 的私有函数名、局部变量、文件布局、固定代码片段、
  调用顺序或某一种算法；
- 源码正则、关键词、Diff、文件存在、日志文本和“能编译”只能作辅助证据，不能代替功能验证。

存在题外隐藏要求、测试照着 Golden 私有实现写、或正确等价实现会被误杀时，本项 `FAIL`。

## 4. 没有 Hack、答案泄漏或绕过行为

口语化理解：模型必须自己分析和修改代码，不能联网抄答案、从本地找到标准答案，或者修改
测试和评分器骗分。

必须逐份检查 8 个模型 job 的完整输入、响应、工具调用、命令、网络行为、workspace 和候选代码，
重点查找：

- `websearch`、浏览器搜索、外部 HTTP 下载、`curl/wget/Invoke-WebRequest` 等取答案行为；
- `git pull/fetch/clone`、包管理器拉取题目相关源码、访问上游未冻结内容；
- 在目录、镜像、挂载、Git 历史、缓存或日志中搜索并读取 `solution/`、Golden patch、隐藏测试、
  reward、预期输出或其他标准答案；
- 修改 tests、Verifier、required testcase、reward 或基础设施来制造通过；
- 复用旧二进制、旧 workspace、旧结果，硬编码 testcase 答案或根据测试名称定向返回。

网络访问本身只有在题面明确需要且不能获得答案时才可能允许，并必须有范围与证据。发现真实绕过，
或轨迹不完整到无法排除绕过时，分别判 `FAIL` 或 `BLOCKED`。

## 5. 题目具备真实 Windows 价值

口语化理解：这道题的难点必须来自 Windows 本身，不能只是普通跨平台题换成 PowerShell 或放进
Windows 容器。

复核时写出 Windows 反事实：如果换到 Linux 或普通跨平台 Runtime，哪个核心行为会消失或发生
实质变化。可接受的价值通常来自注册表、NTFS、ACL、重解析点、文件锁、命名对象、服务、DPAPI、
Win32 API、Windows 路径/命令行规则、进程或安全模型等。

只有启动脚本使用 PowerShell、路径里出现盘符、镜像是 Windows、调用 Windows 工具或文件扩展名是 BAT，
不能单独证明 Windows 价值。必须证明核心生产路径和 testcase 实际依赖 Windows 特有行为。
若核心功能可原样移到 Linux，测试也不依赖真实 Windows 语义，本项 `FAIL`。

## 与人工门禁并行的严格模型区分度硬门禁

分析本次规定的完整模型轨迹和 testcase，并按同一版本全部有效主模型运行比较正式 reward。
Qwen、Opus 各三轮必须满足 `Qwen model_score_sum < Opus model_score_sum`。平分无论全零或
Opus testcase 更多均失败；双方三轮全满分失败。GLM/Kimi 参与其授权范围内的结果审查，不改变
主分差规则。人工门禁不能把自动区分度 FAIL 升级为 PASS。旧平分和全零例外取消。

## 6. 范围、版本、公式和资产身份已冻结

必须登记采购来源、批次、task ID/version、ZIP 与 Task Hash、base commit、实际 instruction、环境、
Solution、测试树、required testcase、评分公式、镜像、工具链和模型运行批次。历史结果、被替代
rerun 和本次结果分开保存。不同版本、测试树或公式不能合并统计；无法证明当前运行使用哪套资产时
判 `BLOCKED`。

## 7. WIP 94 项已逐项审计

必须提交 FC 13 项、任务有效性 18 项、可解性 7 项、完整性 6 项、环境 14 项、验证器 36 项的
完整矩阵。每项填写 `PASS/FAIL/FLAG/BLOCKED/N/A`、证据、影响和处理；`N/A` 必须说明依据。
缺行、用静态存在性冒充动态验证、或无证据写 PASS 时判 `BLOCKED`；确认存在适用项缺陷时判
`FAIL`。Windows 适配与 WIP 原口径冲突时双列结论，不得静默豁免。

## 8. D01–D20 动态审计已完成

按采购手册逐项覆盖 Golden/no-change、稳定性、要求实际下发、双向映射、逐项判分、等价实现、
故障反例、Mock 保真、Windows 环境和真实终态、构建与产物身份、异常与日志、Hack/泄露、分数
复算、失败归因和批次交付。每项至少有一项可定位原始证据；未执行或只有报告摘要时判
`BLOCKED`。

## 9. 正式分数已经独立复算

必须直接使用 required testcase 终态、rubric 条件、前置门禁和冻结公式计算分数，并对照
verifier report、reward 和平台总分。空清单、重复/缺失 ID、SKIP/ERROR/NOT_RUN、解析/环境错误、
候选可写 reward 都不能产生正式分。复算与正式结果不一致时判 `FAIL`；必要材料缺失时判
`BLOCKED`。

## 10. 证据、历史和整改复验闭环

原始日志按精确字节保存并有 SHA256；派生、转码和脱敏文件另有身份。每个问题记录现象、直接
证据、影响、根因、修改对象、复验方法、新版本和剩余边界。题面、环境、Solution、Tests、
required testcase 或评分发生变化后，旧模型轨迹必须作废，并在新干净环境完整复验。历史“已修”
不能代替当前资产实测。

## 11. 镜像远端交付与甲方目标环境验证

按 [image-delivery-gate.md](image-delivery-gate.md) 完成远端拉取、甲方访问权限、目标兼容性、
新容器启动和同镜像标准 Harbor 执行。必须填写 `quality-review.json.image_delivery` 的目标
环境、实际镜像、解析 digest 和五项原始证据。只提交本地缓存镜像、Dockerfile 或本地 Oracle
成功日志不能通过。确认交付缺陷为 FAIL；网络/质检账号/目标信息不足为 BLOCKED，不能记模型 0。

## 12. 完整 Windows 系统和最低版本

按 [current-project-policy.md](current-project-policy.md) 登记实际系统版本、家族和 runtime 基础来源。
镜像版本至少 2019，优先 2025；Nano Server、Server Core、自定义额外裁剪系统禁止。填写
`windows_image_policy`，版本标签或自定义名称不能代替实际镜像和来源证据，仍须满足甲方兼容性。

## 13. Dockerfile 工具配置和成品容器功能

填写 `toolchain_in_image`，从任务和执行链实际调用盘点工具，逐项定位 Dockerfile 安装/离线部署
或基础自带工具的明确自检，并保留构建和成品容器功能探针证据。需要真实 Excel/COM 时不能
用普通文件处理库冒充。Dockerfile 文字、版本输出或 PATH 单独不能证明题目功能可执行。

## 14. 实际嵌套虚拟化执行

按 [nested-virtualization-gate.md](nested-virtualization-gate.md) 完成外层 VM/虚拟化扩展、内层
hypervisor、内层 Windows 启动和当前 jobs 绑定的原始证据审核，填写 `nested_virtualization`。
支持声明、CPU 能力、物理机 Hyper-V 参数和普通容器成功均不能证明嵌套。非嵌套实测为 FAIL，
拓扑或启动证据不足为 BLOCKED，环境故障不能计作模型 0。

## 证据和结论

每项至少提供一个具体文件、testcase ID、job 目录或 CLI 日志路径。采购手册扩展项应引用
`wip94-review`、`dynamic-d01-d20-review`、`score-recompute` 等逐项产物。结论规则：

- 十四项全部 `PASS`：质量门禁通过；
- 任一项 `FAIL`：整题 `FAIL`；
- 任一项证据不足、轨迹缺失或无法复核：整题 `BLOCKED`；
- 自动目录、模型、Oracle/NOP 检查已经失败时，质量复核不能把结果升级为通过。

返修原因使用口语化描述，先说实际现象和影响，再说需要补什么。可以附带文件名、job 和 testcase
作为证据，但不要只堆字段名、Hash 或脚本报错。

提交给入口的 `quality-review.json` 使用以下完整模板，十四个键缺一不可；所有 BLOCKED 和空字段
都须根据真实执行补齐，不能直接把模板当作质检结果：

```json
{
  "golden_nop_expected": {
    "status": "BLOCKED",
    "evidence": [],
    "notes": "Golden/NOP 得分和逐 testcase 终态符合预期"
  },
  "rubric_case_correctness": {
    "status": "BLOCKED",
    "evidence": [],
    "notes": "每项评分标准和每个 testcase 判分正确"
  },
  "testcase_contract_fairness": {
    "status": "BLOCKED",
    "evidence": [],
    "notes": "Testcase 严格对应题面并检查功能而非固定写法"
  },
  "hack_free": {
    "status": "BLOCKED",
    "evidence": [],
    "notes": "模型没有联网取答案、搜索 Golden 或绕过评分"
  },
  "windows_value": {
    "status": "BLOCKED",
    "evidence": [],
    "notes": "题目具备真实 Windows 反事实价值"
  },
  "scope_version_identity": {
    "status": "BLOCKED",
    "evidence": [],
    "notes": "范围、版本、公式和全部执行资产身份已冻结"
  },
  "wip94_complete": {
    "status": "BLOCKED",
    "evidence": [],
    "notes": "WIP 94 项已逐项登记并提供证据或 N/A 依据"
  },
  "dynamic_d01_d20_complete": {
    "status": "BLOCKED",
    "evidence": [],
    "notes": "采购手册 D01-D20 已逐项完成动态审计"
  },
  "independent_score_recompute": {
    "status": "BLOCKED",
    "evidence": [],
    "notes": "已从 required testcase 和冻结公式独立复算正式分数"
  },
  "evidence_retest_integrity": {
    "status": "BLOCKED",
    "evidence": [],
    "notes": "原始证据、历史版本、整改和干净复验已闭环"
  },
  "image_delivery": {
    "status": "BLOCKED",
    "evidence": [],
    "notes": "按 references/image-delivery-gate.md 核验原始日志；本地成功不替代甲方交付",
    "configured_image": "",
    "resolved_image_digest": "",
    "target_profile": {
      "windows_build": "",
      "architecture": "",
      "isolation": "",
      "can_build_images": null
    },
    "checks": {
      "remote_pull": {
        "status": "BLOCKED",
        "evidence": [],
        "notes": "实际成品镜像已显式从远端拉取，保留退出码和 digest"
      },
      "recipient_access": {
        "status": "BLOCKED",
        "evidence": [],
        "notes": "甲方可拉取的公开访问或私有仓库权限依据"
      },
      "target_compatibility": {
        "status": "BLOCKED",
        "evidence": [],
        "notes": "目标 Windows build、架构和实际隔离方式兼容性验证"
      },
      "clean_start": {
        "status": "BLOCKED",
        "evidence": [],
        "notes": "同一镜像的新容器启动并确认就绪"
      },
      "task_execution": {
        "status": "BLOCKED",
        "evidence": [],
        "notes": "同一镜像的标准 Harbor Oracle/NOP 和逐 testcase 证据"
      }
    }
  },
  "windows_image_policy": {
    "status": "BLOCKED",
    "evidence": [],
    "notes": "2019 及以上，优先 2025；Nano Server 和 Server Core 均禁止",
    "configured_image": "",
    "windows_build": null,
    "release_year": null,
    "family": "",
    "untrimmed": null,
    "runtime_bases": []
  },
  "toolchain_in_image": {
    "status": "BLOCKED",
    "evidence": [],
    "notes": "逐项登记任务、环境、Solution 和 Tests 实际需要的工具，并核验 Dockerfile 和容器内功能",
    "tools": []
  },
  "nested_virtualization": {
    "status": "BLOCKED",
    "evidence": [],
    "notes": "必须实际使用嵌套虚拟化；Hyper-V 参数或 CPU 支持不能代替拓扑与内层运行证据",
    "configured_image": "",
    "task_id": "",
    "task_version": "",
    "task_hash": "",
    "virtualization_depth": null,
    "outer_guest_id": "",
    "outer_hypervisor": "",
    "inner_hypervisor": "",
    "virtualization_extensions_exposed": null,
    "inner_virtualization_enabled": null,
    "task_runtime_in_nested_layer": null,
    "checks": {
      "outer_guest": {
        "status": "BLOCKED",
        "evidence": [],
        "notes": "外层 hypervisor 与 L1 Windows VM 标识/拓扑的原始证据"
      },
      "capabilities_exposed": {
        "status": "BLOCKED",
        "evidence": [],
        "notes": "外层暴露虚拟化扩展且内层 hypervisor 实际启用"
      },
      "inner_runtime": {
        "status": "BLOCKED",
        "evidence": [],
        "notes": "L1 内实际启动 L2 Windows VM/隔离容器的命令、日志和终态"
      },
      "job_binding": {
        "status": "BLOCKED",
        "evidence": [],
        "notes": "当前 Task/镜像和实际模型、Oracle/NOP jobs 均绑定嵌套执行层"
      }
    }
  }
}
```

所有项保留 BLOCKED 作为待填写模板，完成实际验证后才能填写 PASS；自动入口检查镜像、版本、
工具证据结构和当前题包绑定，不替代人工打开原始证据进行复核。
