# OBM Source 收集说明书

## 项目背景

benchmark（基准测试集）是用来评估模型能力的一整套标准评测题目，评测模型解决问题的正确率、速度和资源消耗。

为了提升模型与目标benchmark相关的能力，使模型在已有评测集上有更好的表现。我们需要领域专家在类似领域/能力上提出历史上不存在公开解决方案的难题，给出专家的解题经验。



## 需求

收集指定组织格式的，基于目标Benchmark类似领域/能力给出的有训练价值的proposal（提案）、提案对应的验证思路 verifier以及专家领域经验（skill）。

### 目标Benchmark

- **terminal\-bench3（或4）**官网：https://www\.tbench\.ai/

- **program\-bench**** **官网：https://programbench\.com/

- **swe\-marathon **官网：https://www\.swe\-marathon\.org/

- **deepSWE **官网：https://deepswe\.datacurve\.ai/

- **froniterSWE **官网：https://www\.frontierswe\.com/


## 三种造题方式

**A\. 现有/新建 Repo \+ 新需求**：基于真实代码仓库，由专家基于benchmark考察的核心能力，原创一项历史上不存在公开解决方案的任务，任务可以是功能开发，复杂缺陷修复，系统迁移、代码重构或持续集成等，具体取决于题目对标的benchmark题目；并且，专家需要根据原创任务设计行为级别的 verifier。严格禁止从已有 commit / PR 倒推题目和答案。 


**B\. 现有软件/System \+ 新目标**：使用现有软件、模型、编译器、机器学习baseline 作为参考，具体取决于题目对标的benchmark题目考察的能力；专家必须在此基础上原创定义新的目标、约束、公开或隐藏的workloads（工作负载）、correctness/performance metric（正确性或性能指标，机器学习领域术语） ，并设计对应的能够防止模型作弊的verifier。这种造题方式一般适合性能优化、program reimplementation（程序重实现）、AI for AI（使用ai训练ai） 等领域的benchmark题目。


**C\. 专家日常工作任务**：专家基于自己真实专业工作中提出一个有现实价值、可程序化验证的代码任务，并构建或提供题目环境（Docker形式）、将解题思路作为skill，标准答案作为verifier。



## 生产流程表

|步骤|描述|要求|示例case|
|---|---|---|---|
|Step1<br>看例子|专家根据自己领域特长从对应benchmark选择擅长类型的题目作为proposal起点（发散源）|专家需要了解benchmark题目考察的具体领域能力是什么，然后才能基于这个出对应查考能力的题目<br>||
|Step2<br>书写proposal|参考benchmark具体题目内容，专家根据领域相近或考察相似能力的现有非benchmark资源，**提出一个proposal**，**并为proposal书写对应的verify（校验手段）**|proposal**必须**按顺序包含以下内容：<br>- A改造思路（在资源上做了什么改造，C类如果没有改造不用写这部分）<br>- B具体改造细节<br>- C概述agent任务内容、解题限制等<br>- D描述任务对模型来说的【难点/能力考察点】**（分点列出，与skill一一对应）**|**A\. 现有/新建 Repo/Source \+ 新需求**：<br><br><br>**B\. 现有软件/System/Source \+ New Objective**：<br><br><br>**C\. 专家日常工作**：<br>```JSON<br>{<br>  "benchmark": "terminal-bench 4",<br>  "domain": "Operations/Logistics/Dispatch Repair",<br>  "releated_question": "freight-dispatch-shift",<br>  "proposal_type": "C",<br>  "allow_network": true,<br>  "proposal": {<br>    "A_modification_idea": "在面向机场运行模拟与地面资源调度方案推演模型 AeroSurface 上增加已发布计划的最小扰动修复能力。",<br>    "B_modification_details": "在仿真推演中注入滑行通道或共享资源的临时关闭事件，并交付 repair_dispatch 接口及独立行为验收，用于回放原计划、模拟异常事件和比较修复方案。",<br>    "C_agent_task": "Agent需要根据已发布的地面资源通行计划和临时资源关闭事件，生成满足约束的修复方案；可调整尚未发出的请求，并在不可修复时返回可核查的 BLOCKED 原因。Agent需要保持原路线各资源段的相对时间偏移；已发出的请求及其后续资源占用不可撤销或平移；尚未发出的请求只能在批准窗口内推迟或取消；按取消权重、取消数量、改变请求数量、加权推迟和稳定起点签名的字典序求全局最优；若关闭与已发出承诺冲突，必须保留原计划。本题使用经过调度系统批准的固定路线，不能自行增加或改道。完整公开契约如下，顶层恰含 now, horizon, buffer, movements, closures。三个时间字段是非布尔整数，字段取值限制0 <= now <= horizon <= 60，0 <= buffer <= 3。时间单位为离散 slot。movements 最多6项，每项恰含 id, weight, start, latest, segments。weight为1到9的整数；0 <= start <= latest <= horizon。segments 为1到4项，每项恰含 resource, offset, duration。resource非空字符串，offset为0到60整数，duration为1到20的整数。offset间隙是已经批准的等待，修复时保持不变。首段offset=0，后段offset至少为前段offset+duration，最后段结束不超过原计划horizon。路线由输入的资源时间线定义。资源可被同一请求多次使用，但含buffer的本请求原时间线不得自相交；所有请求原计划之间也不得资源冲突。原始每段释放时间 start+offset+duration+buffer <= horizon。closures 最多8项，每项恰含 resource, start, end，resource必须存在于原计划，now <= start < end <= horizon。关闭项可重复、重叠，语义取并集。",<br>    "D_task_difficulties": [<br>      "1. 区分已发出承诺和未来可调整请求，保证冻结承诺不被撤销或平移。",<br>      "2. 在临时资源关闭下保持路线各资源段相对时间偏移，并检查资源占用冲突。",<br>      "3. 在批准窗口内对未来请求进行推迟或取消，并按多级字典序目标求全局最优。",<br>      "4. 不可修复时的处理能力，模型需要返回可核查的 BLOCKED 原因，同时保留原计划。"<br>    ]<br>  },<br>  "proposal_sources": "AeroSurface 地面资源与时隙规划程序。随题提供的既有程序、新增修复接口的题面、初始代码、逐行 JSON 入口，放在了 sources/app/下面。本题以该程序和原创修复需求构造机场运行模拟任务，对标的Terminal-Bench 4 的 freight-dispatch-shift 题目作为调度修复能力参照。",<br>  "proposal_scene": "能够实际用于机场运行的离线程序模拟和方案推演，通过在仿真中载入已发布的地面通行计划，帮助推演人员定位需要调整上层决策的条件。",<br>  "proposal_verify": "对合法输入，评测重建含释放 buffer 的半开资源占用，检查已发出请求的整条路线保持原起点且不可取消，未来请求只能在批准窗口内整体推迟或取消，路线偏移保持不变，所有资源占用及关闭均不冲突。若关闭与冻结承诺冲突，必须返回 BLOCKED，完整列出冲突请求并保留全部原计划；否则由独立 oracle 枚举合法起点及取消组合，比较取消权重、取消数量、改变数量、加权推迟及稳定起点签名的完整字典序，必须得到全局最优。原始释放不超过 horizon；修复后的起点受 latest 约束，释放可以越过原 horizon，但越界部分仍须完整检查冲突。验收覆盖等号边界、相接区间、释放缓冲、重复关闭、同资源复访、多段等待、空计划和合法规模上限，并改变请求标识、排列、窗口、权重及关闭组合，检查输入不被修改、重复调用与合法重排结果一致。非法字段、类型、范围、重复 ID 或不安全原计划应输出 ValueError 错误封装，随后仍能处理下一行。通过 sources/verify.py 对提交目录执行全部主验收与边界检查；核对返回字段、类型和按 ID 排序的结果。所有检查通过、协议正常且每个输入完整收发不超过 30 秒才算完成。",<br>  "expert_experience_skill": "模型需要把已执行承诺与未来可调整决策分开建模。决策时间的等号边界影响了请求是否仍然能够撤回，因此不要依据请求是否已完成才决定冻结。冻结意味着原承诺的后续资源仍被占用，不能只保留过去的片段。资源占用应包括交接和释放缓冲，关闭也必须在同一物理占用口径下检查。路线中存在等待时，平移起点与重新安排每个路段是两类不同的操作；先明确授权调整的自由度。半开区间接触不构成冲突，可用独立占用栅格在小范围内核对实现。运营承诺通常不适合单一加权和。若业务先保留高价值请求、再减少变更次数、最后优化延误，应保留字典序目标，不能凭经验选择巨大权重近似。尤其要注意“较少改变请求”优先于“更短总延误”。模型还应该建立小规模精确求解，作为性能优化时的对照；剪枝只使用单调的目标下界。重排输入后应保持相同结果，最终并列选择必须由业务明确的稳定标识决定。\n\n若突发关闭与已经发出的不可撤销承诺矛盾，应报告不可修复的原因并保持原状态。"<br>}<br>```<br>|
|Step3<br>书写skill<br>|专家书写解决了【难点/能力考察点】的skill。<br>**注意，不能有对verify的泄漏。**|skill要从解决题目难点的角度写，不能从verify中逆推的角度来写（这样属于Hack，泄漏了答案）。<br>**（分点列出，与D描述任务对模型来说的【难点/能力考察点】一一对应）**<br>||
|Step4<br>交付|专家按照要求格式交付数据<br>|- 交付文件层级（交付格式压缩包，包名与最外层文件夹一致）<br>    ```JSON<br>    {bench_name}_{proposal_name} # 从这一层压缩<br>    ├── proposal.json<br>    └── sources  # 离线source（例如具体修改的代码文件，工作数据，verifier需要的数据等，形式不限）放到该目录下<br>          └── ...<br>    ```<br>- proposal\.json 字段（**所有字段均采用自然语言描述，需要人工，禁止AI生成**）<br>    ```JSON<br>    {<br>      "benchmark": "terminal_bench3"|"terminal_bench4"|"programbench"|"swe_marathon"|"deepSWE"|"froniterSWE", // proposal关联的benchmark<br>      "domain": "Science/Biology", // 填写当前case属于哪个领域，用英文填写，子domain（如果存在）通过"/"进行表示，以TB为例，最多3层（大领域-子领域-训练的能力领域）<br>      "related_question": "atrx-vep-crispr", // 填写当前proposal与和原benchmark关联的题目是哪一个，写任务名<br>      "proposal_type": "A" | "B" | "C", // 可选值：A、B、C；填写造题方式类别<br>      "allow_network": true, // 是否允许agent联网解题；true表示允许联网，false表示不允许联网<br>      "proposal": {<br>          "A_modification_idea": "string", // A改造思路（在资源上做了什么改造，C类如果没有进行改造则不用写）<br>          "B_modification_details": "string", // B具体改造细节<br>          "C_agent_task": "string", // C概述agent任务内容（包括任务限制等）<br>          "D_task_difficulties": [ //D描述任务难点/考察点（分点列出）<br>              "string",<br>              "string",<br>              "..."]<br>          }, <br>      "proposal_sources": "string", // 该proposal涉及到的资源（比如基于github上某个repo提出了一个新的打包方式，那么需要给出该repo地址；如果是小众软件，给出对应官网或软件准确名称;如果来自专家工作，需要提供工作相关数据，等等）<br>      "proposal_scene": "string", // 言简意赅的说明，提出的proposal如果实现，可以真实应用在什么场景<br>      "proposal_verify": "string", // 如何验证这个proposal是否已经实现,验证思路<br>      "expert_experience_skill": "string" // 专家自身经验技能，基于任务难点/考察点书写（假设一个人之前并不能实现该proposal，但是通过这个专家经验就能实现）<br>    }<br>    ```||

```JSON
{
  "benchmark": "terminal_bench3",
  "domain": "Science/Biology",
  "related_question": "atrx-vep-crispr",
  "proposal_type": "A",
  "allow_network": true,
  "proposal": {
    "A_modification_idea": "string",
    "B_modification_details": "string",
    "C_agent_task": "string",
    "D_task_difficulties": [
      "string",
      "string",
      "..."
    ]
  },
  "proposal_sources": "string",
  "proposal_scene": "string",
  "proposal_verify": "string",
  "expert_experience_skill": "string"
}
```

## 数据质量评价

1. 首轮格式达标，内容相关，不存在下列情况，符合手册要求。验证使用OBM-review-skills/references/checklist.md。

    ### 拒绝验收的情况

    - proposal存在矛盾/错误、不存在可能解

    - 从公开 commit / PR 倒推任务

    - 解决方案 与已有 patch 高度相似

    - 修改公开 benchmark 的名字/数字形成新题；

    - Verifier 只是复制已有 tests

    - 专家说不清 verify和 test 为什么存在，也不知道出的题目怎么做

    - Skill 只是通用 coding 流程，未起到帮助

    - Skill 泄漏或基于test书写

    - 任务可以通过搜索直接找到 solution

2. 使用agent workflow验证proposal/skill 实际质量

    1. porposal与verify的真实价值，**Doubao\-Seed\-Evolving不能做对或超长轮次（\>100轮）才能做对。**

    2. skill质量，根据a满足下列其一；

        1. seed在no\-skill下无法做对，with\-skill后能够做对。

        2. 或超长轮次使用skil后轮次与时长显著降低（降低30%\+）。

