---
name: Harbor SOTA
description: 按《外发版-评测题包交付规范 v4》与《Coding 交叉长尾领域数据生产规范》自动化生产符合交付标准的 Harbor 格式评测题包。覆盖五件套结构（instruction.md/task.toml/environment/solution/tests）、task.toml schema 1.4 全字段、judge.toml + gating.toml Rubric 编写（条数/权重 3|7|10/维度/锚点≥30%/负向≥20%）、双向预检（Oracle≥0.7 且 gating=1.0、空产物≤0.10、verifier_error=0）、SOTA 三家均分通过率验证（L2≤65%/L3-L4≤55%/L5≤50%）、打包命名与无残留自检。当用户要求生产/生成/交付外发评测题包、五件套、judge.toml、gating.toml、golden_output，或按评测集外发规范/龙猫数据提交标准出题时使用。
description_zh: 评测题包外发生产
description_en: Eval bundle delivery production
disable: false
agent_created: true
---

# Harbor Eval Bundle（评测题包外发生产）

## 用途与触发条件

按《外发版-评测题包交付规范 v4》（20260808，下称「规范」）与《Coding 交叉长尾领域数据生产规范》自动化生产**符合外部验收标准**的 Harbor 格式评测题包，打包提交到「龙猫-数据提交」登记表。

触发词：生产评测题包 / 出题 / 五件套 / judge.toml / gating.toml / golden_output / 外发规范 / 龙猫提交 / SOTA 通过率 / 双向预检。

与 `harbor-skill` 的区别：`harbor-skill` 是**内部 RL 训练数据**生产（pytest 程序化评分 + 16 trial 难度门）；本 skill 是**外部供应商交付**口径（Judge 模型 Rubric + gating 一票否决 + golden_output + 双向预检 + SOTA 通过率）。两者评分体系、task.toml 字段、验收口径完全不同，**不得混用**。

## 交付标准（全部满足才算完成，任一不过禁止打包提交）

| 门 | 标准 | 验证方式 |
|----|------|----------|
| G1 五件套 | instruction.md / task.toml / environment(Dockerfile+requirements.txt+input_files/) / solution(solve.sh+golden_output/) / tests(test.sh+finalize.py+graded/judge.toml+gating/gating.toml+golden_output) 齐全 | 目录检查 |
| G2 task.toml | schema_version="1.4"；必填字段全（见 @references/task-toml-guide.md） | 字段检查 |
| G3 Rubric | 条数 L2≥8/L3≥12/L4≥18/L5≥25；Critical(+10)≥2；锚点≥30%；负向≥20%；权重仅 3/7/10；仅 binary；三必需维度覆盖 | 脚本统计 judge+gating criterion |
| G4 双向预检 | Oracle 产物主分 ≥0.7 且 gating=1.0；空产物 ≤0.10；两次均 verifier_error=0 | `harbor run -p <题> -a oracle` / `-a nop` |
| G5 SOTA | Claude code 框架，三家待测模型均分 L2≤65%、L3-L4≤55%、L5≤50%（裁判 gpt-5.5，以当批规范清单为准） | 跑分记录 |
| G6 打包 | 批次→题目→五件套层级；命名「供应商+领域+一级分类+时间」；无 jobs/logs/reward.json/.git 残留；UTF-8 ≤200 字节 | delivery-checklist 11 项 |

## 端到端生产流程（不得跳步）

### 1. 选题与定级
- 必须来自**真实付费场景**：每道题对应真实工作场景（"有人会为此付费"），`source_note` 标注数据来源与真实性保障；**禁止为测 LLM 弱点设计的 adversarial 题**。
- 领域对齐《领域分类表》（26 领域 / Coding 非常规语言 / 交叉领域）；`category_l1/l2` 与 `scene_l3` 取表内枚举原文，**禁止自造近义说法**。
- 定级 L2~L5（不收 L1），按**长程性**分级（专家人时/必要步骤/工具类别/反馈轮次，见规范 7.1 表），不是"题目难不难"。
- **先规划三级分类分布与交付物清单，再批量生产**：同领域 60 题在三级场景平均分布，不接受集中在少数标签。

**领域分类表参考**
一级分类	二级分类	细分场景
非常规语言	COBOL / JCL	银行核心系统批处理程序维护；大型机报表程序修改；COBOL→Java 迁移改写与逻辑等价校验；JCL 作业调度脚本编写与排错
	ABAP	SAP 报表（ALV）开发；用户出口 / BAdI 增强；IDoc / RFC / BAPI 接口开发；智能表单（Smart Forms）；ECC→S/4HANA 代码适配改造
	RPG（IBM i / AS400）	AS400 遗留业务程序维护；RPG III→RPG IV / Free-format 改写；与 DB2 for i 交互的批处理逻辑
	Verilog / SystemVerilog	RTL 模块设计（FIFO、仲裁器、总线接口）；UVM 验证平台搭建；Testbench 与断言（SVA）编写；时序约束与综合脚本配合
	VHDL	FPGA 逻辑设计（Xilinx / Intel）；状态机与接口时序实现；军工航天遗留 VHDL 代码维护
	MATLAB / Simulink	信号处理与滤波器设计；控制系统建模仿真；Simulink 模型搭建与代码生成（Embedded Coder）；图像处理算法原型
	VBA	Excel 自动化报表与数据清洗；跨工作簿批量处理；Access 小型业务系统维护；Outlook / Word 办公自动化宏
	Solidity / 智能合约语言	ERC-20 / ERC-721 合约编写；DeFi 协议逻辑（质押、借贷、AMM）；合约安全审计（重入、溢出、权限）；Gas 优化
	AutoLISP / VBA for CAD	AutoCAD 批量图纸处理（标注、图层、块）；自定义绘图命令；图纸信息提取导出
	Fortran	气象 / 海洋数值模式维护（WRF 等）；有限元遗留代码修改；Fortran 与 C / Python 混合编程封装
	R	统计建模与假设检验；临床试验数据分析；生信包（Bioconductor）分析流程；ggplot2 出版级绘图；Shiny 交互应用
	SAS	临床试验统计编程（CDISC / SDTM / ADaM）；金融风控评分卡；SAS 宏程序维护；SAS→Python/R 迁移
	PLC 语言（梯形图 / ST，IEC 61131-3）	产线逻辑控制程序（西门子 TIA / Codesys / 三菱）；运动控制与伺服配置；与 HMI / SCADA 联调；安全联锁逻辑
	LabVIEW（G 语言）	测试测量系统搭建；仪器控制（GPIB / VISA）；数据采集（DAQ）与实时显示程序
	汇编（x86 / ARM / MCU）	引导程序（Bootloader）与启动代码；中断服务与关键路径优化；逆向工程与反汇编分析；单片机裸机驱动
	着色器语言（GLSL / HLSL / WGSL）	渲染特效（水面、体积光、后处理）；计算着色器（Compute Shader）优化；Shadertoy 风格程序化图形
	TCL	EDA 工具自动化脚本（Vivado / Design Compiler / ICC）；综合与布局布线流程脚本；仿真回归脚本
	Perl	遗留运维 / 文本处理脚本维护；老生信 pipeline（BioPerl）修补；Perl→Python 迁移
	Delphi / Object Pascal	遗留桌面业务系统（进销存、医院、政务）维护；老组件（BDE、VCL）兼容处理；Delphi 版本升级迁移
	数据库过程语言（PL/SQL / T-SQL 遗留存储过程）	千行级遗留存储过程理解与重构；Oracle→PostgreSQL / 国产库迁移改写；游标与批处理性能优化
	G 代码 / 数控编程	CNC 加工程序编写与刀路修改；宏程序（参数化加工）；后处理器定制
	函数式小众语言（Haskell / OCaml / Erlang / Elixir）	金融领域 DSL 与类型建模；电信高并发系统（Erlang/OTP）维护；编译器 / 静态分析工具开发
	Prolog / Lisp 家族	规则引擎与逻辑推理程序；Emacs Lisp 插件开发；遗留专家系统维护
	Groovy / 构建 DSL	Jenkins Pipeline 编写与排错；Gradle 构建脚本定制；nextflow 生信流程脚本
	MUMPS（M 语言）	医疗信息系统（VistA / InterSystems Caché）维护；全局变量数据结构操作；接口改造
	其他	其他非常规编程语言

### 2. 写 instruction.md（≥300 字，无 AI 痕迹）
- 显式分段写出：业务场景与角色、可用源文件（`/app/input_files/` 只读）、交付物要求（表格式：文件名/是否必交/格式说明）、硬约束（禁行项/文件名/字数，独立段落，不藏括号）。
- 交付物文件名**逐字写死**（禁止 glob/"或等价命名"），不加日期/时间戳/版本号动态成分，大小写敏感，建议以 task_id 为前缀。
- 文风：像真人工程师提需求，禁止 AI 腔（详见 @references/pitfalls.md 文风节）。
- 信息不足时要求 Agent 澄清或给出带假设的方案，不得让模型凭空猜测。

### 3. 准备 environment/input_files/
- 该场景真实交付物用什么源文件就用什么源文件；**真实或高仿真数据**，匿名化/脱敏（不虚构、不含真实涉密或敏感个人信息）。
- 容器内路径固定 `/app/input_files/`（只读，`chmod -R a-w`）。

### 4. 产出 solution/golden_output/
- 由领域专家口径产出标准答案，文件名/格式/数量与 instruction.md 和 `[[metadata.deliverables]]` **严格一致**。
- 显式覆盖该题全部预期失败点，作为 Rubric 自检基准。
- 评分侧副本 `tests/golden_output/` 与之一致，两目录均不得为空。

### 5. 写 task.toml（schema 1.4）
- 完整模板与逐字段说明见 @references/task-toml-guide.md。
- 要点：`artifacts` 由 deliverables 机械展开（`/app/output/` + path）；`[environment]` 只允许规范字段表内键（os/network_mode/allowed_hosts/build_timeout_sec/docker_image/cpus/memory_mb/storage_mb/env/healthcheck），**禁止 workdir**；`[verifier]` 占位符 `${JUDGE_GATEWAY}/${OPENAI_API_KEY}/${OPENAI_BASE_URL}` 逐字保留，**不要填真实密钥**；`[agent].user="agent"`。

### 6. 写 tests/graded/judge.toml + tests/gating/gating.toml
- 规则与示例见 @references/rubric-guide.md。先写 Rubric 再自检 G3 全部指标。

### 7. 写 environment/Dockerfile + requirements.txt
- 模板见 @references/rubric-guide.md 附录或规范 4.1；硬性要求：
  - `FROM python:3.12-slim`（统一官方 python 镜像；内网加速地址由平台下发，不写死私有镜像名）
  - 安装 `harbor-rewardkit[all]==0.1.7` + 任务依赖（python-docx/pypdf/chardet/matplotlib 等按需）
  - `useradd -m -u 1000 agent`；`/app/output` 属 agent 可写；`WORKDIR /app`（工作目录由 Dockerfile 决定）
  - requirements.txt 构建期预装；**无依赖也交空文件**
- 构建后跑镜像自检命令（见规范 4.2），末行打印 OK 才算通过。

### 8. 复制固定模板 tests/test.sh + tests/finalize.py
- **平台固定模板，逐字复制、含注释一并保留、不得改动**（见 templates/ 目录与规范附录 A）。
- 供应商只负责 `graded/` 与 `gating/` 内容。

### 9. 双向预检（本地，同一冻结修订）
```bash
export OPENAI_API_KEY=... OPENAI_BASE_URL=...   # 本地自测要自己导；task.toml 占位符保持原样
harbor run -p <题目目录> -a oracle    # 正向：Oracle 产物主分 ≥0.7，且参考答案未触发任何红线
harbor run -p <题目目录> -a nop       # 负向：空产物主分 ≤0.10
```
- 两个方向均须 `verifier_error=0`。任一不达标 = Rubric 写歪，整题退回重写。
- 本地自测时平台不会替换 `${VAR}`，没导 KEY 会展开成空值导致判官全失败。

### 10. SOTA 通过率验证（G5）
- 在 Claude code 框架下，按当批规范列出的待测模型（20260801 标准：Claude opus 4.8 / glm5.2 / kimi-k3，裁判 gpt5.5）跑分，**取三家均分**：L2≤65%、L3-L4≤55%、L5≤50%。
- 若题目要求区分度（Coding 规范）：多个 frontier 模型跑分极差 ≥0.30。
- 不达标：调整难度定级或题目本身（重新走流程），不得伪装跑分。

### 11. 打包与自检
- 目录层级固定「批次目录 → 题目目录 → 五件套」，不得多套一层、不得平铺在 zip 根。
- 命名：单题 `供应商+领域+一级分类+时间`；批次 zip `供应商+领域+批次+时间`；按领域分别提交压缩包。
- 提交前逐项跑 @references/delivery-checklist.md 的 11 项自检，全过才提交。

### 12. 提交登记
- zip 上传「龙猫-数据提交」多维表格，随件注明批次目录名与题目数。
- 返修：`[task].version` 递增补丁号（1.0.0→1.0.1），只重交修订题，批次目录名沿用原名加 `_fix<N>`，供应商代号不随返修变更。

## 标准目录（交付形态）

```text
<批次目录：供应商+领域+一级分类+时间>/
└── <task_id>/                        # 题目目录 = 题目编号，如 FIN-T2-001
    ├── instruction.md                # 任务描述（仅接受此文件名）
    ├── task.toml                     # schema 1.4 配置+元数据+交付物清单+Rubric 索引
    ├── environment/
    │   ├── Dockerfile
    │   ├── requirements.txt          # 无依赖交空文件
    │   └── input_files/              # 源文件 → /app/input_files（只读）
    ├── solution/
    │   ├── solve.sh                  # Oracle 入口：复制 golden_output → /app/output
    │   └── golden_output/            # 专家标准答案
    └── tests/
        ├── test.sh                   # 固定模板（逐字复制）
        ├── finalize.py               # 固定模板（逐字复制）
        ├── graded/judge.toml         # 计分 Rubric
        ├── gating/gating.toml        # 一票否决
        ├── golden_output/            # 参考答案副本（评分侧）
        └── assets/                   # 可选：评分基准材料
```

## 评分机制速记（judge/gating 语义）

- `graded/`：`aggregation = "weighted_mean"`；`S_max` = 全部正向条目的 weight 之和；分子 = Σ正向 weight×value − Σ负向 weight×(1−value)；reward = clip(分子/S_max, 0, 1)。**负向不进分母**。
- `gating/`：`aggregation = "all_pass"`；任一 criterion 被判"违规存在" → 整题 reward 直接归零，其余维度分保留在 reward.json 供审计；`negate=true` 时 Reward Kit 自动翻转（完全没违规=1.0）。
- `judge.toml` 的 `[judge].weight` **不写**（只影响审计值）；`mode` 统一 `"individual"`。
- gating 选取须慎重：安全合规红线 / 领域公认致命专业错误；**不接受故意设坑**（只能来自任务书明确要求或行业无争议红线）；必须是负向违规描述。

## 反模式（禁止）

1. 缺五件套任一组件的空壳题包（尤其 requirements.txt / input_files/ / golden_output / finalize.py）。
2. `[quality] version=1` 式空壳 Rubric 或未接 rewardkit 的 test.sh（对应内部质检 P0-2 同型错误）。
3. 改固定模板 test.sh/finalize.py。
4. 权重用 3/7/10 以外的值、非 binary、恶意堆砌 negate 负分压分。
5. 不接受恶意负分行为：故意增加题目难度/降低题目分数。
6. instruction <300 字、无显式硬约束段、AI 腔、泄露 Rubric/隐藏测试。
7. 非真实付费场景、无 source_note、adversarial 题、三级分类扎堆。
8. adversarial 造假数据源、未脱敏个人信息（gating G 类红线必配）。
9. 未跑双向预检或 Oracle<0.7 / 空产物>0.10 仍打包。
10. task.toml 填真实密钥、占位符被替换、`[environment]` 写 workdir。
11. zip 含 jobs/、logs/、reward.json、reward-details.json、.git、__pycache__、.venv、__MACOSX、.DS_Store、嵌套 zip、符号链接。
12. 打包层级错误（题目平铺在 zip 根或多套一层）。
13. 交付物文件名六处不一致（instruction.md / deliverables.path / artifacts / 两份 golden_output / judge.files）。

## Verification（交付前必跑）

1. `@references/delivery-checklist.md` 11 项全过。
2. G3 用脚本统计：条数下限、Critical≥2、锚点≥30%、负向≥20%、权重∈{3,7,10}、仅 binary、judge+gating 的 criterion id 集合与 `[[metadata.rubric_index]]` 完全一致。
3. G4 双向预检结果留档：oracle reward、nop reward、verifier_error。
4. G5 SOTA 三家均分记录留档。
5. 解压 zip 复核五件套 + 无残留后提交。

## References

- @references/task-toml-guide.md — task.toml 1.4 完整模板与逐字段说明
- @references/rubric-guide.md — judge/gating 编写规则、维度、示例、镜像要求
- @references/delivery-checklist.md — 提交前 11 项自检 + 打包后硬自检
- @references/pitfalls.md — 反模式与踩坑录（含文风对照）
- @references/sota-calibration.md — SOTA 通过率验证流程
- @references/domain-categories.md — 领域分类表（一级分类/二级分类/细分场景枚举，category 字段必须取自此表）
- @references/qc-standards-20260818.md — 质检新增口径（L4 评测项≥24、10 分核心项≥4、Gating 1–2 条、judge.files 禁 golden_output 脏路径改用 reference，以本口径为准）
- templates/test.sh — 平台固定模板（以规范附录 A 为准，逐字复制）
- templates/finalize.py — 平台固定模板（以规范附录 A 为准，逐字复制）
