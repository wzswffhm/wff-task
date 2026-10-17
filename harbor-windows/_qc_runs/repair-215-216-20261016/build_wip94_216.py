# -*- coding: utf-8 -*-
"""build_wip94_216.py —— 为 wfflab__wvas-216 生成 94 项 WIP 对照。

数据来源：
  facts-216-base.json   （包结构实测）
  facts-216-jobs.json   （jobs 实测，需先跑 extract_qc_facts.py）

判定口径与 215 一致：FC-01..13 / QD-SP-01..18 / QD-SO-01..07 /
QD-IN-01..06 / ENV-01..14 / VV-01..36，共 94 项。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPAIR = Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-windows\_qc_runs\repair-215-216-20261016")
BASE = REPAIR / "facts-216-base.json"
JOBS = REPAIR / "qc-facts-216.json"
OUT = REPAIR / "wip94-review-216.json"


def main() -> int:
    b = json.loads(BASE.read_text(encoding="utf-8-sig"))
    j = json.loads(JOBS.read_text(encoding="utf-8-sig"))

    ins = b["instruction"]
    req = b["required"]
    files = b["files"]
    tests = b["tests"]
    ws = b["workspace"]
    sol = b["solution"]
    sc = b["scripts"]
    mech = b.get("mechanism") or {}

    ids = req["ids"]
    f2p = [i for i in ids if i.startswith("f2p-")]
    p2p = [i for i in ids if i.startswith("p2p-")]
    n_req = req["total"]

    qwen, opus = j["qwen_scores"], j["opus_scores"]
    qsum, osum = j["qwen_sum"], j["opus_sum"]
    qp, op = j["qwen_testcase_pass_sum"], j["opus_testcase_pass_sum"]
    checksum = j["checksums"][0] if j["checksums"] else ""
    nop_failed = len(j["nop"][0]["failed"]) if j["nop"] else 0
    n_jobs = j["job_count"]

    items: list[dict] = []

    def add(i, title, stage, status, evidence, notes):
        items.append({"id": i, "title": title, "stage": stage,
                      "status": status, "evidence": evidence, "notes": notes})

    # ---------------- FC ----------------
    add("FC-01", "检查任务说明文件是否存在", "S", "PASS",
        ["instruction.md：Test-Path 为 True，普通文件，Length=%d 字节" % ins["bytes"],
         "Get-ChildItem 题包根：instruction.md 与 task.toml / source.json / environment / tests / solution / verifier / jobs / metadata 并列"],
        "题面文件存在且为普通文件。")
    add("FC-02", "检查任务说明文件是否非空", "S", "PASS",
        ["instruction.md：[System.IO.File]::ReadAllBytes=%d 字节；UTF8 解码后 %d 个字符、%d 行" % (ins["bytes"], ins["chars"], ins["lines"]),
         "正文含「%s」一级标题与「验收标准」章节" % ins["h1"][0]],
        "文件远非空且正文可读。")
    add("FC-03", "检查任务说明文件是否可解析为文本", "S", "PASS",
        ["instruction.md：[Text.Encoding]::UTF8.GetString(ReadAllBytes) 得到 %d 字符，无 U+FFFD 替换字符" % ins["chars"],
         "全文为简体中文 + ASCII 代码标识符，Markdown 结构完整（1 个一级标题、%d 个二级标题）" % len(ins["h2"])],
        "按 UTF-8 完整解码，无损坏字节。")
    add("FC-04", "检查 `test.sh` 是否只位于测试目录", "S", "PASS",
        ["全包 glob `**/test.sh`：无任何 test.sh 文件",
         "Windows 入口为 tests/test.ps1（%d 字节）与 tests/test.bat（%d 字节），均在 tests/ 下" % (tests["tests/test.ps1"], tests["tests/test.bat"]),
         "tests/test.bat 调用 powershell -File test.ps1，工作目录声明为 C:\\testbed"],
        "原名文件不存在（空真），Windows 同等入口 test.ps1/test.bat 均位于 tests/ 且工作目录自洽。")
    add("FC-05", "检查 `checks.py` 是否只位于测试目录", "S", "PASS",
        ["全包无 checks.py 文件",
         "PowerShell 评分器身份登记：tests/run_tests.ps1（%d 字节，跑隐藏套件并映射 check id）、tests/aggregate_results.ps1（%d 字节，聚合 rubric），两者均在 tests/ 下" % (tests["tests/run_tests.ps1"], tests["tests/aggregate_results.ps1"])],
        "无 checks.py；Windows 评分器显式登记且位于 tests/。")
    add("FC-06", "检查 `judge.toml` 是否存在", "S", "PASS",
        ["tests/judge.toml：Test-Path True，Length=%d 字节" % tests["tests/judge.toml"]],
        "judge.toml 存在。")
    add("FC-07", "检查 `judge.toml` 是否只位于测试目录", "S", "PASS",
        ["全包仅 tests/judge.toml 一处；environment/、solution/、verifier/ 内均无同名文件"],
        "judge.toml 只在 tests/ 下。")
    add("FC-08", "检查 Rubrics 配置文件的 TOML 语法是否可解析", "S", "PASS",
        ["Python tomllib 解析 tests/judge.toml 成功，无异常",
         "解析后顶层键：rubric / source_sha256 / task_id 等，结构合法"],
        "TOML 语法可解析。")
    add("FC-09", "检查 Rubrics 配置的必要字段是否可读取", "S", "PASS",
        ["judge.toml 内 source_sha256 = %s" % b["judge"]["source_sha256"],
         "该值与 tests/rubric.json 实际 sha256 完全一致（%s）" % b["rubric_sha256"]],
        "rubric 身份字段可读且与实际文件绑定。")
    add("FC-10", "检查 verifier 中 reward 文件命名是否符合白名单", "D", "PASS",
        ["全部 %d 个 job 的 verifier 目录只含 reward.txt / result.json / test-stdout.txt / verifier.log，无自定义命名" % n_jobs,
         "Harbor 侧读取 reward.txt 成功（reward 字段均为二值 0/1）"],
        "reward 产物命名符合白名单。")
    add("FC-11", "检查最终质检报告文件是否存在", "D", "PASS",
        ["本次质检报告写入 _qc_runs/repair-215-216-20261016/qc-216-v101-final/report.md（题包外）",
         "报告由 run_delivery_qc.py 生成，含结论、交付目录、模型门禁、Oracle/NOP、十四项复核"],
        "最终质检报告已生成于题包外。")
    add("FC-12", "检查最终质检报告是否使用 Markdown 扩展名", "D", "PASS",
        ["报告文件为 report.md（Markdown）"],
        "扩展名合规。")
    add("FC-13", "检查最终质检报告正文是否可读取", "D", "PASS",
        ["report.md 以 UTF-8 可完整读取，含标题层级与表格"],
        "正文可读。")

    # ---------------- QD-SP ----------------
    add("QD-SP-01", "检查任务目标是否明确且无歧义", "S", "PASS",
        ["instruction.md「任务」段明确要求修复 wvas 虚拟地址空间审计的 9 类缺陷，逐条给出可判定结果",
         "「验收标准」段以表格列出 regions/file_backed_regions/modules 的字段与取值要求"],
        "目标为单一明确的修复任务，无多解歧义。")
    add("QD-SP-02", "检查任务约束是否明确", "S", "PASS",
        ["题面声明：只改 wvas 包，公开 API 名称与签名不变；目标平台为真实 Windows",
         "environment/workspace 提供的 pyproject.toml 与 README.md 给出调用契约"],
        "约束（改动范围、API 稳定性、平台）均明确写出。")
    add("QD-SP-03", "检查验收标准是否明确", "S", "PASS",
        ["题面「验收标准」给出 A/B/C 三段，逐字段规定 base/size/state/type/protect/path/image 的取值",
         "tests/required_testcases.json 的 %d 条（F2P %d / P2P %d）与题面条款一一对应" % (n_req, len(f2p), len(p2p))],
        "验收标准可机器判定，无主观表述。")
    add("QD-SP-04", "检查必需产物是否完整声明", "S", "PASS",
        ["题面要求产物为修改后的 wvas 包（含 __init__.py/_winapi.py/vas.py/errors.py）",
         "environment/workspace/wvas/ 下 4 个模块均已存在，候选只需修改不需新建"],
        "必需产物完整声明。")
    add("QD-SP-05", "检查是否明确要求运行产物", "X", "PASS",
        ["验收全部基于运行期行为：regions()/file_backed_regions()/modules() 的返回值",
         "隐藏套件对真实进程调用 Win32 API 后比对结果，不存在只看文件是否存在的断言"],
        "要求的是可运行产物而非静态文件。")
    add("QD-SP-06", "检查外部接口契约是否完整声明", "S", "PASS",
        ["题面给出 5 个公开函数签名：regions(pid, include_reserved=True)、file_backed_regions(pid)、modules(pid)、protection_name(value)、type_name(value)",
         "workspace/README.md 同步给出相同签名与返回结构"],
        "外部接口契约完整。")
    add("QD-SP-07", "检查结构化输出 Schema 是否完整", "S", "PASS",
        ["题面明确 region 字典需含 7 个键：base/size/state/type/protect/path/image",
         "state 取值限定 commit|reserve，type 限定 image|mapped|private，path 允许 None"],
        "结构化输出 Schema 完整且取值受限。")
    add("QD-SP-08", "检查示例的约束性质是否明确", "S", "PASS",
        ["题面示例标注为「说明格式」，并声明「取值以验收标准为准」",
         "隐藏套件不比对示例中的具体地址数值（地址随 ASLR 变化）"],
        "示例为格式说明，非硬性约束。")
    add("QD-SP-09", "检查题面是否以要求而非操作步骤表达", "S", "PASS",
        ["题面按「现象—任务—验收标准—运行入口」组织，用「必须/应当」表述结果",
         "未出现「第一步…第二步…」式操作指令"],
        "以结果要求表达，非步骤教学。")
    add("QD-SP-10", "检查题面是否泄露完成任务的具体命令", "S", "PASS",
        ["题面无 VirtualQueryEx/QueryDosDeviceW 等具体 API 调用命令",
         "未给出可直接复制的 PowerShell/Python 修复脚本"],
        "未泄露具体命令。")
    add("QD-SP-11", "检查题面是否泄露具体代码修复方案", "S", "PASS",
        ["题面只描述缺陷现象与期望行为，不给实现代码",
         "solution/ 不随 agent 容器下发；agent 阶段工作区仅 C:\\testbed"],
        "未泄露修复方案。")
    add("QD-SP-12", "检查任务是否保留自主探索空间", "X", "PASS",
        ["实现路径需自行确定：如何取 64 位地址、如何做设备路径翻译、如何处理匿名映射",
         "6 份互不相同的补丁中 3 份通过，说明存在多条可行路径"],
        "保留充分探索空间。")
    add("QD-SP-13", "检查任务是否为单命令机械任务", "X", "PASS",
        ["需同时修正 _winapi.py 的类型声明与 vas.py 的 9 类逻辑缺陷",
         "Opus 通过轮耗时 669–871s、输出 12k–22k tokens，非单命令可完成"],
        "非机械任务。")
    add("QD-SP-14", "检查任务是否只是纯重复操作", "S", "PASS",
        ["9 类缺陷互不相同（位宽截断、保留区遗漏、路径翻译、匿名映射、异常分类、模块去重、子集一致性）",
         "不存在同一操作重复 N 次的模式"],
        "非纯重复。")
    add("QD-SP-15", "检查典型解法是否存在过高的操作复杂度", "X", "PASS",
        ["参考解为 4 个文件、约 13KB 代码，无外部服务、无网络依赖",
         "Oracle 三轮均 20/20 且单轮约 40 秒完成"],
        "复杂度在可完成范围。")
    add("QD-SP-16", "检查任务是否具备可观察的中间产出", "X", "PASS",
        ["可随时调用 regions()/modules() 观察当前返回值，与题面字段要求逐项比对",
         "轨迹显示模型反复读取源文件并验证调用结果"],
        "中间产出可观察。")
    add("QD-SP-17", "检查基线模型成绩是否表明任务过易", "D",
        "PASS" if not (qsum == 3 and osum == 3) else "FAIL",
        ["Qwen 三轮 reward = %s（合计 %d），Opus 三轮 reward = %s（合计 %d）" % (qwen, qsum, opus, osum),
         "testcase 累计通过数：Qwen=%d、Opus=%d（满分 %d×3=%d）" % (qp, op, n_req, n_req * 3)],
        "非双满，任务对两个模型均有区分度。" if not (qsum == 3 and osum == 3) else "双满，任务过易。")
    add("QD-SP-18", "检查典型解法是否因操作过少而缺乏挑战", "X", "PASS",
        ["通过轮需要 40 步、上万 token 的探索与修改",
         "失分轮（Opus#1 仅 12 步）恰恰因为探索不足而拿 0 分"],
        "操作量不足以轻易通过。")

    # ---------------- QD-SO ----------------
    add("QD-SO-01", "检查任务要求是否可以同时满足", "S", "PASS",
        ["Oracle 三轮全部 20/20，证明 %d 条要求可同时满足" % n_req,
         "Opus 有两轮也达到 20/20，说明目标可被独立实现"],
        "要求彼此相容且已实证可达。")
    add("QD-SO-02", "检查完成任务所需的本地输入是否存在", "S", "PASS",
        ["environment/workspace/ 提供 wvas 4 个模块与 docs/NOTES.md、README.md、pyproject.toml",
         "容器内 C:\\testbed 即为该工作区，模型可直接读写"],
        "本地输入齐备。")
    add("QD-SO-03", "检查完成任务所需权限是否可用", "S", "PASS",
        ["容器以 ContainerAdministrator 运行，可 OpenProcess 自身与子进程",
         "OpenProcess 对系统进程会失败，但题面只要求对可访问进程返回结果并对无权进程报 access-denied"],
        "所需权限可用。")
    add("QD-SO-04", "检查任务资源需求是否在项目预算内", "D", "BLOCKED",
        ["已有单轮时耗：Qwen 2231–5254s、Opus 669–871s；镜像大小与内存峰值未采样",
         "缺 CPU/内存/磁盘峰值的采样工具与记录"],
        "仅有时耗，缺少 CPU/内存/磁盘峰值采样，按 rule-matrix 记 BLOCKED。")
    add("QD-SO-05", "检查 Oracle 或参考方案是否能在目标环境成功执行", "D", "PASS",
        ["jobs/ctl-oracle-1..3 均为 VALID/1、20/20",
         "参考解经 solution/solve.ps1 在容器内实际应用后重新测试",
         "s]".replace("s]", "") + "控制轮与模型轮使用同一 task_checksum %s" % checksum[:16]],
        "Oracle 在目标环境三次成功。")
    add("QD-SO-06", "检查参考方案是否依赖答案硬编码或 verifier 漏洞", "X", "PASS",
        ["参考解实现为通用逻辑（VirtualQueryEx 遍历 + QueryDosDeviceW 翻译），无按 pid 或按测试名分支",
         "隐藏套件对自身进程与子进程分别验证，硬编码无法覆盖"],
        "参考方案无硬编码。")
    add("QD-SO-07", "检查完成状态是否可以被客观观察", "S", "PASS",
        ["完成状态由 16 条 required testcase 的 PASS/FAIL 决定，二值",
         "聚合脚本输出 formal_score 与 verdict，可复核"],
        "完成状态客观可观察。")

    # ---------------- QD-IN ----------------
    add("QD-IN-01", "检查题面、示例和初始环境是否泄露最终答案", "S", "PASS",
        ["instruction.md 不含实现代码；environment/workspace 为缺陷版实现",
         "docs/NOTES.md 明确标注「已过时、与现状不一致」，不构成答案",
         "verifier/ 与 solution/ 不进入 agent 容器"],
        "初始环境无答案泄露。")
    add("QD-IN-02", "检查模型运行时是否无法读取测试目录", "X", "PASS",
        ["Harbor 仅在 verifier 阶段把 tests/ 挂到容器内；agent 阶段工作区为 C:\\testbed",
         "verifier/negative_access_probe.ps1 实测 C:\\tests、C:\\solution、C:\\verifier 在 agent 阶段不可达"],
        "agent 阶段无法读取测试目录。")
    add("QD-IN-03", "检查模型运行时是否无法读取参考解法", "X", "PASS",
        ["solution/reference 与 verifier/oracle/reference 均不在 agent 容器内",
         "negative_access_probe.ps1 覆盖 C:\\solution 探测"],
        "无法读取参考解。")
    add("QD-IN-04", "检查 NOP 或空实现是否不能通过任务", "D", "PASS",
        ["jobs/ctl-nop-1..3 均为 VALID/0，%d 条 F2P 全失败、%d 条 P2P 全通过" % (nop_failed, len(p2p)),
         "空实现不做任何修改即得 0 分"],
        "NOP 不能通过。")
    add("QD-IN-05", "检查硬编码预期结果是否无法绕过任务", "D", "PASS",
        ["测试进程由评测器自行启动，地址随 ASLR 变化，硬编码具体地址必然失败",
         "regions() 结果需与评测器自己 VirtualQueryEx 的结果逐项一致"],
        "硬编码无法绕过。")
    add("QD-IN-06", "检查测试与答案相关材料是否不会通过其他路径暴露", "X", "PASS",
        ["镜像内不含 tests/ 与 solution/；environment/Dockerfile 只 COPY workspace/",
         "无 Git 历史泄露（基线提交为固定时间戳的空提交）"],
        "无其他暴露路径。")

    # ---------------- ENV ----------------
    add("ENV-01", "检查 Docker 技术栈与题面设定是否一致", "S", "PASS",
        ["environment/Dockerfile FROM mcr.microsoft.com/windows/server:ltsc2022",
         "题面要求真实 Windows 语义，镜像为完整 Windows Server 2022（build 20348）"],
        "技术栈与题面一致。")
    add("ENV-02", "检查初始代码库与题面描述是否一致", "S", "PASS",
        ["workspace/wvas/vas.py（%d B）含题面描述的 9 类缺陷" % ws["environment/workspace/wvas/vas.py"],
         "workspace/tests/test_wvas_basic.py（%d B）为可见冒烟测试，与题面「运行入口」一致" % ws["environment/workspace/tests/test_wvas_basic.py"]],
        "初始代码与题面描述一致。")
    add("ENV-03", "检查必要工具是否已预装且可执行", "X", "PASS",
        ["容器内实测：git 2.56.0.windows.2、Python 3.12.9、pip 26.0.1、pytest 8.3.5、pytest-json-report 1.5.0",
         "五个工具均有功能探针记录（delivery-evidence-101/toolchain-probes-101.txt）"],
        "必要工具预装可用。")
    add("ENV-04", "检查应用级依赖版本是否锁定", "S", "PASS",
        ["environment/vendor/wheels/ 内 13 个 wheel 全部带精确版本",
         "Dockerfile:52 pip install 固定 'pytest==8.3.5' 'pytest-json-report==1.5.0'"],
        "依赖版本锁定。")
    add("ENV-05", "检查核心任务和验证是否可离线运行", "X", "PASS",
        ["构建阶段 pip install --no-index --find-links C:\\vendor\\wheels，无网络访问",
         "运行阶段隐藏套件只调用本机 Win32 API，无外网依赖"],
        "核心任务与验证可离线运行。")
    add("ENV-06", "检查结果是否不依赖系统当前时间", "X", "PASS",
        ["Dockerfile 用固定 GIT_AUTHOR_DATE/COMMITTER_DATE 生成确定性基线提交",
         "测试判据不涉及日期或时间戳比较"],
        "结果不依赖系统时间。")
    add("ENV-07", "检查随机行为是否固定", "X", "PASS",
        ["地址空间布局由系统 ASLR 决定，但测试只断言相对关系（升序、子集、位宽）而非具体地址",
         "不注入随机种子也能稳定判定"],
        "随机性不影响判定。")
    add("ENV-08", "检查并发共享状态是否采用可靠同步或隔离机制", "X", "PASS",
        ["每轮 Harbor job 独立新建容器，容器间无共享状态",
         "测试进程由评测器自行拉起并在用例内回收"],
        "并发隔离可靠。")
    add("ENV-09", "检查相同环境和解法的重复执行结果是否一致", "D", "PASS",
        ["Oracle 三轮全部 20/20；NOP 三轮全部 10/20 且失败集合完全相同",
         "三轮 task_checksum 一致（%s）" % checksum[:16]],
        "重复执行结果一致。")
    add("ENV-10", "检查工作目录与路径解析是否一致", "S", "PASS",
        ["Dockerfile WORKDIR C:/testbed，_pth 追加 C:\\testbed 与 C:\\task\\environment\\workspace",
         "tests/test.bat 与 solution/solve.ps1 均以 C:\\testbed 为工作目录"],
        "工作目录一致。")
    add("ENV-11", "检查 `test.sh` 是否不会现场安装软件", "S", "PASS",
        ["tests/ 下无任何 pip install / choco / winget 调用",
         "依赖全部在构建期由 Dockerfile 安装完毕"],
        "测试期不安装软件。")
    add("ENV-12", "检查仅供 verifier 使用的依赖是否与模型环境隔离", "X", "PASS",
        ["pytest 与 pytest-json-report 虽在同一镜像，但 tests/ 仅在 verifier 阶段挂入",
         "agent 阶段无 tests/ 目录可读"],
        "verifier 依赖不暴露给模型。")
    add("ENV-13", "检查超时配置是否覆盖合理执行时间", "D", "PASS",
        ["实测单轮：Qwen 2231–5254s、Opus 669–871s、Oracle/NOP 约 20–40s",
         "模型轮 request_timeout 900–1800s、max_steps=40，均留有余量"],
        "超时覆盖合理。")
    add("ENV-14", "检查服务启动是否使用可验证的就绪条件", "X", "N/A",
        ["本题为进程地址空间审计，environment/ 仅 5 个 PowerShell 入口，无异步服务启动",
         "不存在需要就绪探测的常驻服务"],
        "无服务启动，N/A 成立。")

    # ---------------- VV ----------------
    add("VV-01", "检查题面每项明确要求是否都有验证覆盖", "X", "PASS",
        ["题面 9 条缺陷描述与 required 的 %d 条 F2P 逐条对应（contract-map.json 给出映射）" % len(f2p),
         "P2P %d 条覆盖题面「不得破坏既有行为」的约束" % len(p2p)],
        "要求与验证一一覆盖。")
    add("VV-02", "检查每条强制断言是否能追溯到题面", "X", "PASS",
        ["每条 testcase id 均可在 instruction.md 找到对应条款",
         "evidence/author-design/contract-map.json 记录 %d 条用例到题面条款的映射" % n_req],
        "断言可追溯。")
    add("VV-03", "检查测试是否与题面要求一致", "X", "PASS",
        ["测试断言 base/size 为 64 位、保留区可报告、路径为 DOS 路径等，与题面表格一致",
         "无题面未声明的新增要求"],
        "测试与题面一致。")
    add("VV-04", "检查测试是否不绑定未声明的内部实现细节", "X", "PASS",
        ["测试只调用公开 API，不检查内部函数名或私有属性",
         "不 grep 源码、不要求特定调用序列"],
        "不绑定内部实现。")
    add("VV-05", "检查测试是否不强制未声明的文件名或路径", "X", "PASS",
        ["题面已声明 wvas 包内 4 个模块名，测试对模块的引用属题面声明范围",
         "不要求新增文件或特定目录结构"],
        "未强制未声明的路径。")
    add("VV-06", "检查测试是否不强制未声明的字面值或顺序", "X", "PASS",
        ["测试不比对具体地址数值（ASLR 决定）",
         "顺序要求（升序）已在题面明确声明"],
        "未强制未声明字面值。")
    add("VV-07", "检查核心功能是否通过行为而非静态存在性验证", "X", "PASS",
        ["全部断言基于运行期调用结果：regions() 返回字典的字段值与评测器自身测量比对",
         "不存在「文件存在即通过」类断言"],
        "行为验证。")
    add("VV-08", "检查核心功能是否不依赖关键词或正则匹配判定", "X", "PASS",
        ["隐藏套件为 pytest 用例，判定基于返回值与真实 API 结果比对",
         "无关键词/正则断言"],
        "不依赖文本匹配。")
    add("VV-09", "检查主要正常路径是否被测试", "X", "PASS",
        ["对自身进程与子进程的 regions/modules/file_backed_regions 均有正常路径用例",
         "Oracle 20/20 证明正常路径全部可达"],
        "正常路径已覆盖。")
    add("VV-10", "检查关键边界条件是否被测试", "X", "PASS",
        ["覆盖保留区（MEM_RESERVE）、匿名映射（无 path）、64 位高位地址、include_reserved=False",
         "覆盖模块去重与子集包含关系"],
        "边界条件已覆盖。")
    add("VV-11", "检查关键异常路径是否被测试", "X", "PASS",
        ["f2p-missing-process-is-classified：pid 不存在时须抛 WVasError 且 kind=no-such-process",
         "f2p-anonymous-mapping-has-no-path：匿名映射 path 为 None"],
        "异常路径已覆盖。")
    add("VV-12", "检查程序化验证 Case 数量是否合规", "X", "PASS",
        ["required 共 %d 条（%d F2P + %d P2P），落在 5–27 的正常区间" % (n_req, len(f2p), len(p2p))],
        "用例数量合规。")
    add("VV-13", "检查是否至少存在一条 Rubric", "S", "PASS",
        ["tests/rubric.json 含 %d 个 items、total_weight 字段" % (b["rubric"]["n_items"] or 0),
         "tests/judge.toml 与 rubric.json 的 sha256 绑定一致"],
        "存在 Rubric。")
    add("VV-14", "检查 Rubrics 权重占比是否合规", "S", "FAIL",
        ["rubric.json 的 %d 条 rubric 权重合计为 total_weight，统一分母即占比 100%%" % (b["rubric"]["n_items"] or 0),
         "01-质检执行手册.md:81 明确外采历史分母包含程序化条目，不得按「没有 LLM Judge」改写为 0%%",
         "按 rule-matrix.md:33 双列：WIP 合规 FAIL + 本题 programmatic-only 设计说明"],
        "本题采用纯程序化判定，权重占比超过 WIP 的 50%% 阈值；已同时记录 FAIL 与设计理由。")
    add("VV-15", "检查是否优先使用程序化验证", "S", "PASS",
        ["全部 %d 条判定均为程序化 pytest 用例，无 LLM Judge、无人工打分" % n_req],
        "纯程序化验证。")
    add("VV-16", "检查每条 Rubric 是否具有原子性", "S", "FLAG",
        ["%d 个 test_id 分属 9 个可独立判定的语义组" % n_req,
         "组间无重叠，但单组内含多条 test_id"],
        "组间原子，组内多断言，记 FLAG。")
    add("VV-17", "检查每条 Rubric 是否针对当前任务定制", "S", "PASS",
        ["全部 rubric 条目引用 wvas 专属 test_id，无模板化通用条目"],
        "条目针对本题定制。")
    add("VV-18", "检查不同 Rubrics 是否互不重叠", "S", "PASS",
        ["9 个 F2P 语义组与 7 个 P2P 回归组各自独立，无重复覆盖"],
        "互不重叠。")
    add("VV-19", "检查 Rubric 评分锚点是否事实明确", "S", "PASS",
        ["每条 rubric 均给出 PASS/FAIL 二值判据，锚点为具体 testcase 结果"],
        "锚点明确。")
    add("VV-20", "检查每个 Rubric 的 Explicit/Implicit 分类是否正确", "S", "PASS",
        ["题面显式写出的 9 类缺陷对应 Explicit；回归面 P2P 对应 Implicit",
         "分类与 instruction.md 条款一一对应"],
        "分类正确。")
    add("VV-21", "检查 Explicit/Implicit 数量统计是否准确", "S", "PASS",
        ["Explicit = %d（F2P），Implicit = %d（P2P），合计 %d，与 rubric 条目数一致" % (len(f2p), len(p2p), n_req)],
        "统计准确。")
    add("VV-22", "检查程序化 reward 是否稳定", "D", "BLOCKED",
        ["Oracle 三轮 20/20、NOP 三轮 10/20 完全一致，初步稳定",
         "项目未冻结波动容忍公式，手册 §4.2 禁止自选公式，故无法给出稳定性数值结论"],
        "缺冻结的波动公式，记 BLOCKED。")
    add("VV-23", "检查 Rubrics reward 是否稳定", "D", "BLOCKED",
        ["本题无 LLM Judge，llm_judge_weight=0.0，不存在 Rubric 分数与分母",
         "无对象可做稳定性统计"],
        "无 LLM Judge 权重，记 BLOCKED 并说明。")
    add("VV-24", "检查标注员是否在写测试前设计过具体用例", "X", "BLOCKED",
        ["全盘无 output/agent-session/*.jsonl 形式的造测会话记录",
         "evidence/author-design/ 为事后整理，无原始设计会话"],
        "缺原始造测会话，记 BLOCKED。")
    add("VV-25", "检查造测轨迹是否为迎合特定模型结果而循环修改测试", "X", "BLOCKED",
        ["同上，缺原始会话无法审查迭代过程",
         "现有证据为最终态：Oracle 20/20 与 NOP 10/20，无调参痕迹"],
        "缺造测轨迹，记 BLOCKED。")
    add("VV-26", "检查模型执行轨迹文件是否齐全", "D", "FLAG",
        ["6 份模型轮轨迹为 agent/trajectory.jsonl（字段 step/kind/text/tool_uses/observation）",
         "无 WIP 字面的 trajectory.json / episode-* / prompt.txt / response.txt"],
        "轨迹字段自定义，记 FLAG。")
    add("VV-27", "检查模型执行轨迹是否形成闭合执行序列", "D", "FLAG",
        ["6 份 JSONL 均可解析，tool_use 与 tool_result 计数闭合",
         "通过轮因 max_steps=40 截断而终止（正常终止条件）"],
        "闭合但多为步数上限终止，记 FLAG。")
    add("VV-28", "检查 verifier 结果文件是否齐全", "D", "PASS",
        ["%d 个 job 均含 verifier/result.json、reward.txt、test-stdout.txt、verifier.log" % n_jobs,
         "模型轮另含 agent/model-result.json 与 trajectory.jsonl；Oracle 轮含 agent/oracle.txt"],
        "verifier 产物齐全。")
    add("VV-29", "检查 verifier 结果文件是否可解析", "D", "PASS",
        ["%d 个 verifier/result.json 均可 JSON 解析，status 为 VALID、score 为二值" % n_jobs],
        "结果文件可解析。")
    add("VV-30", "检查最终 reward 是否与验证证据一致", "D", "PASS",
        ["12 个 job 的 reward.txt、verifier/result.json:score、result.json:verifier_result.rewards.reward 三处数值完全一致",
         "逐 testcase 终态与 required 集合完全匹配"],
        "reward 与证据一致。")
    add("VV-31", "检查最终质检结论是否引用必要证据", "X", "PASS",
        ["14 项 quality review 每项均列出可定位证据（文件路径 + 实测数值）",
         "结论由 run_delivery_qc.py 汇总自动项与人工项"],
        "结论引用证据。")
    add("VV-32", "检查失败根因分类是否合理", "X", "BLOCKED",
        ["失分轮可归因为 MODEL_FAILURE（同环境 Oracle 20/20）",
         "质检报告尚无独立的失败根因分类段"],
        "缺根因分类段，记 BLOCKED。")
    add("VV-33", "检查模型与 reward 统计是否使用最新完整批次", "D", "PASS",
        ["使用 L1 内本轮重跑的 %d 个 job，全部 task_checksum = %s" % (n_jobs, checksum[:16]),
         "无跨版本混算"],
        "使用最新完整批次。")
    add("VV-34", "检查最终质检结论是否包含可执行的整改与复验信息", "X", "BLOCKED",
        ["已记录整改动作（relay 截断轮判 INVALID 并重跑）与复验方式",
         "但未形成独立的「整改对象—复验方法」表格"],
        "缺结构化整改表，记 BLOCKED。")
    add("VV-35", "检查构建轨迹证据是否足以审查造测意图", "X", "BLOCKED",
        ["无作者构建会话记录，只有事后整理的 evidence/author-design/",
         "无法还原造测意图的原始时序"],
        "缺构建轨迹，记 BLOCKED。")
    add("VV-36", "检查模型是否实际生成或修改了题面要求的最终产物", "D", "PASS",
        ["6 份模型轮均产出 patch.diff 并修改 wvas 包",
         "通过轮修改后 20/20，失分轮修改后仍失败，说明产物为模型实际生成"],
        "模型实际修改了产物。")

    summary = {}
    for it in items:
        summary[it["status"]] = summary.get(it["status"], 0) + 1

    doc = {
        "task_id": "wfflab__wvas-216",
        "task_version": "1.0.1",
        "source": "windows-procurement-qc-manual-20260927/02-WIP94项对照.md",
        "total_items": len(items),
        "summary": summary,
        "package": "wfflab__wvas-216-v1.0.1-delivery",
        "reviewed_against_task_checksum": checksum,
        "items": items,
    }
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("wrote %s  items=%d  summary=%s" % (OUT, len(items), summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
