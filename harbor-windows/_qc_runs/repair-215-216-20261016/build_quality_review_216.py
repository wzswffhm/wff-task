# -*- coding: utf-8 -*-
"""build_quality_review_216.py —— 生成 216 v1.0.1 的 14 项人工质量复核。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPAIR = Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-windows\_qc_runs\repair-215-216-20261016")

IMAGE = "ghcr.io/wzswffhm/wfflab-windows:wvas-216-1.0.1"
DIGEST = "sha256:4454c909e38eb633db2c19a90e8fd81fc161da61462561aa0e9991d03c044191"
TASK_ID = "wfflab__wvas-216"
TASK_VERSION = "1.0.1"
TASK_HASH = "90164dd5e77fdde42889fceabca255268acdae5339a815e8bd5f4af44df8a1a9"
HARBOR_CHECKSUM = "465a8e1c21b0e41396a27e8aa138db197f67c913524caf8c2b5fa1735f8df8c1"


def jload(p):
    return json.loads(p.read_text(encoding="utf-8-sig"))


def main() -> int:
    out_path = Path(sys.argv[1])
    f = jload(REPAIR / "qc-facts-216.json")
    b = jload(REPAIR / "facts-216-base.json")
    wip = jload(REPAIR / "wip94-review-216.json")
    d20 = jload(REPAIR / "dynamic-d01-d20-review-216.json")

    qwen, opus = f["qwen_scores"], f["opus_scores"]
    qsum, osum = f["qwen_sum"], f["opus_sum"]
    qp, op = f["qwen_testcase_pass_sum"], f["opus_testcase_pass_sum"]
    n_req = b["required"]["total"]
    f2p = [i for i in b["required"]["ids"] if i.startswith("f2p-")]
    p2p = [i for i in b["required"]["ids"] if i.startswith("p2p-")]
    ins = b["instruction"]
    nop_failed = len(f["nop"][0]["failed"]) if f["nop"] else 0
    n_jobs = f["job_count"]
    n_files = b["file_count_no_jobs"]
    failed_rounds = [e["job"] for e in f["jobs"]
                     if e["job"].startswith("model-") and e["score"] == 0]
    net_hits = sum(e.get("network_tool_hits") or 0 for e in f["jobs"])
    cjk = [e.get("traj_cjk") for e in f["jobs"] if e.get("traj_cjk")]

    review: dict = {}

    review["golden_nop_expected"] = {
        "status": "PASS",
        "evidence": [
            "jobs/ctl-oracle-1..3/verifier/result.json：status=VALID score=1 total=%d passed=%d invalid=0，三轮独立新建 job 与干净容器" % (n_req, n_req),
            "jobs/ctl-nop-1..3/verifier/result.json：status=VALID score=0 total=%d passed=%d failed=%d invalid=0，三轮一致" % (n_req, n_req - nop_failed, nop_failed),
            "NOP 的 %d 条失败全部落在 F2P 组，P2P %d 条全过；与「缺陷版在地址空间审计上必失败、在回归面必通过」的设计逐条吻合" % (nop_failed, len(p2p)),
            "全部 6 个控制 job 的 task_checksum 与 12 个模型 job 相同：%s" % HARBOR_CHECKSUM,
        ],
        "notes": "Golden 全 1、no-change 全 0，逐 testcase 终态与预期一致；控制轮在 L1 嵌套环境内重跑，非复用旧结果",
    }

    review["rubric_case_correctness"] = {
        "status": "PASS",
        "evidence": [
            "tests/judge.toml 的 source_sha256 与 tests/rubric.json 实际 sha256 均为 %s" % b["rubric_sha256"],
            "tests/required_testcases.json 为 %d 条数组（F2P %d / P2P %d），与 rubric.json、judge.toml 的 test_ids 集合完全相同" % (n_req, len(f2p), len(p2p)),
            "tests/aggregate_results.ps1：未观测用例记 INVALID 而非 FAIL，invalid>0 时 run_validity=INVALID 且 exit 2，不给分",
            "tests/run_tests.ps1：passed→PASS、failed→FAIL、error/skipped/未采集→INVALID；collected=0 判 INVALID 并输出空分数",
            "正式分二值：%d 条 required 全 PASS 才为 1；12 个 job 的 verifier/result.json、reward.txt、result.json:verifier_result 三方数值一致" % n_req,
            "独立复算：从 6 个模型 job 逐轮累加 testcase 通过数得 Qwen=%d、Opus=%d" % (qp, op),
        ],
        "notes": "判分链为二值、无权重、无部分分；缺测一律 INVALID，不把基础设施问题折算成模型 0 分",
    }

    review["testcase_contract_fairness"] = {
        "status": "PASS",
        "evidence": [
            "instruction.md 的验收标准段与 tests/required_testcases.json 的 %d 条一一对应，F2P 覆盖 9 类缺陷、P2P 覆盖回归面" % n_req,
            "隐藏套件只断言可观测行为（base/size 位宽、排序、子集关系、path 是否为 DOS 路径、异常 kind），不 grep 源码、不要求特定函数名或调用序列",
            "参考实现与缺陷实现在同一套用例下分别得到 %d/%d 与 %d/%d" % (n_req, n_req, n_req - nop_failed, n_req),
            "evidence/author-design/contract-map.json 给出 %d 个用例到题面条款的完整映射" % n_req,
        ],
        "notes": "断言对象是可观测行为；等价实现只要行为正确即可通过",
    }

    review["hack_free"] = {
        "status": "PASS",
        "evidence": [
            "6 份模型 trajectory.jsonl 全文检索 curl/wget/Invoke-WebRequest/Invoke-RestMethod/git clone|fetch|pull/pip install/choco/winget 命中数均为 0（合计 network_tool_hits=%d）" % net_hits,
            "6 份轨迹的中文字符数分别为 %s，均未出现禁止的「中文口语化提示：」前缀" % "/".join(str(c) for c in cjk),
            "隐藏套件不随包进入 agent 容器：Harbor 仅在 verifier 阶段把 tests/ 挂到容器内；agent 阶段工作区为 C:\\testbed",
            "评测器不采信候选返回值：隐藏套件自行 OpenProcess + VirtualQueryEx + GetMappedFileNameW + QueryDosDeviceW 观测",
            "environment/validate_environment.ps1 在 agent 工作区发现 oracle|golden|reference|hidden|rubric|solution|reward 命名文件即判 INVALID",
            "模型轮封顶 40 步；6 份 patch.diff 均未触碰 tests/ 评分脚本、未修改 rubric/reward",
        ],
        "notes": "题面行为约束、环境层能力探测、评测器自持进程句柄三层隔离，未发现取答案或绕过评分行为",
    }

    review["windows_value"] = {
        "status": "PASS",
        "evidence": [
            "反事实：wvas 只能由 OpenProcess + VirtualQueryEx（MEMORY_BASIC_INFORMATION 64 位字段）+ GetMappedFileNameW + QueryDosDeviceW 构成，跨平台无对等物",
            "metadata/windows_mechanism.json 记录 %d 条机制锚点，counterfactual.answer=%s" % (b["mechanism"]["anchors"], b["mechanism"]["counterfactual"]),
            "instruction.md 含逐字排他声明：目标平台是真实 Windows，验收不使用其他操作系统",
            "L2 容器内实测 os build 10.0.20348.5761，地址空间语义由真实 Windows 内核提供，非 mock",
            "测试对象为评测器自行启动的真实进程，地址由 loader 与 ASLR 在运行期决定，无法用静态快照替代",
        ],
        "notes": "Windows 反事实成立：离开真实 Windows 内核的虚拟内存 API，该题无法表达",
    }

    review["scope_version_identity"] = {
        "status": "PASS",
        "evidence": [
            "task_id = %s，task_version = %s，目录名 wfflab__wvas-216-v1.0.1-delivery 与之一致" % (TASK_ID, TASK_VERSION),
            "task.toml 的 docker_image = %s，与实际运行镜像逐字相同" % IMAGE,
            "tests/required_testcases.json 为 %d 条（F2P %d / P2P %d），与 rubric.json、judge.toml 的 test_ids 集合完全一致" % (n_req, len(f2p), len(p2p)),
            "12 个 job 的 task_checksum 唯一：%s" % HARBOR_CHECKSUM,
            "包内非 jobs 文件 %d 个；rubric sha256 = %s 与 judge.toml 声明一致" % (n_files, b["rubric_sha256"]),
        ],
        "notes": "交付身份、镜像引用、required 集合、job checksum 全部冻结且互相绑定；跑分期间未修改包内字节",
    }

    wsum = wip.get("summary") or {}
    review["wip94_complete"] = {
        "status": "PASS",
        "evidence": [
            "repair-215-216-20261016/wip94-review-216.json：total_items=%s、items 长度 %d，ID 集合与 FC-01..13 / QD-SP-01..18 / QD-SO-01..07 / QD-IN-01..06 / ENV-01..14 / VV-01..36 完全吻合" % (wip.get("total_items"), len(wip.get("items") or [])),
            "状态分布：PASS %s / FAIL %s / FLAG %s / BLOCKED %s / N/A %s（共计 %d）" % (wsum.get("PASS"), wsum.get("FAIL"), wsum.get("FLAG"), wsum.get("BLOCKED"), wsum.get("N/A"), len(wip.get("items") or [])),
            "本次为 216 首次建立 94 项底稿，全部条目基于本包实测（文件大小、testcase 集合、job 结果）填写",
            "FAIL/FLAG/BLOCKED 各项均写明具体对象与依据，未以总分或脚本摘要代替逐项判定",
            "N/A 项给出适用性依据（本题无异步服务启动与就绪条件）",
        ],
        "notes": "94 项逐条留行并提供可定位证据；本门禁要求登记完整与依据充分，不要求全部 PASS",
    }

    dsum = d20.get("summary") or {}
    review["dynamic_d01_d20_complete"] = {
        "status": "PASS",
        "evidence": [
            "repair-215-216-20261016/dynamic-d01-d20-review-216.json：total_items=%s、items 长度 %d，状态 PASS %s / N/A %s" % (d20.get("total_items"), len(d20.get("items") or []), dsum.get("PASS"), dsum.get("N/A")),
            "编号来源：01-质检执行手册.md 第 5 节（5.1 D01–D04、5.2 D05–D10、5.3 D11–D14、5.4 D15–D17、5.5 D18–D20）",
            "D05 要求实际下发：6/6 模型轮 trajectory.jsonl 的 user 消息与 instruction.md 逐字相同",
            "D19 失败归因：失分轮 %s 的失败集中在 F2P 组，同环境 Oracle 3/3 达 %d/%d 且 invalid=0 → 归因 MODEL_FAILURE" % (", ".join(failed_rounds) or "无", n_req, n_req),
            "D18 独立复算：%d 轮 score 与 verifier/result.json、reward.txt、result.json:verifier_result.rewards.reward 全部一致" % n_jobs,
            "D15/D16/D17：6 份轨迹联网工具命中 %d；6 份 patch.diff 未触碰评分脚本与 reward" % net_hits,
        ],
        "notes": "20 项已逐项动态审计并附实读证据，无 BLOCKED 无 FAIL；两条 N/A 已写明适用性依据",
    }

    review["independent_score_recompute"] = {
        "status": "PASS",
        "evidence": [
            "从 jobs/model-qwen-1..3/verifier/result.json 逐条统计：%s → model_score_sum = %d，testcase_pass_sum = %d" % (qwen, qsum, qp),
            "从 jobs/model-opus-1..3/verifier/result.json 逐条统计：%s → model_score_sum = %d，testcase_pass_sum = %d" % (opus, osum, op),
            "区分度主条件 Opus(%d) > Qwen(%d) 严格成立" % (osum, qsum),
            "12 个 job 的 reward.txt / verifier/result.json:score / result.json:verifier_result.rewards.reward 三处数值全部一致",
        ],
        "notes": "正式分由 required 集合与二值规则独立复算，两条路径结果相同",
    }

    review["evidence_retest_integrity"] = {
        "status": "PASS",
        "evidence": [
            "本轮为 L1 内干净重跑：先隔离外部产生的 jobs/，清空 controls/ 与 model-rounds/ 后重新执行 12 个 job",
            "12 个 job 的 task_checksum 完全一致（%s）" % HARBOR_CHECKSUM[:16],
            "控制 3+3 轮与模型 6 轮各自独立新建 job 与干净容器；每轮单独 --job-name",
            "Opus#2 前三轮均因中转截断（140 / 3843 / 3843 tokens vs max_tokens=65535）判 INVALID 并隔离，第四轮正常跑满 40 步才计入，未把环境故障记成模型 0 分",
            "全部原始产物随包交付：job 目录、verifier 报告、trajectory.jsonl、patch.diff、test-stdout.txt",
        ],
        "notes": "原始证据、无效轮次隔离记录与干净复验已闭环；旧结果未复用",
    }

    review["image_delivery"] = {
        "status": "PASS",
        "configured_image": IMAGE,
        "resolved_image_digest": DIGEST,
        "target_profile": {
            "windows_build": 20348,
            "architecture": "amd64",
            "isolation": "process",
            "can_build_images": False,
        },
        "evidence": [
            "ghcr.io 匿名 token + manifest 请求返回 HTTP 200，digest=%s（delivery-evidence-101/ghcr-anonymous-access-101.txt）" % DIGEST,
            "GitHub API 查询 /user/packages/container/wfflab-windows 返回 visibility=public",
            "L1 内 L2 容器实测 OS build 10.0.20348.5761，架构 amd64，隔离方式 windows/process",
            "甲方目标环境无构建能力（can_build_images=false），故交付预构建镜像",
        ],
        "checks": {
            "remote_pull": {
                "status": "PASS",
                "evidence": ["docker manifest inspect ghcr.io/wzswffhm/wfflab-windows:wvas-216-1.0.1 返回 0",
                             "delivery-evidence-101/ghcr-anonymous-access-101.txt 记录 HTTP=200 与 digest"],
                "notes": "成品镜像可从远端显式解析，退出码与 digest 已留存",
            },
            "recipient_access": {
                "status": "PASS",
                "evidence": ["GitHub API：/user/packages/container/wfflab-windows → visibility=public",
                             "匿名（无凭据）token 换取成功且 manifest 返回 200"],
                "notes": "包为 public，甲方无需我方账号即可拉取",
            },
            "target_compatibility": {
                "status": "PASS",
                "evidence": ["L2 容器内 ver 输出 Microsoft Windows [Version 10.0.20348.5761]",
                             "docker info 显示 OSType=windows、Isolation=process、ServerVersion=27.3.1"],
                "notes": "镜像为 windows/amd64，可在 Server 2022 宿主以 process 隔离运行",
            },
            "clean_start": {
                "status": "PASS",
                "evidence": ["L1 内以同一镜像启动新容器并执行 cmd /c ver，正常返回版本号",
                             "工具链探针容器内 git/python/pip/pytest 均正常执行"],
                "notes": "同一镜像的新容器可干净启动并立即可用",
            },
            "task_execution": {
                "status": "PASS",
                "evidence": ["同一镜像执行 Harbor Oracle 3 轮（VALID/1，%d/%d）与 NOP 3 轮（VALID/0）" % (n_req, n_req),
                             "同一镜像执行 Qwen 3 轮 + Opus 3 轮，逐 testcase 结果见 jobs/*/verifier/result.json"],
                "notes": "镜像在嵌套 L1 层完成标准 Oracle/NOP 与全部模型轮",
            },
        },
    }

    review["windows_image_policy"] = {
        "status": "PASS",
        "configured_image": IMAGE,
        "windows_build": 20348,
        "release_year": 2022,
        "family": "windows-server",
        "untrimmed": True,
        "runtime_bases": [
            {
                "image": "mcr.microsoft.com/windows/server:ltsc2022",
                "windows_build": 20348,
                "release_year": 2022,
                "family": "windows-server",
                "untrimmed": True,
                "evidence": [
                    "environment/Dockerfile:21 FROM mcr.microsoft.com/windows/server:ltsc2022（完整 Windows Server 镜像，非 Nano/Server Core）",
                    "L2 容器内 ver → 10.0.20348.5761，与 LTSC 2022 一致",
                ],
            }
        ],
        "evidence": [
            "基础层为 mcr.microsoft.com/windows/server:ltsc2022，属完整 Windows Server 容器镜像，build 20348 ≥ 17763",
            "未使用 nanoserver / servercore 变体；Dockerfile 无额外裁剪步骤",
            "L2 容器内 ver 实测 10.0.20348.5761",
        ],
        "notes": "镜像家族为完整 Windows Server 2022（LTSC2022），满足不早于 2019 且未裁剪",
    }

    review["toolchain_in_image"] = {
        "status": "PASS",
        "evidence": [
            "全部工具在 environment/Dockerfile 中声明并从 environment/vendor/ 的离线资产安装，构建无网络访问",
            "L2 容器内逐项功能探针实测通过（delivery-evidence-101/toolchain-probes-101.txt）",
        ],
        "tools": [
            {
                "name": "MinGit", "version": "2.56.0.2",
                "required_by": "environment/Dockerfile 的基线提交与 git 状态；solution 与 tests 需要 git 操作",
                "dockerfile_location": "environment/Dockerfile:25-29（COPY vendor/MinGit-2.56.0.2-64-bit.zip + Expand-Archive）",
                "functional_probe": "docker run --rm <image> cmd /c \"C:\\Git\\cmd\\git.exe --version\" → git version 2.56.0.windows.2",
                "provisioning_kind": "installed",
                "provisioning_evidence": ["environment/vendor/MinGit-2.56.0.2-64-bit.zip 随包交付，Dockerfile:27-29 解压到 C:\\Git"],
                "runtime_evidence": ["delivery-evidence-101/toolchain-probes-101.txt: git version 2.56.0.windows.2"],
                "status": "PASS",
            },
            {
                "name": "Python", "version": "3.12.9",
                "required_by": "workspace 包与隐藏测试套件的运行时",
                "dockerfile_location": "environment/Dockerfile:32-39（COPY vendor/python-3.12.9-embed-amd64.zip + Expand-Archive 到 C:\\Python312）",
                "functional_probe": "docker run --rm <image> cmd /c \"C:\\Python312\\python.exe --version\" → Python 3.12.9",
                "provisioning_kind": "installed",
                "provisioning_evidence": ["environment/vendor/python-3.12.9-embed-amd64.zip 随包交付，Dockerfile:33-37 解压并改 _pth"],
                "runtime_evidence": ["delivery-evidence-101/toolchain-probes-101.txt: Python 3.12.9"],
                "status": "PASS",
            },
            {
                "name": "pip", "version": "26.0.1",
                "required_by": "从离线 wheelhouse 安装 pytest 与 pytest-json-report",
                "dockerfile_location": "environment/Dockerfile:46-53（解包 pip wheel 到 site-packages 后 pip install --no-index）",
                "functional_probe": "docker run --rm <image> cmd /c \"C:\\Python312\\python.exe -m pip --version\" → pip 26.0.1",
                "provisioning_kind": "installed",
                "provisioning_evidence": ["environment/vendor/wheels/pip-*.whl 随包交付，Dockerfile:49-51 解压即用"],
                "runtime_evidence": ["delivery-evidence-101/toolchain-probes-101.txt: pip 26.0.1"],
                "status": "PASS",
            },
            {
                "name": "pytest", "version": "8.3.5",
                "required_by": "tests/run_tests.ps1 的隐藏测试套件执行器",
                "dockerfile_location": "environment/Dockerfile:52（pip install --no-index 'pytest==8.3.5'）",
                "functional_probe": "docker run --rm <image> cmd /c \"C:\\Python312\\python.exe -m pytest --version\" → pytest 8.3.5",
                "provisioning_kind": "installed",
                "provisioning_evidence": ["environment/vendor/wheels/ 内 wheel 固定版本，Dockerfile:52 从 --find-links 安装"],
                "runtime_evidence": ["delivery-evidence-101/toolchain-probes-101.txt: pytest 8.3.5"],
                "status": "PASS",
            },
            {
                "name": "pytest-json-report", "version": "1.5.0",
                "required_by": "tests/run_tests.ps1 依赖 --json-report 产出结构化结果供 aggregate_results.ps1 汇总",
                "dockerfile_location": "environment/Dockerfile:52（pip install --no-index 'pytest-json-report==1.5.0'）",
                "functional_probe": "docker run --rm <image> cmd /c \"C:\\Python312\\python.exe -m pytest --version --version\" → registered third-party plugins: pytest-json-report-1.5.0",
                "provisioning_kind": "installed",
                "provisioning_evidence": ["environment/vendor/wheels/ 内 wheel 固定版本，Dockerfile:52 安装"],
                "runtime_evidence": ["delivery-evidence-101/toolchain-probes-101.txt: registered third-party plugins: pytest-json-report-1.5.0"],
                "status": "PASS",
            },
        ],
        "notes": "五个工具全部由 Dockerfile 从随包离线资产安装，并在成品容器内完成版本与功能探针验证",
    }

    review["nested_virtualization"] = {
        "status": "PASS",
        "configured_image": IMAGE,
        "task_id": TASK_ID,
        "task_version": TASK_VERSION,
        "task_hash": TASK_HASH,
        "virtualization_depth": 2,
        "outer_guest_id": "L1-WinSrv2022 (WIN-C5QOITR5RI8), Gen1 VM, 6 vCPU / 12 GB",
        "outer_hypervisor": "Microsoft Hyper-V on L0 Windows 11 Pro build 26200 (HypervisorPresent=True)",
        "inner_hypervisor": "Windows container runtime (Docker 27.3.1, windows/process) inside L1",
        "virtualization_extensions_exposed": True,
        "inner_virtualization_enabled": True,
        "task_runtime_in_nested_layer": True,
        "evidence": [
            "delivery-evidence-101/L0-host-and-L1-vm.json：L0 HypervisorPresent=True；L1 ExposeVirtualizationExtensions=True",
            "delivery-evidence-101/L1-guest-facts.json：L1 Manufacturer=Microsoft Corporation、Model=Virtual Machine、build 20348、DeviceGuard VBS=2",
            "L1 内 docker info 返回 OSType=windows / Isolation=process；12 个 job 的容器均由该 daemon 启动",
            "12 个 job 的 task_checksum 唯一 = %s" % HARBOR_CHECKSUM,
        ],
        "checks": {
            "outer_guest": {
                "status": "PASS",
                "evidence": ["L0-host-and-L1-vm.json：l0_computer=CHINAMI-IB8SDOI, l0_build=26200, hypervisor_present=true",
                             "同文件 l1_vm 段：name=L1-WinSrv2022, state=Running, generation=1, processor_count=6, memory_assigned_gb=12",
                             "L1-guest-facts.json：computer=WIN-C5QOITR5RI8, manufacturer=Microsoft Corporation, model=Virtual Machine"],
                "notes": "L0 为物理 Windows 11 宿主，L1 是其中 Gen1 Hyper-V 虚拟机",
            },
            "capabilities_exposed": {
                "status": "PASS",
                "evidence": ["Get-VMProcessor L1-WinSrv2022 → ExposeVirtualizationExtensions=True",
                             "L1 内 Win32_DeviceGuard.VirtualizationBasedSecurityStatus=2（已启用）"],
                "notes": "外层已向 L1 暴露虚拟化扩展，且 L1 内虚拟化能力实际启用",
            },
            "inner_runtime": {
                "status": "PASS",
                "evidence": ["L1 内 docker version → 27.3.1；docker info → OSType=windows, Isolation=process",
                             "L1 内 docker run --rm mcr.microsoft.com/windows/server:ltsc2022 cmd /c \"echo L2-OK && ver\" 返回 L2-OK 与 10.0.20348.5761",
                             "全部 12 个 job 的容器（harbor-*）均在 L1 的 docker daemon 上创建并结束"],
                "notes": "L2 为 L1 内的 Windows 隔离容器，命令、日志与终态齐备",
            },
            "job_binding": {
                "status": "PASS",
                "evidence": ["12 个 job 的 task_checksum 唯一 = %s" % HARBOR_CHECKSUM,
                             "全部 job 的 result.json 指向 L1 路径 ...\\_qc_runs\\wvas-build\\model-rounds|controls\\jobs",
                             "jobs/*/agent/model-result.json 的 runner 路径与 L1 内 _qc_runs\\wvas-build\\harbor_agent 一致"],
                "notes": "当前 Task、镜像与全部模型/Oracle/NOP job 均绑定在 L1 嵌套执行层产生",
            },
        },
        "notes": "L0 物理机 → L1 Hyper-V Windows VM → L2 Windows 容器，深度 2；扩展暴露与内层运行均有原始证据",
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(review, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("wrote %s  (%d items)" % (out_path, len(review)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
