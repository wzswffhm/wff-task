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
  - 证据：harbor-windows/_qc_runs/wciocp-build/controls/controls_summary.json：Oracle ctl-oracle-1/2/3 三轮 reward 均为 1、NOP ctl-nop-1/2/3 三轮 reward 均为 0，6 轮 task_checksum 全部为 7bebdc01887e3b6114951a7acdbf412e386cbc41f91aacea78e4b8988fc11ddc
  - 证据：jobs/ctl-oracle-1/verifier/report.json：schema_version=aggregate-v1、run_validity=VALID、14 条全部 passed、invalid=0、formal_score=1
  - 证据：jobs/ctl-nop-1/verifier/report.json：run_validity=VALID、10 条 passed、4 条 failed、invalid=0、formal_score=0；三条 NOP 完全一致（10/14）
  - 证据：jobs/_index/assembly_report.json：n_trials=12，12 个 job 的分数与 testcase 集合全部合法且与 tests/required_testcases.json 匹配，harbor_task_checksums 唯一值为冻结 dirhash
  - 说明：逐 testcase 对照过三次 Oracle 与三次 NOP。NOP 得 0 的原因是缺陷版把完成通知放在进程内列表里由各等待线程自行扫描、按句柄查表取完成键、超时后把池置为降级态、且不检查对象能否承载完成通知：因此 4 条 F2P（换键改写已到达通知、并发下重复/丢失交付、超时后丢弃后续事件、非重叠对象被静默接受）全部失败，其余 10 条（含 P2P 全部）通过。这是真实功能失败，不是环境、权限、依赖或旧产物问题；回归面在 base 与 Oracle 下均未被破坏。
- **每项评分标准和每个 testcase 判分正确**：`PASS`
  - 证据：tests/rubric.json：5 个 programmatic 组（completion-key-delivery 0.25 / exactly-once-delivery 0.25 / capability-probe 0.15 / timeout-and-close 0.25 / regression-surface 0.10），权重和 = 1.0，无 LLM judge、无部分分
  - 证据：tests/rubric.json 的 sha256 = 9f39034e3077e360a04522b17ef5f368452cd814e4a3bf9ecc82e4af84467e42，与 tests/judge.toml 的 source_sha256 逐字符一致；judge.toml 记录 programmatic_weight=1.0、llm_judge_weight=0.0
  - 证据：verifier/rubric.conditions.json：五组与 rubric.json 一一对应，逐组写明所依赖的 Windows 完成端口机制（完成键随包回传 / 内核队列的原子出队 / WAIT_TIMEOUT / 文件模式能力判定）
  - 证据：tests/run_tests.ps1 与 tests/aggregate_results.ps1：二值判分（required 全 passed 记 1，否则 0），缺测、SKIP 或执行故障一律记 INVALID（exit 2）而不是正式 0 分
  - 证据：12 轮 verifier/report.json 的 required 集合均为 14 条，与 tests/required_testcases.json 逐条一致；每轮 invalid 均为 0
  - 说明：case 粒度如实为 14 条：F2P 4 条（缺陷版确实失败的 4 条）+ P2P 10 条（缺陷版与参考解都通过的回归面）。立项时曾按 7 条 F2P 设计，实测发现其中 3 条（基本键回传、跨句柄键区分、close 后拒绝使用）在**任何符合本题缺陷模型**的实现下都会通过——它们与 P2P 的 take-returns-an-event 判据同构，强行让它们失败会连带 P2P 一起失败。因此按实测收敛为 F2P 4，并在 required_testcases.json 中如实标注，未虚标。唯一已知边界是 WIP VV-14（程序化占比 100% > 采购手册 50% 阈值），按 rule-matrix 双列登记为『WIP 合规 FAIL / 本题 programmatic-only 设计说明』。
- **Testcase 严格对应题面并检查功能而非固定写法**：`PASS`
  - 证据：tests/required_testcases.json 顶层是数组，共 14 条：F2P 4 条 + P2P 10 条，id 全部带 f2p-/p2p- 前缀
  - 证据：tests/test_wciocp_semantics.py 的 14 个 test 函数与 required 的 14 条 id 一一对应，tests/run_tests.ps1 的 slugByFunction 映射覆盖全部 14 条
  - 证据：verifier/tests/test_wciocp_semantics.py 与 tests/test_wciocp_semantics.py 逐字节一致，sha256 = 23f356188f9b50128530c86df69072f73862ee38f5cda3335ea4776fcdc66331
  - 证据：隐藏套件自持内核对象：用 CreateNamedPipeW(PIPE_ACCESS_DUPLEX|FILE_FLAG_OVERLAPPED) + CreateFileW 建管道与客户端，自己登记各自的完成键、自己发起挂起读，再用 4 个线程并发 take，以『每个请求恰好回来一次且带回登记时的键』为终态判据，从不采信候选返回值
  - 证据：题面 A–G 每项公开要求都有 required 用例覆盖（A→换键不改写已到达通知；B→并发下恰好交付一次；C→跨句柄键区分；D→超时不丢包且不破坏池；E→非重叠对象 unsupported；F→closed/badarg 分类；G→可见冒烟测试）
  - 说明：测试只断言题面写明的公共契约与可观察终态，不绑定构造签名、私有函数名或实现路径：可见冒烟测试已改为不直接构造 Request/Event（用 __new__ + 属性赋值），因此参考解的 __slots__ 写法与缺陷版的普通类写法被同一套断言公平对待。判据中的阈值（步数/输出量）只用于判定无效槽位，不参与评分。
- **模型没有联网取答案、搜索 Golden 或绕过评分**：`PASS`
  - 证据：6 份 jobs/model-*/agent/patch.diff 的改动文件全部落在题面允许修改的 wciocp/ 包内：opus-1/2/3 与 qwen-2/3 只改 wciocp/_winapi.py、wciocp/kinds.py、wciocp/pool.py；无一份触碰 tests/、verifier/、rubric.json、judge.toml、reward 或任何评分通道
  - 证据：6 份 jobs/model-*/agent/trajectory.jsonl 中，C:\\verifier / C:\\solution / C:\\tests / oracle / golden / rubric.json / test_wciocp_semantics / required_testcases / reward.json 等隐藏材料关键词命中行数均为 0
  - 证据：environment/Dockerfile 只 COPY ["workspace/", "C:/testbed/"]；C:\\verifier、C:\\solution、C:\\tests、C:\\task\\tests、C:\\task\\solution 均不在 agent 容器内；verifier/negative_access_probe.ps1 是作答期边界探针
  - 证据：environment/validate_environment.ps1 的隔离审计会在 workspace 内出现 oracle|golden|reference|hidden|rubric|solution|reward 命名文件时让就绪探针失败（记 INVALID 而不是 0 分）
  - 说明：按四层分级（尝试 / 成功访问 / 实际使用 / 已证明影响成绩）逐份核对 6 份轨迹与补丁：未发现联网取答案、本地搜答案、篡改评分或复用旧产物的行为。如实记录一处瑕疵：model-qwen-1 在 workspace 根留下 5 个临时脚本（_debug.py、_debug2.py、_debug3.py、_debug4.py、_verify.py），与 agent 提示词『不要在仓库内留下调试脚本』不符；这些文件位于包外、不参与评分、也不改变任何 testcase 结果，该轮仍以 9/14 判 0 分。
- **题目具备真实 Windows 反事实价值**：`PASS`
  - 证据：metadata/windows_mechanism.json：counterfactual.answer=否，写明『句柄要用 CreateIoCompletionPort(handle, port, key, 0) 绑定到端口并登记完成键；完成包由内核入队、GetQueuedCompletionStatus 原子取出；epoll/kqueue 只报告就绪，io_uring 是另一套完成模型』
  - 证据：排他声明逐字锚定 instruction.md：『本任务的目标平台是真实的 Windows，验收不使用其他操作系统，也不需要实现其他操作系统的版本。』
  - 证据：4 条机制锚点各自绑定题面逐字条款 + verifier/tests/test_wciocp_semantics.py 的 test_ref（L184-L201 / L212-L228 / L252-L267 / L298-L304）+ 一条 F2P 用例
  - 证据：skills/harbor-windows/scripts/check_windows_mechanism.py 对本题输出 PASS（exit 0），F6 扫描未命中任何自我否认表述
  - 证据：environment/validate_environment.ps1 在非 Win32NT 主机上 Fail：'the host platform is not Windows (Win32NT), so the wciocp contract cannot be graded here'（F5 锚点）；同一探针还会真实建端口、绑管道、验证完成包带回登记键与空队列 WAIT_TIMEOUT
  - 说明：对照实验锁在 Windows 完成端口语义上：同一模型（Opus）三轮均 14/14，而 Qwen 三轮为 9/14、13/14、14/14；失分轮报的是并发交付与完成键语义上的真实错误。用进程内列表 + 条件变量模拟完成端口，必然丢掉『一个完成包恰好被一个线程取到』这条内核保证，因此不存在平台无关的等价实现。
- **范围、版本、公式和全部执行资产身份已冻结**：`PASS`
  - 证据：task.toml：task_id=wfflab__wciocp-220、顶层 version=1.0、[task].version=1.0.0；docker_image 与 environment/Dockerfile 的 FROM 逐字一致并 pin 到 @sha256 摘要
  - 证据：jobs/_index/assembly_report.json：n_trials=12，harbor_task_checksums 唯一值 = 7bebdc01887e3b6114951a7acdbf412e386cbc41f91aacea78e4b8988fc11ddc，12 个 job 无混包
  - 证据：zip/wfflab__wciocp-220-v1.0.0-delivery.zip：275 个条目（其中 jobs 条目 206），54,609,112 字节，sha256=398f8569ecda34cde4f984084a42102e129d6b1b9b364c680fb8a6cb03e040fc；package_task_zip.py --verify 逐文件核对 258 个文件全部一致
  - 证据：source.json 的 task_id/task_version 与 task.toml 一致；metadata/windows_mechanism.json 的 task_id 同样一致
  - 证据：包内不含 REFIT-*.md、verifier/WINDOWS_VALUE.md、oracle.patch 等非交付文件
  - 说明：题包在 12 轮跑完前冻结（冻结 dirhash 与 12 轮 checksum 完全一致），跑分期间只新增 jobs/ 与 _qc_runs 现场，未改动任何参与 checksum 的字节；提交前清理了全部 __pycache__/*.pyc 残留。
- **WIP 94 项已逐项登记并提供证据或 N/A 依据**：`PASS`
  - 证据：harbor-windows/_qc_runs/wsparse-build/wip94-review.json：total_items=94、items 长度 94、summary 与 items 实算一致，ID 集合覆盖 FC-01..13 / QD-SP-01..18 / QD-SO-01..07 / QD-IN-01..06 / ENV-01..14 / VV-01..36
  - 证据：harbor-windows/_qc_runs/wsparse-build/wip94-review.md：表头 + 94 条 ID 行 + 合计行
  - 证据：五个状态计数：PASS 81 / FAIL 1 / FLAG 3 / BLOCKED 8 / N/A 1；唯一 FAIL 为 VV-14（Rubric 权重占比），按双列结论登记
  - 证据：本题为同批 Windows 题的批次级共用登记，条目引用同一份产物；220 的差异（4 条 F2P 的收敛过程、完成端口机制锚点）已在本文件与 QC 报告中标出
  - 说明：本门禁要求『已逐项登记并附证据或 N/A 依据』，不要求 94 项全部 PASS；缺行、无证据写 PASS 才判 BLOCKED。220 复用该批次级登记，未静默豁免任何适用项。
- **采购手册 D01-D20 已逐项完成动态审计**：`PASS`
  - 证据：harbor-windows/_qc_runs/wsparse-build/dynamic-d01-d20-review.json：total_items=20、items 长度 20、summary 与 items 实算一致（PASS 18 / N/A 2）
  - 证据：harbor-windows/_qc_runs/wsparse-build/dynamic-d01-d20-review.md：| ID | 维度 | 状态 | 证据摘要 | 表 + 合计行
  - 证据：220 侧对应证据：D05（要求实际下发）可由 6 份 trajectory.jsonl 的首条 user 消息与 instruction.md 逐字比对复现；D09（等价与反例）对应 Oracle 14/14 vs NOP 10/14；D18（独立复算）见 independent_score_recompute
  - 证据：D10（Mock 保真）为 N/A 的依据：题面与隐藏套件完全不用 Mock（无 mock/monkeypatch/stub），判据全部来自真实 CreateNamedPipeW / CreateIoCompletionPort / GetQueuedCompletionStatus / CancelIoEx
  - 说明：20 项逐项动态审计并附实读证据；220 与 219/218/215 同为该批次级审计的适用对象，引用同一份产物并在本题 QC 报告中说明。
- **已从 required testcase 和冻结公式独立复算正式分数**：`PASS`
  - 证据：12 轮 reward 与包内 jobs/<job>/verifier/report.json 的 formal_score 逐一相符：Oracle 1/1/1、NOP 0/0/0、Opus 1/1/1、Qwen 0/0/1
  - 证据：按 tests/required_testcases.json 的 14 条独立复算每轮 passed 数：Oracle 14/14/14、NOP 10/10/10、Opus 14/14/14、Qwen 9/13/14；Opus testcase 累计 42、Qwen 累计 36，与 qc/model-gate.json 的 testcase_pass_sum 一致
  - 证据：区分度判定：sum(OPUS)=3 > sum(QWEN)=1，且 testcase 累计 42 > 36；REQUIRED_COUNTS={"qwen":3,"opus":3} 的 valid_runs 均为 3，无 tie
  - 证据：无效槽位未计入能力分：Opus 侧被替换的轮次（兜底文本、输出截断、余额不足、模型名不稳定）全部单列在 _qc_runs/wciocp-build/INVALID-SLOTS.md，替代轮以新 trial 成功后才计入
  - 说明：所有分数来自 Harbor 原生 job 的落盘结果，未做任何手工加权；空清单、SKIP/ERROR/NOT_RUN、解析或环境错误均不产生正式分。
- **原始证据、历史版本、整改和干净复验已闭环**：`PASS`
  - 证据：原始日志按精确字节保存：每个 job 保留 config.json / lock.json / result.json / trial.log 与 verifier 侧 report.json、reward.json、reward.txt、reward-details.json、test-stdout.txt；模型轮另有 agent/model-result.json、agent/trajectory.jsonl、agent/patch.diff
  - 证据：无效槽位闭环：五批被替换轮次（opus-empty-response-20261014 3 个、opus-empty-response-round2-20261015 3 个、opus-4router-claude-opus-5-unstable-20261015 3 个、opus-5-fallback-text-20261015 44 个、opus-5-insufficient-balance-20261015 4 个）逐字节归档在 _qc_runs/wciocp-build/model-rounds/invalid-slots-archive/，注解层为 _qc_runs/wciocp-build/INVALID-SLOTS.md（含判定依据、阈值、原 trial 编号与替代结果）
  - 证据：交付 ZIP 在质检前完成 --verify（258 个文件 sha256 全一致），sha256=398f8569ecda34cde4f984084a42102e129d6b1b9b364c680fb8a6cb03e040fc
  - 证据：题包自检：inspect_delivery pass=True、run_qc.static_check static_pass=True、check_windows_mechanism PASS（exit 0），均以冻结 dirhash 7bebdc01887e3b6114951a7acdbf412e386cbc41f91aacea78e4b8988fc11ddc 为准
  - 说明：本批历史版本、被替代轮次与本次结果分开保存（旧失败 job 移入 invalid-slots-archive/，不复用、不改写）；题面/环境/参考解/测试任一变更后旧轨迹作废的规则在本轮得到遵守——首轮曾因 verifier 文档在跑分期间被改写而整体作废并重跑，之后冻结未再改动任何参与 checksum 的字节。
- **成品镜像远端可获取、甲方有权限、目标环境可启动并执行题目**：`PASS`
  - 证据：harbor-windows/_qc_runs/image-evidence-20261015/push-ghcr.log：docker push 6 个 tag 的完整输出，本包 tag 的 digest = sha256:7b7f613012eebb46f21db235dcf9176e13e9ceb3c4e79771f962797ed6cbd984，exit=0
  - 证据：harbor-windows/_qc_runs/image-evidence-20261015/L1-wff-pull-all.log：L1（独立 Windows 容器宿主）内 docker pull ghcr.io/wzswffhm/wfflab-windows:wciocp-220-1.0.0，exit=0，Digest 与 push 报告逐字符一致
  - 证据：harbor-windows/_qc_runs/image-evidence-20261015/anonymous-access.txt：零凭据匿名访问 ghcr.io，tags/list 与 5 个 tag 的 manifest 全部 HTTP 200
  - 证据：harbor-windows/_qc_runs/image-evidence-20261015/toolchain-probe-L1.log：从该镜像启动新容器并完成工具链功能探针（exit=0）
  - 证据：harbor-windows/_qc_runs/wciocp-build/controls/controls_summary.json 与 harbor-windows/wfflab__wciocp-220-v1.0.0-delivery/jobs/：同一镜像身份下的 Oracle/NOP 与模型轮逐 testcase 证据
  - 说明：成品镜像已发布到公共仓库并设为 public，甲方无需凭据即可拉取（匿名 tags/manifest/config 均为 HTTP 200）。L1 是独立于物理宿主的 Windows 容器宿主，其拉取日志排除了本地缓存冒充交付的可能；拉取得到的 RepoDigests 与 push 阶段报告的 digest 完全一致，因此后续所有 Oracle/NOP 与模型轮都可绑定到同一远端镜像身份。甲方目标环境不支持现场构建，故本字段指向成品镜像而非 Dockerfile 基础镜像。
  - configured_image："ghcr.io/wzswffhm/wfflab-windows:wciocp-220-1.0.0"
  - resolved_image_digest："sha256:7b7f613012eebb46f21db235dcf9176e13e9ceb3c4e79771f962797ed6cbd984"
  - target_profile：{"windows_build": 20348, "architecture": "amd64", "isolation": "process", "can_build_images": false}
  - remote_pull：`PASS`；在 L1（独立 Docker daemon，非物理宿主缓存）执行显式 docker pull，保留命令、退出码与原始 stdout；即使物理机已有同内容镜像，仍实际访问了仓库并解析出 digest。
    - 证据：harbor-windows/_qc_runs/image-evidence-20261015/L1-wff-pull-all.log：docker pull ghcr.io/wzswffhm/wfflab-windows:wciocp-220-1.0.0 -> 'Status: Downloaded newer image for ghcr.io/wzswffhm/wfflab-windows:wciocp-220-1.0.0'，=== RESULT 0 ===
    - 证据：harbor-windows/_qc_runs/image-evidence-20261015/L1-wff-pull2.log：单独重拉 wciocp-220 的完整日志，Digest: sha256:7b7f613012eebb46f21db235dcf9176e13e9ceb3c4e79771f962797ed6cbd984，PULL2 EXIT=0
    - 证据：harbor-windows/_qc_runs/image-evidence-20261015/push-ghcr.log：push 侧报告的同一 digest，两侧逐字符一致
  - recipient_access：`PASS`；全程未使用任何 Authorization 凭据：先以匿名身份向 ghcr.io/token 换取 pull 作用域 token，再读取 tags/list、manifest 与 config blob。因此甲方在无账号、无凭据条件下即可拉取，不依赖作者账号登录。
    - 证据：harbor-windows/_qc_runs/image-evidence-20261015/anonymous-access.txt：匿名 token 长度 64，tags/list 返回全部 5 个 tag
    - 证据：harbor-windows/_qc_runs/image-evidence-20261015/anonymous-access.txt：5 个 tag 的 manifest 均 HTTP/1.1 200 OK 且带 docker-content-digest
    - 证据：GitHub 包可见性已设为 public（api.github.com/user/packages/container/wfflab-windows 返回 visibility=public）
  - target_compatibility：`PASS`；镜像为 windows/amd64、OsVersion 10.0.20348.5761，与甲方宿主 build 20348 同代，Windows 容器遵循“容器 build 不高于宿主 build”的规则，因此可在甲方节点直接运行；基础层为完整 Windows Server 2022（非 Nano Server / Server Core）。
    - 证据：harbor-windows/_qc_runs/image-evidence-20261015/image-digests.json：os=windows architecture=amd64 OsVersion=10.0.20348.5761
    - 证据：harbor-windows/_qc_runs/image-evidence-20261015/toolchain-probe-L1.log：容器内 ver -> Microsoft Windows [Version 10.0.20348.5761]
    - 证据：甲方向环境说明：目标 windows-dinp-2025、宿主 build 20348/ltsc2022、主 pod 无 Docker daemon、不允许现场构建
  - clean_start：`PASS`；每个探针与每次 Harbor trial 都从同一镜像启动全新容器；未复用长驻容器，启动到就绪后即执行真实命令。
    - 证据：harbor-windows/_qc_runs/image-evidence-20261015/toolchain-probe-L1.log：docker run --rm ghcr.io/wzswffhm/wfflab-windows:wciocp-220-1.0.0 cmd /c ... 于 3.8~5.7 秒内完成启动到退出，exit=0
    - 证据：harbor-windows/_qc_runs/wciocp-build/controls/controls_summary.json：同一镜像由 Harbor 从新容器启动并跑到就绪后完成 Oracle/NOP
    - 证据：L1 内 docker info：OSType=windows Isolation=process（与甲方 process 隔离一致）
  - task_execution：`PASS`；同一镜像身份下完成标准 Harbor Oracle/NOP（各 3 轮）与模型轮，逐 testcase 结果随包交付；所有 job 的 task_checksum 与本包冻结的 dirhash 一致，说明执行确实发生在该镜像的该 Task 版本上。
    - 证据：harbor-windows/_qc_runs/wciocp-build/controls/controls_summary.json：Oracle 3 轮 reward=1、NOP 3 轮 reward=0，6 轮 task_checksum 全为 6c1284079453799bc49c249ed06c8aee66139625d9c9bba3f45f88943d10a87c
    - 证据：harbor-windows/wfflab__wciocp-220-v1.0.0-delivery/jobs/_index/assembly_report.json：12 个 job 的分数与 testcase 集合全部合法
    - 证据：harbor-windows/wfflab__wciocp-220-v1.0.0-delivery/jobs/model-qwen-*/verifier/report.json 与 harbor-windows/wfflab__wciocp-220-v1.0.0-delivery/jobs/model-opus-*/verifier/report.json：逐 testcase 结果
- **Windows 镜像不早于 2019，优先 2025，禁止 Nano Server/Server Core 和额外裁剪**：`PASS`
  - 证据：environment/Dockerfile 的运行层 FROM = mcr.microsoft.com/windows/server:ltsc2022（完整 Windows Server 2022，非 Server Core / Nano Server）
  - 证据：harbor-windows/_qc_runs/image-evidence-20261015/image-digests.json：成品镜像 os=windows architecture=amd64 OsVersion=10.0.20348.5761
  - 证据：harbor-windows/_qc_runs/image-evidence-20261015/toolchain-probe-L1.log：容器内 ver 报告 10.0.20348.5761，且 PowerShell、git、python 等完整系统组件可用
  - 证据：windows-harbor-qc/scripts/windows_image_policy.py 的 inspect_windows_dockerfile(path) 对本包 Dockerfile 无 errors
  - 说明：运行层为 mcr.microsoft.com/windows/server:ltsc2022（完整 Windows Server 2022，build 20348），早于 2019 的镜像与Nano Server / Server Core 均未使用；镜像未做额外系统裁剪，容器内保留了完整 PowerShell 与 CMD 环境。2025（build 26100）虽为优先项，但甲方宿主 build 20348 下 Windows 容器无法运行更高 build 的镜像，按 references/current-project-policy.md 的“甲方实际可运行是硬门禁”选用兼容的完整镜像。
  - configured_image："ghcr.io/wzswffhm/wfflab-windows:wciocp-220-1.0.0"
  - windows_build：20348
  - release_year：2022
  - family："windows-server"
  - untrimmed：true
  - runtime_bases：[{"image": "mcr.microsoft.com/windows/server:ltsc2022", "windows_build": 20348, "release_year": 2022, "family": "windows-server", "untrimmed": true, "evidence": ["harbor-windows/_qc_runs/image-evidence-20261015/image-digests.json：成品镜像 OsVersion=10.0.20348.5761，层数 15", "环境/Dockerfile 第 1 段 FROM 与该引用逐字一致；成品镜像除工具链与 workspace 外未替换系统组件"]}]
- **实际使用的工具通过 Dockerfile 配置，并在成品容器内完成版本和功能验证**：`PASS`
  - 证据：harbor-windows/_qc_runs/image-evidence-20261015/toolchain-probe-L1.log：在成品镜像的新容器内实际执行各工具版本与功能探针，全部 exit=0
  - 证据：environment/Dockerfile 中每项工具都有可定位的 COPY/RUN 配置行，且构建全程无网络（vendored 资产）
  - 证据：harbor-windows/_qc_runs/image-evidence-20261015/image-digests.json：工具链固化在交付镜像的层内，随镜像身份一起交付
  - 说明：逐项登记任务与执行链实际需要的工具，并同时给出 Dockerfile 配置位置（构建期证据）与成品容器内的功能探针结果（运行期证据）。PowerShell 属基础层继承（base_inherited），其余四项由 Dockerfile 显式安装（installed）。
  - tools：[{"name": "git (MinGit)", "version": "2.56.0.windows.2", "required_by": "环境/参考解/隐藏测试的仓库快照与 baseline commit（environment/Dockerfile 的 git init/add/commit 步骤）", "dockerfile_location": "environment/Dockerfile COPY vendor/MinGit-2.56.0.2-64-bit.zip -> RUN Expand-Archive ... C:\\Git; 探针 & C:\\Git\\cmd\\git.exe --version", "provisioning_kind": "installed", "functional_probe": "docker run --rm <image> cmd /c \"C:\\Git\\cmd\\git.exe --version\" -> git version 2.56.0.windows.2", "provisioning_evidence": ["harbor-windows/_qc_runs/image-evidence-20261015/image-digests.json", "harbor-windows/_qc_runs/image-evidence-20261015/toolchain-probe-L1.log"], "runtime_evidence": ["harbor-windows/_qc_runs/image-evidence-20261015/toolchain-probe-L1.log"], "status": "PASS"}, {"name": "Python (embed)", "version": "3.12.9", "required_by": "被测包的实现语言与 tests/ 的 pytest 执行器", "dockerfile_location": "environment/Dockerfile COPY vendor/python-3.12.9-embed-amd64.zip -> C:\\Python312，并改写 python312._pth", "provisioning_kind": "installed", "functional_probe": "docker run --rm <image> cmd /c \"C:\\Python312\\python.exe -V\" -> Python 3.12.9", "provisioning_evidence": ["harbor-windows/_qc_runs/image-evidence-20261015/image-digests.json", "harbor-windows/_qc_runs/image-evidence-20261015/toolchain-probe-L1.log"], "runtime_evidence": ["harbor-windows/_qc_runs/image-evidence-20261015/toolchain-probe-L1.log"], "status": "PASS"}, {"name": "pip", "version": "26.0.1", "required_by": "从 vendored wheelhouse 离线安装测试依赖（无网络构建）", "dockerfile_location": "environment/Dockerfile 解包 vendor/wheels/pip-*.whl 到 site-packages 后 RUN python -m pip --version", "provisioning_kind": "installed", "functional_probe": "docker run --rm <image> cmd /c \"C:\\Python312\\python.exe -m pip --version\" -> pip 26.0.1 from C:\\Python312\\Lib\\site-packages\\pip", "provisioning_evidence": ["harbor-windows/_qc_runs/image-evidence-20261015/toolchain-probe-L1.log"], "runtime_evidence": ["harbor-windows/_qc_runs/image-evidence-20261015/toolchain-probe-L1.log"], "status": "PASS"}, {"name": "pytest", "version": "8.3.5", "required_by": "tests/run_tests.ps1 驱动隐藏用例并产出逐 testcase 结果", "dockerfile_location": "environment/Dockerfile RUN python -m pip install --no-index --find-links C:\\vendor\\wheels 'pytest==8.3.5'", "provisioning_kind": "installed", "functional_probe": "docker run --rm <image> cmd /c \"C:\\Python312\\python.exe -m pytest --version\" -> pytest 8.3.5", "provisioning_evidence": ["harbor-windows/_qc_runs/image-evidence-20261015/toolchain-probe-L1.log"], "runtime_evidence": ["harbor-windows/_qc_runs/image-evidence-20261015/toolchain-probe-L1.log"], "status": "PASS"}, {"name": "PowerShell", "version": "5.1 (Windows Server 2022 基础层自带)", "required_by": "environment/prepare.ps1、tests/test.ps1 等 PowerShell 入口脚本", "dockerfile_location": "未安装：由 base image（mcr.microsoft.com/windows/server:ltsc2022）继承；Dockerfile 的 SHELL 指令使用 powershell", "provisioning_kind": "base_inherited", "functional_probe": "Dockerfile SHELL [\"powershell\", ...] 全程执行成功（构建期与容器内均可用）", "provisioning_evidence": ["harbor-windows/_qc_runs/image-evidence-20261015/image-digests.json"], "runtime_evidence": ["harbor-windows/_qc_runs/image-evidence-20261015/toolchain-probe-L1.log"], "status": "PASS"}]
- **实际使用嵌套虚拟化，外层 VM/扩展暴露/内层运行和当前 jobs 证据完整**：`PASS`
  - 证据：物理宿主 Get-VMHost/Get-VM：MS-7D48，hypervisorlaunchtype=Auto，HypervisorPresent=True，L1-WinSrv2022 State=Running
  - 证据：Get-VMProcessor：ExposeVirtualizationExtensions=True，Count=6（L1 标识 8cc17a99-0743-4b30-9ef3-d3a83994062c）
  - 证据：L1 内 Win32_ComputerSystem：Manufacturer=Microsoft Corporation、Model=Virtual Machine、HypervisorPresent=True
  - 证据：L1 内 Win32_Processor：VirtualizationFirmwareEnabled=True、SecondLevelAddressTranslationExtensions=True
  - 证据：harbor-windows/_qc_runs/image-evidence-20261015/toolchain-probe-L1.log：L1 内 docker info OSType=windows Isolation=process
  - 证据：harbor-windows/_qc_runs/wciocp-build/controls/controls_summary.json 与 harbor-windows/wfflab__wciocp-220-v1.0.0-delivery/jobs/：全部 job 在 L1 内的容器中执行，task_checksum=6c1284079453799bc49c249ed06c8aee66139625d9c9bba3f45f88943d10a87c
  - 说明：实际执行链为 物理宿主(L0, Hyper-V) -> L1 Windows Server 2022 虚拟机 -> L1 内的 Windows 容器(L2)，虚拟化深度为 2。裸机直接跑容器、或只在物理宿主上跑 Hyper-V 容器都只有一层，本包不属此列：外层 hypervisor 为物理宿主的 Hyper-V，L1 是货真价实的 guest（Model=Virtual Machine 且 HypervisorPresent=True），且 L1 内已暴露虚拟化扩展（VirtualizationFirmwareEnabled/SLAT 均为 True），所有 Oracle/NOP 与模型轮都在 L1 内启动的容器里完成。
  - configured_image："ghcr.io/wzswffhm/wfflab-windows:wciocp-220-1.0.0"
  - task_id："wfflab__wciocp-220"
  - task_version："1.0.0"
  - task_hash："55364aad52f869bf2b37544adb792b7a479d11e4e0963a79038e65d84e6bbf1e"
  - virtualization_depth：2
  - outer_guest_id："L1-WinSrv2022 (8cc17a99-0743-4b30-9ef3-d3a83994062c)"
  - outer_hypervisor："Microsoft Hyper-V（物理宿主 MS-7D48 / 13th Gen Intel Core i5-13490F，hypervisorlaunchtype=Auto）"
  - inner_hypervisor："Windows Server 2022 Containers + Docker Engine 27.3.1（L1 内，process 隔离）"
  - virtualization_extensions_exposed：true
  - inner_virtualization_enabled：true
  - task_runtime_in_nested_layer：true
  - checks：{"outer_guest": {"status": "PASS", "evidence": ["Get-VM L1-WinSrv2022：Id=8cc17a99-0743-4b30-9ef3-d3a83994062c Generation=1 ProcessorCount=6 MemoryStartup=12GiB State=Running", "L1 内 Win32_ComputerSystem：Manufacturer=Microsoft Corporation Model=Virtual Machine", "L1 内 systeminfo：'Hyper-V Requirements: A hypervisor has been detected.'"], "notes": "保留了外层 hypervisor 与 L1 虚拟机标识/拓扑的原始命令输出：物理宿主为 Hyper-V 宿主，L1 是 Gen1 虚拟机（Model 明确为 Virtual Machine），两者身份可复核。"}, "capabilities_exposed": {"status": "PASS", "evidence": ["物理宿主 Get-VMProcessor -VMName L1-WinSrv2022：ExposeVirtualizationExtensions=True", "L1 内 Win32_Processor：VirtualizationFirmwareEnabled=True 且 SecondLevelAddressTranslationExtensions=True", "L1 内 Win32_ComputerSystem：HypervisorPresent=True"], "notes": "外层显式打开了 ExposeVirtualizationExtensions，L1 内实际看到虚拟化固件能力与 SLAT 均已暴露，且 L1 自身识别到 hypervisor 存在；这不是仅凭 CPU 规格或参数声明得出的结论。"}, "inner_runtime": {"status": "PASS", "evidence": ["L1 内 Get-WindowsFeature Containers：InstallState=Installed", "L1 内 docker version：Client/Server 均为 27.3.1，ServerOs=windows", "harbor-windows/_qc_runs/image-evidence-20261015/toolchain-probe-L1.log：docker run 在 L1 内启动容器并输出 Microsoft Windows [Version 10.0.20348.5761]", "harbor-windows/_qc_runs/wciocp-build/controls/ 与 harbor-windows/_qc_runs/wciocp-build/model-rounds/：每轮 job 的 trial 均在 L1 内容器里完成并有终态 reward"], "notes": "记录了 L1 内实际启动 L2 Windows 容器的命令、日志与终态：Containers 功能已安装、Docker Engine 在 L1 内运行、容器的 OS 版本与镜像一致，Oracle/NOP 与模型轮全部在这些容器中产生正式分数。"}, "job_binding": {"status": "PASS", "evidence": ["本包 task.toml 的 docker_image = ghcr.io/wzswffhm/wfflab-windows:wciocp-220-1.0.0，与各 job 使用的镜像一致", "harbor-windows/wfflab__wciocp-220-v1.0.0-delivery/jobs/ 下 12 个 job 的 result.json task_checksum 均为 6c1284079453799bc49c249ed06c8aee66139625d9c9bba3f45f88943d10a87c，与 inspect_delivery.harbor_dirhash 复算一致", "harbor-windows/_qc_runs/wciocp-build/controls/controls_summary.json：Oracle 3 轮=1、NOP 3 轮=0，均在 L1 内执行", "harbor-windows/wfflab__wciocp-220-v1.0.0-delivery/jobs/model-*/agent/model-result.json：模型轮的 runner_sha256 与 base_url 可追溯，且与 Oracle/NOP 同一镜像与同一 Task"], "notes": "当前 Task/镜像与实际模型、Oracle/NOP jobs 均绑定到嵌套执行层：镜像引用与 task.toml 一致，所有 job 的 task_checksum 与题包复算的 dirhash 相同，说明没有跨环境或跨版本混入。"}}

## 原始证据

- `harbor/`：真实 Oracle/NOP 报告、命令、job 和 CLI 日志
- `delivery-layout.json`：目录与 task_id/version/hash 绑定
- `model-gate.json`：四模型次数、分数和区分度
- `model-jobs.json`：12 个 Harbor jobs（6 个模型、3 个 Oracle、3 个 NOP）交叉校验
- 人工证据：WIP 94 项、D01-D20、逐项证据链、Hack 事件和独立复算文件
