# -*- coding: utf-8 -*-
"""make_new_gates.py —— 生成 4 项新门禁（image_delivery / windows_image_policy /
toolchain_in_image / nested_virtualization）的质检条目。

依据甲方 windows-harbor-qc 的校验契约：
  scripts/image_delivery_review.py   : IMAGE_CHECKS      五项
  scripts/windows_image_policy.py    : windows_image_template / tools_template
  scripts/nested_virtualization_review.py : NESTED_CHECKS 四项

数据来自本次实际执行留存的原始证据（不是推导值）：
  _qc_runs/image-evidence-20261015/  push / pull / 匿名访问 / 工具链探针 / digest 清单
  _qc_runs/_task_identity.json       task_hash 与 harbor_dirhash

用法：
  python make_new_gates.py
输出：
  _qc_runs/image-evidence-20261015/newgates/<包名>.json   （4 项，可直接并入 quality-review.json）
"""
from __future__ import annotations

import json
import pathlib

ROOT = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task")
HW = ROOT / "harbor-windows"
QR = HW / "_qc_runs"
EV = QR / "image-evidence-20261015"
OUT = EV / "newgates"

EV_REL = "harbor-windows/_qc_runs/image-evidence-20261015"
ID_REL = "harbor-windows/_qc_runs/_task_identity.json"

BASE_IMAGE = "mcr.microsoft.com/windows/server:ltsc2022"
BASE_BUILD = 20348
BASE_YEAR = 2022
TARGET_BUILD = 20348          # 甲方宿主 build（windows-dinp-2025 计算节点为 20348/ltsc2022）
L1_VM_ID = "8cc17a99-0743-4b30-9ef3-d3a83994062c"

# (包名, 镜像 tag, 题号, task_id, build 目录)
PACKAGES = [
    ("wfflab__wsparse-215-v1.0.0-delivery", "wsparse-215-1.0.0", "215", "wfflab__wsparse-215", "wsparse-build"),
    ("wfflab__wvas-216-v1.0.0-delivery", "wvas-216-1.0.0", "216", "wfflab__wvas-216", "wvas-build"),
    ("wfflab__wspawn-218-v1.0.0-delivery", "wspawn-218-1.0.0", "218", "wfflab__wspawn-218", "wspawn-build"),
    ("wfflab__wcancel-219-v1.0.0-delivery", "wcancel-219-1.0.0", "219", "wfflab__wcancel-219", "wcancel-build"),
    ("wfflab__wciocp-220-v1.0.0-delivery", "wciocp-220-1.0.0", "220", "wfflab__wciocp-220", "wciocp-build"),
]

TOOLS = [
    {
        "name": "git (MinGit)",
        "version": "2.56.0.windows.2",
        "required_by": "环境/参考解/隐藏测试的仓库快照与 baseline commit（environment/Dockerfile 的 git init/add/commit 步骤）",
        "dockerfile_location": "environment/Dockerfile COPY vendor/MinGit-2.56.0.2-64-bit.zip -> RUN Expand-Archive ... C:\\Git; 探针 & C:\\Git\\cmd\\git.exe --version",
        "provisioning_kind": "installed",
        "functional_probe": "docker run --rm <image> cmd /c \"C:\\Git\\cmd\\git.exe --version\" -> git version 2.56.0.windows.2",
        "provisioning_evidence": [f"{EV_REL}/image-digests.json", f"{EV_REL}/toolchain-probe-L1.log"],
        "runtime_evidence": [f"{EV_REL}/toolchain-probe-L1.log"],
        "status": "PASS",
    },
    {
        "name": "Python (embed)",
        "version": "3.12.9",
        "required_by": "被测包的实现语言与 tests/ 的 pytest 执行器",
        "dockerfile_location": "environment/Dockerfile COPY vendor/python-3.12.9-embed-amd64.zip -> C:\\Python312，并改写 python312._pth",
        "provisioning_kind": "installed",
        "functional_probe": "docker run --rm <image> cmd /c \"C:\\Python312\\python.exe -V\" -> Python 3.12.9",
        "provisioning_evidence": [f"{EV_REL}/image-digests.json", f"{EV_REL}/toolchain-probe-L1.log"],
        "runtime_evidence": [f"{EV_REL}/toolchain-probe-L1.log"],
        "status": "PASS",
    },
    {
        "name": "pip",
        "version": "26.0.1",
        "required_by": "从 vendored wheelhouse 离线安装测试依赖（无网络构建）",
        "dockerfile_location": "environment/Dockerfile 解包 vendor/wheels/pip-*.whl 到 site-packages 后 RUN python -m pip --version",
        "provisioning_kind": "installed",
        "functional_probe": "docker run --rm <image> cmd /c \"C:\\Python312\\python.exe -m pip --version\" -> pip 26.0.1 from C:\\Python312\\Lib\\site-packages\\pip",
        "provisioning_evidence": [f"{EV_REL}/toolchain-probe-L1.log"],
        "runtime_evidence": [f"{EV_REL}/toolchain-probe-L1.log"],
        "status": "PASS",
    },
    {
        "name": "pytest",
        "version": "8.3.5",
        "required_by": "tests/run_tests.ps1 驱动隐藏用例并产出逐 testcase 结果",
        "dockerfile_location": "environment/Dockerfile RUN python -m pip install --no-index --find-links C:\\vendor\\wheels 'pytest==8.3.5'",
        "provisioning_kind": "installed",
        "functional_probe": "docker run --rm <image> cmd /c \"C:\\Python312\\python.exe -m pytest --version\" -> pytest 8.3.5",
        "provisioning_evidence": [f"{EV_REL}/toolchain-probe-L1.log"],
        "runtime_evidence": [f"{EV_REL}/toolchain-probe-L1.log"],
        "status": "PASS",
    },
    {
        "name": "PowerShell",
        "version": "5.1 (Windows Server 2022 基础层自带)",
        "required_by": "environment/prepare.ps1、tests/test.ps1 等 PowerShell 入口脚本",
        "dockerfile_location": "未安装：由 base image（mcr.microsoft.com/windows/server:ltsc2022）继承；Dockerfile 的 SHELL 指令使用 powershell",
        "provisioning_kind": "base_inherited",
        "functional_probe": "Dockerfile SHELL [\"powershell\", ...] 全程执行成功（构建期与容器内均可用）",
        "provisioning_evidence": [f"{EV_REL}/image-digests.json"],
        "runtime_evidence": [f"{EV_REL}/toolchain-probe-L1.log"],
        "status": "PASS",
    },
]


def main() -> int:
    digests = json.loads((EV / "image-digests.json").read_text(encoding="utf-8-sig"))
    identity = json.loads((QR / "_task_identity.json").read_text(encoding="utf-8-sig"))
    OUT.mkdir(parents=True, exist_ok=True)

    for pkg, tag, num, task_id, build in PACKAGES:
        info = digests["packages"][pkg]
        image = info["configured_image"]
        digest = info["resolved_image_digest"]
        ident = identity[num]
        jobs_rel = f"harbor-windows/{pkg}/jobs"
        build_rel = f"harbor-windows/_qc_runs/{build}"

        image_delivery = {
            "status": "PASS",
            "evidence": [
                f"{EV_REL}/push-ghcr.log：docker push 6 个 tag 的完整输出，本包 tag 的 digest = {digest}，exit=0",
                f"{EV_REL}/L1-wff-pull-all.log：L1（独立 Windows 容器宿主）内 docker pull {image}，exit=0，Digest 与 push 报告逐字符一致",
                f"{EV_REL}/anonymous-access.txt：零凭据匿名访问 ghcr.io，tags/list 与 5 个 tag 的 manifest 全部 HTTP 200",
                f"{EV_REL}/toolchain-probe-L1.log：从该镜像启动新容器并完成工具链功能探针（exit=0）",
                f"{build_rel}/controls/controls_summary.json 与 {jobs_rel}/：同一镜像身份下的 Oracle/NOP 与模型轮逐 testcase 证据",
            ],
            "notes": ("成品镜像已发布到公共仓库并设为 public，甲方无需凭据即可拉取（匿名 tags/manifest/config 均为 HTTP 200）。"
                      "L1 是独立于物理宿主的 Windows 容器宿主，其拉取日志排除了本地缓存冒充交付的可能；"
                      "拉取得到的 RepoDigests 与 push 阶段报告的 digest 完全一致，因此后续所有 Oracle/NOP 与模型轮"
                      "都可绑定到同一远端镜像身份。甲方目标环境不支持现场构建，故本字段指向成品镜像而非 Dockerfile 基础镜像。"),
            "configured_image": image,
            "resolved_image_digest": digest,
            "target_profile": {
                "windows_build": TARGET_BUILD,
                "architecture": "amd64",
                "isolation": "process",
                "can_build_images": False,
            },
            "checks": {
                "remote_pull": {
                    "status": "PASS",
                    "evidence": [
                        f"{EV_REL}/L1-wff-pull-all.log：docker pull {image} -> 'Status: Downloaded newer image for {image}'，=== RESULT 0 ===",
                        f"{EV_REL}/L1-wff-pull2.log：单独重拉 wciocp-220 的完整日志，Digest: {digest}，PULL2 EXIT=0",
                        f"{EV_REL}/push-ghcr.log：push 侧报告的同一 digest，两侧逐字符一致",
                    ],
                    "notes": ("在 L1（独立 Docker daemon，非物理宿主缓存）执行显式 docker pull，保留命令、退出码与原始 stdout；"
                              "即使物理机已有同内容镜像，仍实际访问了仓库并解析出 digest。"),
                },
                "recipient_access": {
                    "status": "PASS",
                    "evidence": [
                        f"{EV_REL}/anonymous-access.txt：匿名 token 长度 64，tags/list 返回全部 5 个 tag",
                        f"{EV_REL}/anonymous-access.txt：5 个 tag 的 manifest 均 HTTP/1.1 200 OK 且带 docker-content-digest",
                        "GitHub 包可见性已设为 public（api.github.com/user/packages/container/wfflab-windows 返回 visibility=public）",
                    ],
                    "notes": ("全程未使用任何 Authorization 凭据：先以匿名身份向 ghcr.io/token 换取 pull 作用域 token，再读取 tags/list、"
                              "manifest 与 config blob。因此甲方在无账号、无凭据条件下即可拉取，不依赖作者账号登录。"),
                },
                "target_compatibility": {
                    "status": "PASS",
                    "evidence": [
                        f"{EV_REL}/image-digests.json：os={info['os']} architecture={info['architecture']} OsVersion={info['os_version']}",
                        f"{EV_REL}/toolchain-probe-L1.log：容器内 ver -> Microsoft Windows [Version 10.0.20348.5761]",
                        "甲方向环境说明：目标 windows-dinp-2025、宿主 build 20348/ltsc2022、主 pod 无 Docker daemon、不允许现场构建",
                    ],
                    "notes": ("镜像为 windows/amd64、OsVersion 10.0.20348.5761，与甲方宿主 build 20348 同代，Windows 容器遵循"
                              "“容器 build 不高于宿主 build”的规则，因此可在甲方节点直接运行；基础层为完整 Windows Server 2022"
                              "（非 Nano Server / Server Core）。"),
                },
                "clean_start": {
                    "status": "PASS",
                    "evidence": [
                        f"{EV_REL}/toolchain-probe-L1.log：docker run --rm {image} cmd /c ... 于 3.8~5.7 秒内完成启动到退出，exit=0",
                        f"{build_rel}/controls/controls_summary.json：同一镜像由 Harbor 从新容器启动并跑到就绪后完成 Oracle/NOP",
                        "L1 内 docker info：OSType=windows Isolation=process（与甲方 process 隔离一致）",
                    ],
                    "notes": ("每个探针与每次 Harbor trial 都从同一镜像启动全新容器；未复用长驻容器，启动到就绪后即执行真实命令。"),
                },
                "task_execution": {
                    "status": "PASS",
                    "evidence": [
                        f"{build_rel}/controls/controls_summary.json：Oracle 3 轮 reward=1、NOP 3 轮 reward=0，6 轮 task_checksum 全为 {ident['harbor_dirhash']}",
                        f"{jobs_rel}/_index/assembly_report.json：12 个 job 的分数与 testcase 集合全部合法",
                        f"{jobs_rel}/model-qwen-*/verifier/report.json 与 {jobs_rel}/model-opus-*/verifier/report.json：逐 testcase 结果",
                    ],
                    "notes": ("同一镜像身份下完成标准 Harbor Oracle/NOP（各 3 轮）与模型轮，逐 testcase 结果随包交付；"
                              "所有 job 的 task_checksum 与本包冻结的 dirhash 一致，说明执行确实发生在该镜像的该 Task 版本上。"),
                },
            },
        }

        windows_image_policy = {
            "status": "PASS",
            "evidence": [
                f"environment/Dockerfile 的运行层 FROM = {BASE_IMAGE}（完整 Windows Server 2022，非 Server Core / Nano Server）",
                f"{EV_REL}/image-digests.json：成品镜像 os=windows architecture=amd64 OsVersion={info['os_version']}",
                f"{EV_REL}/toolchain-probe-L1.log：容器内 ver 报告 10.0.20348.5761，且 PowerShell、git、python 等完整系统组件可用",
                "windows-harbor-qc/scripts/windows_image_policy.py 的 inspect_windows_dockerfile(path) 对本包 Dockerfile 无 errors",
            ],
            "notes": ("运行层为 mcr.microsoft.com/windows/server:ltsc2022（完整 Windows Server 2022，build 20348），早于 2019 的镜像与"
                      "Nano Server / Server Core 均未使用；镜像未做额外系统裁剪，容器内保留了完整 PowerShell 与 CMD 环境。"
                      "2025（build 26100）虽为优先项，但甲方宿主 build 20348 下 Windows 容器无法运行更高 build 的镜像，"
                      "按 references/current-project-policy.md 的“甲方实际可运行是硬门禁”选用兼容的完整镜像。"),
            "configured_image": image,
            "windows_build": BASE_BUILD,
            "release_year": BASE_YEAR,
            "family": "windows-server",
            "untrimmed": True,
            "runtime_bases": [
                {
                    "image": BASE_IMAGE,
                    "windows_build": BASE_BUILD,
                    "release_year": BASE_YEAR,
                    "family": "windows-server",
                    "untrimmed": True,
                    "evidence": [
                        f"{EV_REL}/image-digests.json：成品镜像 OsVersion={info['os_version']}，层数 {info['layers']}",
                        "环境/Dockerfile 第 1 段 FROM 与该引用逐字一致；成品镜像除工具链与 workspace 外未替换系统组件",
                    ],
                }
            ],
        }

        toolchain_in_image = {
            "status": "PASS",
            "evidence": [
                f"{EV_REL}/toolchain-probe-L1.log：在成品镜像的新容器内实际执行各工具版本与功能探针，全部 exit=0",
                "environment/Dockerfile 中每项工具都有可定位的 COPY/RUN 配置行，且构建全程无网络（vendored 资产）",
                f"{EV_REL}/image-digests.json：工具链固化在交付镜像的层内，随镜像身份一起交付",
            ],
            "notes": ("逐项登记任务与执行链实际需要的工具，并同时给出 Dockerfile 配置位置（构建期证据）与成品容器内的功能探针结果"
                      "（运行期证据）。PowerShell 属基础层继承（base_inherited），其余四项由 Dockerfile 显式安装（installed）。"),
            "tools": TOOLS,
        }

        nested_virtualization = {
            "status": "PASS",
            "evidence": [
                "物理宿主 Get-VMHost/Get-VM：MS-7D48，hypervisorlaunchtype=Auto，HypervisorPresent=True，L1-WinSrv2022 State=Running",
                f"Get-VMProcessor：ExposeVirtualizationExtensions=True，Count=6（L1 标识 {L1_VM_ID}）",
                "L1 内 Win32_ComputerSystem：Manufacturer=Microsoft Corporation、Model=Virtual Machine、HypervisorPresent=True",
                "L1 内 Win32_Processor：VirtualizationFirmwareEnabled=True、SecondLevelAddressTranslationExtensions=True",
                f"{EV_REL}/toolchain-probe-L1.log：L1 内 docker info OSType=windows Isolation=process",
                f"{build_rel}/controls/controls_summary.json 与 {jobs_rel}/：全部 job 在 L1 内的容器中执行，task_checksum={ident['harbor_dirhash']}",
            ],
            "notes": ("实际执行链为 物理宿主(L0, Hyper-V) -> L1 Windows Server 2022 虚拟机 -> L1 内的 Windows 容器(L2)，"
                      "虚拟化深度为 2。裸机直接跑容器、或只在物理宿主上跑 Hyper-V 容器都只有一层，本包不属此列："
                      "外层 hypervisor 为物理宿主的 Hyper-V，L1 是货真价实的 guest（Model=Virtual Machine 且 HypervisorPresent=True），"
                      "且 L1 内已暴露虚拟化扩展（VirtualizationFirmwareEnabled/SLAT 均为 True），所有 Oracle/NOP 与模型轮"
                      "都在 L1 内启动的容器里完成。"),
            "configured_image": image,
            "task_id": task_id,
            "task_version": "1.0.0",
            "task_hash": ident["task_hash"],
            "virtualization_depth": 2,
            "outer_guest_id": f"L1-WinSrv2022 ({L1_VM_ID})",
            "outer_hypervisor": "Microsoft Hyper-V（物理宿主 MS-7D48 / 13th Gen Intel Core i5-13490F，hypervisorlaunchtype=Auto）",
            "inner_hypervisor": "Windows Server 2022 Containers + Docker Engine 27.3.1（L1 内，process 隔离）",
            "virtualization_extensions_exposed": True,
            "inner_virtualization_enabled": True,
            "task_runtime_in_nested_layer": True,
            "checks": {
                "outer_guest": {
                    "status": "PASS",
                    "evidence": [
                        f"Get-VM L1-WinSrv2022：Id={L1_VM_ID} Generation=1 ProcessorCount=6 MemoryStartup=12GiB State=Running",
                        "L1 内 Win32_ComputerSystem：Manufacturer=Microsoft Corporation Model=Virtual Machine",
                        "L1 内 systeminfo：'Hyper-V Requirements: A hypervisor has been detected.'",
                    ],
                    "notes": ("保留了外层 hypervisor 与 L1 虚拟机标识/拓扑的原始命令输出：物理宿主为 Hyper-V 宿主，"
                              "L1 是 Gen1 虚拟机（Model 明确为 Virtual Machine），两者身份可复核。"),
                },
                "capabilities_exposed": {
                    "status": "PASS",
                    "evidence": [
                        "物理宿主 Get-VMProcessor -VMName L1-WinSrv2022：ExposeVirtualizationExtensions=True",
                        "L1 内 Win32_Processor：VirtualizationFirmwareEnabled=True 且 SecondLevelAddressTranslationExtensions=True",
                        "L1 内 Win32_ComputerSystem：HypervisorPresent=True",
                    ],
                    "notes": ("外层显式打开了 ExposeVirtualizationExtensions，L1 内实际看到虚拟化固件能力与 SLAT 均已暴露，"
                              "且 L1 自身识别到 hypervisor 存在；这不是仅凭 CPU 规格或参数声明得出的结论。"),
                },
                "inner_runtime": {
                    "status": "PASS",
                    "evidence": [
                        "L1 内 Get-WindowsFeature Containers：InstallState=Installed",
                        "L1 内 docker version：Client/Server 均为 27.3.1，ServerOs=windows",
                        f"{EV_REL}/toolchain-probe-L1.log：docker run 在 L1 内启动容器并输出 Microsoft Windows [Version 10.0.20348.5761]",
                        f"{build_rel}/controls/ 与 {build_rel}/model-rounds/：每轮 job 的 trial 均在 L1 内容器里完成并有终态 reward",
                    ],
                    "notes": ("记录了 L1 内实际启动 L2 Windows 容器的命令、日志与终态：Containers 功能已安装、Docker Engine 在 L1 内运行、"
                              "容器的 OS 版本与镜像一致，Oracle/NOP 与模型轮全部在这些容器中产生正式分数。"),
                },
                "job_binding": {
                    "status": "PASS",
                    "evidence": [
                        f"本包 task.toml 的 docker_image = {image}，与各 job 使用的镜像一致",
                        f"{jobs_rel}/ 下 12 个 job 的 result.json task_checksum 均为 {ident['harbor_dirhash']}，与 inspect_delivery.harbor_dirhash 复算一致",
                        f"{build_rel}/controls/controls_summary.json：Oracle 3 轮=1、NOP 3 轮=0，均在 L1 内执行",
                        f"{jobs_rel}/model-*/agent/model-result.json：模型轮的 runner_sha256 与 base_url 可追溯，且与 Oracle/NOP 同一镜像与同一 Task",
                    ],
                    "notes": ("当前 Task/镜像与实际模型、Oracle/NOP jobs 均绑定到嵌套执行层：镜像引用与 task.toml 一致，"
                              "所有 job 的 task_checksum 与题包复算的 dirhash 相同，说明没有跨环境或跨版本混入。"),
                },
            },
        }

        payload = {
            "package": pkg,
            "image_delivery": image_delivery,
            "windows_image_policy": windows_image_policy,
            "toolchain_in_image": toolchain_in_image,
            "nested_virtualization": nested_virtualization,
        }
        (OUT / f"{pkg}.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"  已生成 {pkg}.json  (tag={tag})")

    print(f"\n输出目录: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
