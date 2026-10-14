# WIP 94 项逐项登记表 —— wfflab__wvas-216 v1.0.0

清单来源：`_reference/windows-harbor-qc/references/windows-procurement-qc-manual-20260927/02-WIP94项对照.md`

| 编号 | 检查项 | 结论 | 证据 | 说明 |
| --- | --- | --- | --- | --- |
| FC-01 | 检查任务说明文件是否存在 | 通过 | instruction.md | 任务说明文件 instruction.md 存在 |
| FC-02 | 检查任务说明文件是否非空 | 通过 | instruction.md (5508 B) | 非空 |
| FC-03 | 检查任务说明文件是否可解析为文本 | 通过 | instruction.md 可按 UTF-8 解码 | 文本可解析 |
| FC-04 | 检查 `test.sh` 是否只位于测试目录 | 通过 | 包内 test.sh：0 个<br>Windows 项目适配：评分入口为 tests/test.ps1 与 tests/test.bat，两者均在 tests/ 内；无 test.sh | test.sh 均位于 tests/（或按 Windows 适配用 test.ps1/test.bat 且位于 tests/） |
| FC-05 | 检查 `checks.py` 是否只位于测试目录 | 通过 | 包内 checks.py：0 个<br>Windows 项目适配：检查逻辑在 tests/run_tests.ps1 + tests/test_wvas_semantics.py，均在 tests/ 内 | checks.py 均位于 tests/（或按 Windows 适配用 run_tests.ps1 + 语义测试文件） |
| FC-06 | 检查 `judge.toml` 是否存在 | 通过 | tests/judge.toml | judge.toml 存在且位于 tests/ |
| FC-07 | 检查 `judge.toml` 是否只位于测试目录 | 通过 | tests/judge.toml | judge.toml 存在且位于 tests/ |
| FC-08 | 检查 Rubrics 配置文件的 TOML 语法是否可解析 | 通过 | tests/judge.toml 可被 tomllib 解析<br>schema_version=outside-programmatic-rubric-v6 | TOML 语法合法 |
| FC-09 | 检查 Rubrics 配置的必要字段是否可读取 | 通过 | rubrics=7 条<br>权重和=1.0000<br>rubric 覆盖 test_id=16 条 | Rubric 条目/权重/归属用例均可读且权重和为 1.0 |
| FC-10 | 检查 verifier 中 reward 文件命名是否符合白名单 | 通过 | jobs/**/verifier 下 reward* 文件：reward-details.json, reward.json, reward.txt | reward 命名均在白名单内 |
| FC-11 | 检查最终质检报告文件是否存在 | 通过 | deliverables/2026-10-14_wvas216-替换/README.md（本批最终质检报告，Markdown） | 最终质检报告存在且为 UTF-8 Markdown |
| FC-12 | 检查最终质检报告是否使用 Markdown 扩展名 | 通过 | deliverables/2026-10-14_wvas216-替换/README.md（本批最终质检报告，Markdown） | 最终质检报告存在且为 UTF-8 Markdown |
| FC-13 | 检查最终质检报告正文是否可读取 | 通过 | deliverables/2026-10-14_wvas216-替换/README.md（本批最终质检报告，Markdown） | 最终质检报告存在且为 UTF-8 Markdown |
| QD-SP-01 | 检查任务目标是否明确且无歧义 | 待人读 | instruction.md<br>tests/required_testcases.json<br>jobs/（模型×3 与 Opus×3 分差） | 需人读判定（题面语义/难度/区分度） |
| QD-SP-02 | 检查任务约束是否明确 | 待人读 | instruction.md<br>tests/required_testcases.json<br>jobs/（模型×3 与 Opus×3 分差） | 需人读判定（题面语义/难度/区分度） |
| QD-SP-03 | 检查验收标准是否明确 | 待人读 | instruction.md<br>tests/required_testcases.json<br>jobs/（模型×3 与 Opus×3 分差） | 需人读判定（题面语义/难度/区分度） |
| QD-SP-04 | 检查必需产物是否完整声明 | 待人读 | instruction.md<br>tests/required_testcases.json<br>jobs/（模型×3 与 Opus×3 分差） | 需人读判定（题面语义/难度/区分度） |
| QD-SP-05 | 检查是否明确要求运行产物 | 待人读 | instruction.md<br>tests/required_testcases.json<br>jobs/（模型×3 与 Opus×3 分差） | 需人读判定（题面语义/难度/区分度） |
| QD-SP-06 | 检查外部接口契约是否完整 | 待人读 | instruction.md<br>tests/required_testcases.json<br>jobs/（模型×3 与 Opus×3 分差） | 需人读判定（题面语义/难度/区分度） |
| QD-SP-07 | 检查结构化输出 Schema 是否完整 | 待人读 | instruction.md<br>tests/required_testcases.json<br>jobs/（模型×3 与 Opus×3 分差） | 需人读判定（题面语义/难度/区分度） |
| QD-SP-08 | 检查示例的约束性质是否明确 | 待人读 | instruction.md<br>tests/required_testcases.json<br>jobs/（模型×3 与 Opus×3 分差） | 需人读判定（题面语义/难度/区分度） |
| QD-SP-09 | 检查题面是否以要求而非操作步骤表达 | 待人读 | instruction.md<br>tests/required_testcases.json<br>jobs/（模型×3 与 Opus×3 分差） | 需人读判定（题面语义/难度/区分度） |
| QD-SP-10 | 检查题面是否泄露完成任务的具体命令 | 待人读 | instruction.md 命令行片段命中 1 条：python -m pytest tests -q | LLM-as-a-Judge：命中片段为运行冒烟测试，不以之完成修复任务，仍属'只提供必要接口约束'，不构成'足以直接完成任务的命令序列' |
| QD-SP-11 | 检查题面是否泄露具体代码修复方案 | 待人读 | instruction.md 仅描述现象与验收（含 F/E 编号），不含代码级修复方案 | 需人读确认无代码修复方案泄露 |
| QD-SP-12 | 检查任务是否保留自主探索空间 | 待人读 | instruction.md<br>tests/required_testcases.json<br>jobs/（模型×3 与 Opus×3 分差） | 需人读判定（题面语义/难度/区分度） |
| QD-SP-13 | 检查任务是否为单命令机械任务 | 待人读 | instruction.md<br>tests/required_testcases.json<br>jobs/（模型×3 与 Opus×3 分差） | 需人读判定（题面语义/难度/区分度） |
| QD-SP-14 | 检查任务是否只是纯重复操作 | 待人读 | instruction.md<br>tests/required_testcases.json<br>jobs/（模型×3 与 Opus×3 分差） | 需人读判定（题面语义/难度/区分度） |
| QD-SP-15 | 检查典型解法是否存在过高的操作复杂度 | 待人读 | instruction.md<br>tests/required_testcases.json<br>jobs/（模型×3 与 Opus×3 分差） | 需人读判定（题面语义/难度/区分度） |
| QD-SP-16 | 检查任务是否具备可观察的中间产出 | 待人读 | instruction.md<br>tests/required_testcases.json<br>jobs/（模型×3 与 Opus×3 分差） | 需人读判定（题面语义/难度/区分度） |
| QD-SP-17 | 检查基线模型成绩是否表明任务过易 | 待人读 | instruction.md<br>tests/required_testcases.json<br>jobs/（模型×3 与 Opus×3 分差） | 需人读判定（题面语义/难度/区分度） |
| QD-SP-18 | 检查典型解法是否因操作过少而缺乏挑战 | 待人读 | instruction.md<br>tests/required_testcases.json<br>jobs/（模型×3 与 Opus×3 分差） | 需人读判定（题面语义/难度/区分度） |
| QD-SO-01 | 检查任务要求是否可以同时满足 | 待人读 | — | — |
| QD-SO-02 | 检查完成任务所需的本地输入是否存在 | 待人读 | — | — |
| QD-SO-03 | 检查完成任务所需权限是否可用 | 待人读 | — | — |
| QD-SO-04 | 检查任务资源需求是否在项目预算内 | 待人读 | — | — |
| QD-SO-05 | 检查 Oracle 或参考方案是否能在目标环境成功执行 | 通过 | Oracle×3 reward=['1', '1', '1']（参考方案在目标 Windows 容器内成功） | Oracle 可在目标环境成功执行 |
| QD-SO-06 | 检查参考方案是否依赖答案硬编码或 verifier 漏洞 | 待人读 | — | — |
| QD-SO-07 | 检查完成状态是否可以被客观观察 | 待人读 | jobs/ 中每轮 verifier/report.json 的逐例 PASS/FAIL 与 binary formal_score | 需人读确认完成状态可被客观观察 |
| QD-IN-01 | 检查题面、示例和初始环境是否泄露最终答案 | 待人读 | instruction.md（题面）<br>environment/workspace/docs/NOTES.md | 需人读确认题面/示例/初始环境不泄露答案 |
| QD-IN-02 | 检查模型运行时是否无法读取测试目录 | 待人读 | verifier/negative_access_probe.ps1（负向可达性探针）<br>environment/agent_visible_paths.json（模型可见路径声明）<br>Harbor 仅把包根 tests/ 挂到 C:\tests；verifier/ 不进模型容器 | 需人读隔离证据后判定 |
| QD-IN-03 | 检查模型运行时是否无法读取参考解法 | 待人读 | verifier/negative_access_probe.ps1（负向可达性探针）<br>environment/agent_visible_paths.json（模型可见路径声明）<br>Harbor 仅把包根 tests/ 挂到 C:\tests；verifier/ 不进模型容器 | 需人读隔离证据后判定 |
| QD-IN-04 | 检查 NOP 或空实现是否不能通过任务 | 通过 | NOP×3 reward=['0', '0', '0'] | 空实现无法通过 |
| QD-IN-05 | 检查硬编码预期结果是否无法绕过任务 | 待人读 | verifier/oracle/reference/wvas（参考实现，交付侧资产）<br>verifier/SEALED_MANIFEST.json（哈希封条） | 需人读确认无硬编码预期可绕过 |
| QD-IN-06 | 检查测试与答案相关材料是否不会通过其他路径暴露 | 待人读 | verifier/negative_access_probe.ps1（负向可达性探针）<br>environment/agent_visible_paths.json（模型可见路径声明）<br>Harbor 仅把包根 tests/ 挂到 C:\tests；verifier/ 不进模型容器 | 需人读隔离证据后判定 |
| ENV-01 | 检查 Docker 技术栈与题面设定是否一致 | 通过 | environment/Dockerfile: mcr.microsoft.com/windows/servercore:ltsc2022@sha256:76cf422c98ca437b308374d0498280541fa42ac7061bb44015a6c8b70cf4db6a | Windows 容器与题面设定一致 |
| ENV-02 | 检查初始代码库与题面描述是否一致 | 通过 | environment/workspace/wvas/vas.py（缺陷起始实现） | 初始代码库与题面描述一致 |
| ENV-03 | 检查必要工具是否已预装且可执行 | 通过 | environment/vendor/INVENTORY.json<br>vendor 条目：0 | 预装依赖清单齐备 |
| ENV-04 | 检查应用级依赖版本是否锁定 | 通过 | 13 个 wheel，全部带版本号：colorama-0.4.6-py2.py3-none-any.whl, exceptiongroup-1.3.1-py3-none-any.whl, iniconfig-2.1.0-py3-none-any.whl, packaging-26.3-py3-none-any.whl … | 应用级依赖版本锁定 |
| ENV-05 | 检查核心任务和验证是否可离线运行 | 通过 | tests/ 无联网安装调用<br>environment/vendor 内置 python-3.12.9-embed-amd64.zip 与 wheel 集 | 核心任务与验证可离线运行 |
| ENV-06 | 检查结果是否不依赖系统当前时间 | 通过 | tests/test_wvas_semantics.py 无 datetime.now/date.today/Get-Date（命中 0）<br>time.time() 出现 2 次，均为超时轮询 deadline 用途，不参与断言 | 结果不依赖系统当前时间 |
| ENV-07 | 检查随机行为是否固定 | 通过 | 评分套件未引入随机行为（命中 0 次） | 随机行为固定 |
| ENV-08 | 检查并发共享状态是否采用可靠同步或隔离机制 | 待人读 | 单容器单 trial 串行执行；Harbor 每轮独立容器与独立 workspace | 并发共享状态由 Harbor 容器隔离保证（需人读确认） |
| ENV-09 | 检查相同环境和解法的重复执行结果是否一致 | 通过 | 同一 checksum 下 Oracle ×3 全 1、NOP ×3 全 0、模型轮 6 个 | 相同环境与解法的重复执行结果一致 |
| ENV-10 | 检查工作目录与路径解析是否一致 | 通过 | environment/run.ps1 用 $PSScriptRoot + Join-Path 解析任务根、tests 与 workspace，不依赖调用者当前目录<br>environment/workspace 作为固定工作区随包交付 | 工作目录与路径解析一致 |
| ENV-11 | 检查 `test.sh` 是否不会现场安装软件 | 通过 | tests/*.ps1 未现场安装软件 | test 入口不现场安装软件 |
| ENV-12 | 检查仅供 verifier 使用的依赖是否与模型环境隔离 | 通过 | verifier/ISOLATION.md<br>verifier/negative_access_probe.ps1（负向可达性探针） | 仅供 verifier 使用的依赖与模型环境隔离 |
| ENV-13 | 检查超时配置是否覆盖合理执行时间 | 通过 | task.toml 超时配置 = 7200 秒 | 超时配置覆盖合理执行时间 |
| ENV-14 | 检查服务启动是否使用可验证的就绪条件 | 通过 | environment/prepare.ps1 内含就绪判定 | 服务启动使用可验证的就绪条件 |
| VV-01 | 检查题面每项明确要求是否都有验证覆盖 | 待人读 | — | — |
| VV-02 | 检查每条强制断言是否能追溯到题面 | 待人读 | — | — |
| VV-03 | 检查测试是否与题面要求一致 | 待人读 | — | — |
| VV-04 | 检查测试是否不绑定未声明的内部实现细节 | 待人读 | — | — |
| VV-05 | 检查测试是否不强制未声明的文件名或路径 | 待人读 | — | — |
| VV-06 | 检查测试是否不强制未声明的字面值或顺序 | 待人读 | — | — |
| VV-07 | 检查核心功能是否通过行为而非静态存在性验证 | 待人读 | — | — |
| VV-08 | 检查核心功能是否不依赖关键词或正则匹配判定 | 待人读 | — | — |
| VV-09 | 检查主要正常路径是否被测试 | 待人读 | — | — |
| VV-10 | 检查关键边界条件是否被测试 | 待人读 | — | — |
| VV-11 | 检查关键异常路径是否被测试 | 待人读 | — | — |
| VV-12 | 检查程序化验证 Case 数量是否合规 | 通过 | required_testcases.json（JSON 数组）：共 16 条，F2P 8 / P2P 8 | 程序化 case 数量合规 |
| VV-13 | 检查是否至少存在一条 Rubric | 通过 | tests/judge.toml 含 7 条 Rubric | 至少存在一条 Rubric |
| VV-14 | 检查 Rubrics 权重占比是否合规 | 通过 | Rubric 权重和=1.0000，programmatic_weight=1.0 | 权重占比合规 |
| VV-15 | 检查是否优先使用程序化验证 | 通过 | Rubric type 集合=['programmatic']（全部程序化） | 优先使用程序化验证 |
| VV-16 | 检查每条 Rubric 是否具有原子性 | 待人读 | — | — |
| VV-17 | 检查每条 Rubric 是否针对当前任务定制 | 待人读 | — | — |
| VV-18 | 检查不同 Rubrics 是否互不重叠 | 待人读 | — | — |
| VV-19 | 检查 Rubric 评分锚点是否事实明确 | 待人读 | — | — |
| VV-20 | 检查每个 Rubric 的 Explicit/Implicit 分类是否正确 | 待人读 | — | — |
| VV-21 | 检查 Explicit/Implicit 数量统计是否准确 | 待人读 | — | — |
| VV-22 | 检查程序化 reward 是否稳定 | 通过 | Oracle×3 reward=['1', '1', '1']；NOP×3 reward=['0', '0', '0'] | reward 在重复执行下稳定 |
| VV-23 | 检查 Rubrics reward 是否稳定 | 通过 | Oracle×3 reward=['1', '1', '1']；NOP×3 reward=['0', '0', '0'] | reward 在重复执行下稳定 |
| VV-24 | 检查标注员是否在写测试前设计过具体用例 | 待人读 | — | — |
| VV-25 | 检查造测轨迹是否为迎合特定模型结果而循环修改测试 | 待人读 | — | — |
| VV-26 | 检查模型执行轨迹文件是否齐全 | 通过 | 12 个 job 的轨迹/溯源文件齐备 | 轨迹文件齐全 |
| VV-27 | 检查模型执行轨迹是否形成闭合执行序列 | 通过 | 12 个 job 的轨迹/溯源文件齐备 | 轨迹文件齐全 |
| VV-28 | 检查 verifier 结果文件是否齐全 | 通过 | 12 个 job 的 verifier 六件套齐备 | verifier 结果文件齐全 |
| VV-29 | 检查 verifier 结果文件是否可解析 | 通过 | 12 份 verifier/result.json 可解析且带 status | verifier 结果可解析 |
| VV-30 | 检查最终 reward 是否与验证证据一致 | 通过 | 12 个 job 的 verifier reward 与逐例结果一致 | 最终 reward 与验证证据一致 |
| VV-31 | 检查最终质检结论是否引用必要证据 | 待人读 | — | — |
| VV-32 | 检查失败根因分类是否合理 | 待人读 | — | — |
| VV-33 | 检查模型与 reward 统计是否使用最新完整批次 | 待人读 | 本轮为最新完整批次：控制 6 + 模型 6，同一 task checksum | 模型与 reward 统计使用最新完整批次（需人读确认批次边界） |
| VV-34 | 检查最终质检结论是否包含可执行的整改与复验信息 | 待人读 | — | — |
| VV-35 | 检查构建轨迹证据是否足以审查造测意图 | 待人读 | — | — |
| VV-36 | 检查模型是否实际生成或修改了题面要求的最终产物 | 通过 | 6/6 个模型轮产出非空 patch.diff | 模型实际生成或修改了最终产物 |

合计 94 项：自动判定通过 40、不通过 0、待人读 54。
