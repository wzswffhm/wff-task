# Windows Harbor 完整质检报告

结论：**PASS**

- 交付目录：`PASS`
- 四模型门禁：`PASS`
- 四模型原始 jobs：`PASS`
- Oracle/NOP：`PASS`
- 十四项人工质量复核：`PASS`

## 交付目录

- 通过

## 模型门禁

- 通过

## 模型 jobs

- 通过

## 十四项人工质量硬门禁

- **Golden/NOP 得分和逐 testcase 终态符合预期**：`PASS`
  - 证据：jobs/ctl-oracle-1..3/verifier/result.json：status=VALID score=1 total=20 passed=20 invalid=0，三轮独立新建 job 与干净容器
  - 证据：jobs/ctl-nop-1..3/verifier/result.json：status=VALID score=0 total=20 passed=10 failed=10 invalid=0，三轮一致
  - 证据：NOP 的 10 条失败全部落在 F2P 组，P2P 10 条全过；与「缺陷版在稀疏语义上必失败、在回归面必通过」的设计逐条吻合
  - 证据：全部 6 个控制 job 的 task_checksum 与第 12 个模型 job 相同，均为 5fbd308e1cb6b37a
  - 说明：Golden 全 1、no-change 全 0，逐 testcase 终态与预期一致；控制轮在本轮 L1 环境中重跑，非复用旧结果
- **每项评分标准和每个 testcase 判分正确**：`PASS`
  - 证据：tests/judge.toml 的 source_sha256 与 tests/rubric.json 实际 sha256 均为 cfa42e47e8c29842678c7b04728244c9d752cff0fd0622c3e5a53975c5f03d00，两者一致
  - 证据：tests/required_testcases.json 为 20 条数组（F2P 10 / P2P 10），与 rubric.json、judge.toml 的 test_ids 集合完全相同
  - 证据：tests/aggregate_results.ps1：未观测用例记 INVALID 而非 FAIL，invalid>0 时 run_validity=INVALID 且 exit 2，不给分
  - 证据：tests/run_tests.ps1：passed→PASS、failed→FAIL、error/skipped/未采集→INVALID；collected=0 判 INVALID 并输出空分数
  - 证据：正式分二值：20 条 required 全 PASS 才为 1；12 个 job 的 verifier/result.json、reward.txt、result.json:verifier_result 三方数值一致
  - 证据：独立复算：从 6 个模型 job 逐轮累加 testcase 通过数得 Qwen=52、Opus=60，与 qc 侧统计一致
  - 说明：判分链为二值、无权重、无部分分；缺测一律 INVALID，不会把基础设施问题折算成模型 0 分
- **Testcase 严格对应题面并检查功能而非固定写法**：`PASS`
  - 证据：instruction.md 的验收条款与 tests/required_testcases.json 的 20 条一一对应，F2P 覆盖稀疏语义、P2P 覆盖回归面
  - 证据：隐藏套件只断言可观测行为（磁盘占用、已分配区间、错误 kind），不 grep 源码、不要求特定函数名或调用序列
  - 证据：参考实现与缺陷实现在同一套用例下分别得到 20/20 与 10/20，说明断言区分的是行为而非写法
  - 证据：evidence/author-design/contract-map.json 给出 20 个用例到题面条款的完整映射
  - 说明：断言对象是可观测行为；等价实现（不同内部写法）只要行为正确即可通过
- **模型没有联网取答案、搜索 Golden 或绕过评分**：`PASS`
  - 证据：6 份模型 trajectory.jsonl 全文检索 curl/wget/Invoke-WebRequest/Invoke-RestMethod/git clone|fetch|pull/pip install/choco/winget 命中数均为 0
  - 证据：6 份轨迹的 CJK 字符数分别为 1416/1327/1428/1487/1331/1328，均未出现禁止的「中文口语化提示：」前缀
  - 证据：隐藏套件不随包进入 agent 容器：Harbor 仅在 verifier 阶段把 tests/ 挂到容器内；agent 阶段工作区为 C:\testbed
  - 证据：评测器不采信候选返回值：隐藏套件自行 CreateFileW + DeviceIoControl + GetCompressedFileSizeW + fsutil 观测
  - 证据：environment/validate_environment.ps1 在 agent 工作区发现 oracle|golden|reference|hidden|rubric|solution|reward 命名文件即判 INVALID
  - 证据：模型轮封顶 40 步；6 份 patch.diff 均未触碰 tests/ 评分脚本、未修改 rubric/reward
  - 说明：题面行为约束、环境层能力探测、评测器自持内核对象三层隔离，未发现任何取答案或绕过评分的行为
- **题目具备真实 Windows 反事实价值**：`PASS`
  - 证据：依据公开上游缺陷 CPython issue 39910（os.ftruncate on Windows should be sparse）；容器内实测 Python 3.12.9 上 os.truncate(64MB) 后 compressed=67108864、fsutil queryflag 报 NOT sparse
  - 证据：反事实：实现只能由 FSCTL_SET_SPARSE、SetFilePointerEx+SetEndOfFile、FSCTL_QUERY_ALLOCATED_RANGES、GetCompressedFileSizeW/FILE_STANDARD_INFO.AllocationSize 构成，跨平台无对等物
  - 证据：instruction.md 含逐字排他声明：目标平台是真实 Windows + NTFS，验收不使用其他操作系统
  - 证据：environment/validate_environment.ps1 断言 File System Name : NTFS 与 Supports Sparse files，不满足即 INVALID
  - 证据：L2 容器内实测 os build 10.0.20348.5761，稀疏语义由真实 NTFS 提供，非 mock
  - 说明：Windows 反事实成立：离开 NTFS 稀疏语义该题无法表达，Linux/WSL 无等价实现
- **范围、版本、公式和全部执行资产身份已冻结**：`PASS`
  - 证据：task_id = wfflab__wsparse-215，task_version = 1.0.1，目录名 wfflab__wsparse-215-v1.0.1-delivery 与之一致
  - 证据：task.toml 的 docker_image = ghcr.io/wzswffhm/wfflab-windows:wsparse-215-1.0.1，与本次实际运行镜像逐字相同
  - 证据：tests/required_testcases.json 为 20 条（F2P 10 / P2P 10），与 rubric.json、judge.toml 的 test_ids 集合完全一致
  - 证据：12 个 job 的 task_checksum 唯一：5fbd308e1cb6b37a51240bfb38b6ae2dc251319af5874fdf6e72ce4ad4a01da1
  - 证据：包内非 jobs 文件 86 个；rubric sha256 = cfa42e47e8c29842678c7b04728244c9d752cff0fd0622c3e5a53975c5f03d00 与 judge.toml 声明一致
  - 说明：交付身份、镜像引用、required 集合、job checksum 全部冻结且互相绑定；跑分期间未修改包内任何字节
- **WIP 94 项已逐项登记并提供证据或 N/A 依据**：`PASS`
  - 证据：harbor-windows/_qc_runs/wsparse-build/wip94-review-v101.json：total_items=94、items 长度 94，ID 集合与 FC-01..13 / QD-SP-01..18 / QD-SO-01..07 / QD-IN-01..06 / ENV-01..14 / VV-01..36 完全吻合
  - 证据：状态分布：PASS 81 / FAIL 1 / FLAG 3 / BLOCKED 8 / N/A 1（共计 94）
  - 证据：已针对 1.0.1 重新绑定：task_version、目录名、task_checksum 全部更新为当前值（5fbd308e1cb6b37a）
  - 证据：FAIL/FLAG/BLOCKED 各项均写明具体对象与依据，未以总分或脚本摘要代替逐项判定
  - 证据：N/A 项给出适用性依据（本题无异步服务启动与就绪条件）
  - 说明：94 项逐条留行并提供可定位证据；本门禁要求登记完整与依据充分，不要求 94 项全部 PASS
- **采购手册 D01-D20 已逐项完成动态审计**：`PASS`
  - 证据：harbor-windows/_qc_runs/wsparse-build/dynamic-d01-d20-review-v101.json：total_items=20、items 长度 20，状态 PASS 18 / N/A 2
  - 证据：编号来源：01-质检执行手册.md 第 5 节（5.1 D01–D04、5.2 D05–D10、5.3 D11–D14、5.4 D15–D17、5.5 D18–D20）
  - 证据：D05 要求实际下发：6/6 模型轮 trajectory.jsonl 的 user 消息与 instruction.md 逐字相同
  - 证据：D19 失败归因：唯一失分轮 model-qwen-2 失败 8 条（5 F2P + 3 P2P），同环境 Oracle 3/3、Opus 3/3 均 20/20 且 invalid=0 → 归因 MODEL_FAILURE
  - 证据：D18 独立复算：12 轮 score 与 verifier/result.json、reward.txt、result.json:verifier_result.rewards.reward 全部一致
  - 证据：D12 身份：12 个 job 的 task_checksum 唯一 = 5fbd308e1cb6b37a
  - 证据：D15/D16/D17：6 份轨迹联网工具命中 0；6 份 patch.diff 未触碰评分脚本与 reward
  - 说明：20 项已逐项动态审计并附实读证据，无 BLOCKED 无 FAIL；两条 N/A 已写明适用性依据
- **已从 required testcase 和冻结公式独立复算正式分数**：`PASS`
  - 证据：从 jobs/model-qwen-1..3/verifier/result.json 逐条统计：[1, 0, 1] → model_score_sum = 2，testcase_pass_sum = 52
  - 证据：从 jobs/model-opus-1..3/verifier/result.json 逐条统计：[1, 1, 1] → model_score_sum = 3，testcase_pass_sum = 60
  - 证据：区分度主条件 Opus(3) > Qwen(2) 严格成立
  - 证据：testcase 累计 Opus(60) > Qwen(52)，与主分差方向一致
  - 证据：12 个 job 的 reward.txt / verifier/result.json:score / result.json:verifier_result.rewards.reward 三处数值全部一致
  - 说明：正式分由 required 集合与二值规则独立复算，两条路径（本机统计 / QC 自算）结果相同
- **原始证据、历史版本、整改和干净复验已闭环**：`PASS`
  - 证据：本轮为 L1 内干净重跑：先把外部产生的 jobs/ 整体隔离到 jobs-outside-L1-*，清空 controls/ 与 model-rounds/ 后重新执行 12 个 job
  - 证据：12 个 job 的 task_checksum 完全一致（5fbd308e1cb6b37a），说明全部运行绑定在同一版冻结包上
  - 证据：控制 3+3 轮与模型 6 轮各自独立新建 job 与干净容器；每轮单独 --job-name
  - 证据：两处 relay 截断轮（215 Opus#1 output_tokens=1、216 相关轮）已按「中转空响应」判为 INVALID 并隔离，重跑后才计入，未把环境故障记成模型 0 分
  - 证据：全部原始产物随包交付：job 目录、verifier 报告、trajectory.jsonl、patch.diff、test-stdout.txt
  - 说明：原始证据、无效轮次隔离记录与干净复验已闭环；旧结果未复用
- **成品镜像远端可获取、甲方有权限、目标环境可启动并执行题目**：`PASS`
  - 证据：ghcr.io 匿名 token + manifest 请求返回 HTTP 200，digest=sha256:d29e10e41813338ec8d5a52de8c198469b0c380dcfaaff2f48ac4fa29f7211cf（delivery-evidence-101/ghcr-anonymous-access-101.txt）
  - 证据：GitHub API 查询 /user/packages/container/wfflab-windows 返回 visibility=public，任何人可匿名 pull
  - 证据：L1 内 L2 容器实测 OS build 10.0.20348.5761，架构 amd64，隔离方式 windows/process
  - 证据：甲方目标环境无构建能力（can_build_images=false），故交付预构建镜像而非 Dockerfile 现场构建
  - configured_image："ghcr.io/wzswffhm/wfflab-windows:wsparse-215-1.0.1"
  - resolved_image_digest："sha256:d29e10e41813338ec8d5a52de8c198469b0c380dcfaaff2f48ac4fa29f7211cf"
  - target_profile：{"windows_build": 20348, "architecture": "amd64", "isolation": "process", "can_build_images": false}
  - remote_pull：`PASS`；成品镜像可从远端显式解析，退出码与 digest 均已留存
    - 证据：docker manifest inspect ghcr.io/wzswffhm/wfflab-windows:wsparse-215-1.0.1 返回 0
    - 证据：delivery-evidence-101/ghcr-anonymous-access-101.txt 记录 HTTP=200 与 digest
  - recipient_access：`PASS`；包为 public，甲方无需我方账号即可拉取
    - 证据：GitHub API：/user/packages/container/wfflab-windows → visibility=public
    - 证据：匿名（无凭据）token 换取成功且 manifest 返回 200
  - target_compatibility：`PASS`；镜像为 windows/amd64，可在 Server 2022 宿主以 process 隔离运行
    - 证据：L2 容器内 ver 输出 Microsoft Windows [Version 10.0.20348.5761]
    - 证据：docker info 显示 OSType=windows、Isolation=process、ServerVersion=27.3.1
  - clean_start：`PASS`；同一镜像的新容器可干净启动并立即可用
    - 证据：L1 内以同一镜像启动新容器并执行 cmd /c ver，正常返回版本号
    - 证据：工具链探针容器内 git/python/pip/pytest 均正常执行
  - task_execution：`PASS`；镜像在嵌套 L1 层完成标准 Oracle/NOP 与全部模型轮，逐 testcase 证据随包
    - 证据：同一镜像执行 Harbor Oracle 3 轮（VALID/1，20/20）与 NOP 3 轮（VALID/0，10/20）
    - 证据：同一镜像执行 Qwen 3 轮 + Opus 3 轮，逐 testcase 结果见 jobs/*/verifier/result.json
- **Windows 镜像不早于 2019，优先 2025，禁止 Nano Server/Server Core 和额外裁剪**：`PASS`
  - 证据：基础层为 mcr.microsoft.com/windows/server:ltsc2022，属完整 Windows Server 容器镜像，build 20348 ≥ 17763
  - 证据：未使用 nanoserver / servercore 变体；Dockerfile 无额外裁剪步骤
  - 证据：L2 容器内 ver 实测 10.0.20348.5761
  - 说明：镜像家族为完整 Windows Server 2022（LTSC2022），满足不早于 2019 且未裁剪
  - configured_image："ghcr.io/wzswffhm/wfflab-windows:wsparse-215-1.0.1"
  - windows_build：20348
  - release_year：2022
  - family："windows-server"
  - untrimmed：true
  - runtime_bases：[{"image": "mcr.microsoft.com/windows/server:ltsc2022", "windows_build": 20348, "release_year": 2022, "family": "windows-server", "untrimmed": true, "evidence": ["environment/Dockerfile:20 FROM mcr.microsoft.com/windows/server:ltsc2022（完整 Windows Server 镜像，非 Nano/Server Core）", "L2 容器内 ver → 10.0.20348.5761，与 LTSC 2022 一致"]}]
- **实际使用的工具通过 Dockerfile 配置，并在成品容器内完成版本和功能验证**：`PASS`
  - 证据：全部工具均在 environment/Dockerfile 中声明并从 environment/vendor/ 的离线资产安装，构建无网络访问
  - 证据：L2 容器内逐项功能探针实测通过（delivery-evidence-101/toolchain-probes-101.txt）
  - 说明：五个工具全部由 Dockerfile 从随包离线资产安装，并在成品容器内完成版本与功能探针验证
  - tools：[{"name": "MinGit", "version": "2.56.0.2", "required_by": "environment/Dockerfile 的基线提交与 git 状态；solution 与 tests 需要 git 操作", "dockerfile_location": "environment/Dockerfile:24-28（COPY vendor/MinGit-2.56.0.2-64-bit.zip + Expand-Archive）", "functional_probe": "docker run --rm <image> cmd /c \"C:\\Git\\cmd\\git.exe --version\" → git version 2.56.0.windows.2", "provisioning_kind": "installed", "provisioning_evidence": ["environment/vendor/MinGit-2.56.0.2-64-bit.zip 随包交付，Dockerfile:26-28 解压到 C:\\Git"], "runtime_evidence": ["delivery-evidence-101/toolchain-probes-101.txt: git version 2.56.0.windows.2"], "status": "PASS"}, {"name": "Python", "version": "3.12.9", "required_by": "workspace 包与隐藏测试套件的运行时", "dockerfile_location": "environment/Dockerfile:31-38（COPY vendor/python-3.12.9-embed-amd64.zip + Expand-Archive 到 C:\\Python312）", "functional_probe": "docker run --rm <image> cmd /c \"C:\\Python312\\python.exe --version\" → Python 3.12.9", "provisioning_kind": "installed", "provisioning_evidence": ["environment/vendor/python-3.12.9-embed-amd64.zip 随包交付，Dockerfile:32-36 解压并改 _pth"], "runtime_evidence": ["delivery-evidence-101/toolchain-probes-101.txt: Python 3.12.9"], "status": "PASS"}, {"name": "pip", "version": "26.0.1", "required_by": "从离线 wheelhouse 安装 pytest 与 pytest-json-report", "dockerfile_location": "environment/Dockerfile:45-52（解包 pip wheel 到 site-packages 后 pip install --no-index）", "functional_probe": "docker run --rm <image> cmd /c \"C:\\Python312\\python.exe -m pip --version\" → pip 26.0.1 from C:\\Python312\\Lib\\site-packages\\pip", "provisioning_kind": "installed", "provisioning_evidence": ["environment/vendor/wheels/pip-*.whl 随包交付，Dockerfile:48-50 解压即用（无 get-pip.py 网络下载）"], "runtime_evidence": ["delivery-evidence-101/toolchain-probes-101.txt: pip 26.0.1"], "status": "PASS"}, {"name": "pytest", "version": "8.3.5", "required_by": "tests/run_tests.ps1 的隐藏测试套件执行器", "dockerfile_location": "environment/Dockerfile:51（pip install --no-index 'pytest==8.3.5'）", "functional_probe": "docker run --rm <image> cmd /c \"C:\\Python312\\python.exe -m pytest --version\" → pytest 8.3.5; pip show pytest → Version: 8.3.5", "provisioning_kind": "installed", "provisioning_evidence": ["environment/vendor/wheels/ 内 wheel 固定版本，Dockerfile:51 从 --find-links C:\\vendor\\wheels 安装"], "runtime_evidence": ["delivery-evidence-101/toolchain-probes-101.txt: pytest 8.3.5, imported from C:\\Python312\\Lib\\site-packages\\pytest\\__init__.py"], "status": "PASS"}, {"name": "pytest-json-report", "version": "1.5.0", "required_by": "tests/run_tests.ps1 依赖 --json-report 产出结构化结果，供 aggregate_results.ps1 汇总", "dockerfile_location": "environment/Dockerfile:51（pip install --no-index 'pytest-json-report==1.5.0'）", "functional_probe": "docker run --rm <image> cmd /c \"C:\\Python312\\python.exe -m pytest --version --version\" → registered third-party plugins: pytest-json-report-1.5.0", "provisioning_kind": "installed", "provisioning_evidence": ["environment/vendor/wheels/ 内 wheel 固定版本，Dockerfile:51 安装"], "runtime_evidence": ["delivery-evidence-101/toolchain-probes-101.txt: registered third-party plugins: pytest-json-report-1.5.0 at C:\\Python312\\Lib\\site-packages\\pytest_jsonreport\\plugin.py"], "status": "PASS"}]
- **实际使用嵌套虚拟化，外层 VM/扩展暴露/内层运行和当前 jobs 证据完整**：`PASS`
  - 证据：delivery-evidence-101/L0-host-and-L1-vm.json：L0 HypervisorPresent=True；L1 ExposeVirtualizationExtensions=True
  - 证据：delivery-evidence-101/L1-guest-facts.json：L1 Manufacturer=Microsoft Corporation、Model=Virtual Machine、build 20348、DeviceGuard VBS=2
  - 证据：L1 内 docker info 返回 OSType=windows / Isolation=process；12 个 job 的容器均由该 daemon 启动
  - 证据：12 个 job 的 task_checksum 唯一 = 5fbd308e1cb6b37a51240bfb38b6ae2dc251319af5874fdf6e72ce4ad4a01da1，全部绑定同一冻结 Task
  - 说明：L0 物理机 → L1 Hyper-V Windows VM → L2 Windows 容器，深度 2；扩展暴露与内层运行均有原始证据
  - configured_image："ghcr.io/wzswffhm/wfflab-windows:wsparse-215-1.0.1"
  - task_id："wfflab__wsparse-215"
  - task_version："1.0.1"
  - task_hash："90ee067b0ae6aa29022cf504db5987c08c3fac19cf131ffa9432ecf8225fbc73"
  - virtualization_depth：2
  - outer_guest_id："L1-WinSrv2022 (WIN-C5QOITR5RI8), Gen1 VM, 6 vCPU / 12 GB"
  - outer_hypervisor："Microsoft Hyper-V on L0 Windows 11 Pro build 26200 (HypervisorPresent=True)"
  - inner_hypervisor："Windows container runtime (Docker 27.3.1, windows/process) inside L1"
  - virtualization_extensions_exposed：true
  - inner_virtualization_enabled：true
  - task_runtime_in_nested_layer：true
  - checks：{"outer_guest": {"status": "PASS", "evidence": ["delivery-evidence-101/L0-host-and-L1-vm.json：l0_computer=CHINAMI-IB8SDOI, l0_build=26200, hypervisor_present=true", "同文件 l1_vm 段：name=L1-WinSrv2022, state=Running, generation=1, processor_count=6, memory_assigned_gb=12", "delivery-evidence-101/L1-guest-facts.json：computer=WIN-C5QOITR5RI8, manufacturer=Microsoft Corporation, model=Virtual Machine"], "notes": "L0 为物理 Windows 11 宿主，L1 是其中 Gen1 Hyper-V 虚拟机，客体内省信息确认虚拟化身份"}, "capabilities_exposed": {"status": "PASS", "evidence": ["Get-VMProcessor L1-WinSrv2022 → ExposeVirtualizationExtensions=True", "L1 内 Win32_DeviceGuard.VirtualizationBasedSecurityStatus=2（已启用）"], "notes": "外层已向 L1 暴露虚拟化扩展，且 L1 内虚拟化能力实际处于启用状态"}, "inner_runtime": {"status": "PASS", "evidence": ["L1 内 docker version → 27.3.1；docker info → OSType=windows, Isolation=process", "L1 内 docker run --rm mcr.microsoft.com/windows/server:ltsc2022 cmd /c \"echo L2-OK && ver\" 返回 L2-OK 与 10.0.20348.5761", "全部 12 个 job 的容器（harbor-*）均在 L1 的 docker daemon 上创建并结束"], "notes": "L2 为 L1 内的 Windows 隔离容器，命令、日志与终态齐备"}, "job_binding": {"status": "PASS", "evidence": ["12 个 job 的 task_checksum 唯一 = 5fbd308e1cb6b37a51240bfb38b6ae2dc251319af5874fdf6e72ce4ad4a01da1", "全部 job 的 result.json 指向 L1 路径 C:\\Users\\Administrator\\Desktop\\wff-task\\harbor-windows\\_qc_runs\\*-build\\model-rounds|controls\\jobs", "jobs/*/agent/model-result.json 的 runner 路径与 L1 内 _qc_runs\\*-build\\harbor_agent 一致"], "notes": "当前 Task、镜像与全部模型/Oracle/NOP job 均绑定在 L1 嵌套执行层产生"}}

## 原始证据

- `harbor/`：真实 Oracle/NOP 报告、命令、job 和 CLI 日志
- `delivery-layout.json`：目录与 task_id/version/hash 绑定
- `model-gate.json`：四模型次数、分数和区分度
- `model-jobs.json`：12 个 Harbor jobs（6 个模型、3 个 Oracle、3 个 NOP）交叉校验
- 人工证据：WIP 94 项、D01-D20、逐项证据链、Hack 事件和独立复算文件
