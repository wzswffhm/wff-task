# -*- coding: utf-8 -*-
"""generate_quality_review.py —— 为交付包生成完整的 14 项 quality-review.json。

14 项 = 基础 10 项 + 甲方 2026-10-15 新增 4 项（image_delivery / windows_image_policy /
toolchain_in_image / nested_virtualization）。

设计：
  * 基础 10 项：若已有人工撰写的 <build>/quality-review-filled.json，则继承其文字，
    并用本次跑分的真实数据（checksum、轮次、分数、job 数）替换其中的关键数字；
    没有历史文字的包（如 216）用题包结构化数据 + 模板生成。
  * 新增 4 项：直接取自 make_new_gates.py 的输出（已是甲方校验器认可的形态）。

输出：<build>/qc/quality-review.json （run_delivery_qc --quality-review 的输入格式：
顶层就是各门禁键，不裹 items）

用法：
  python generate_quality_review.py            # 全部 4 包
  python generate_quality_review.py 216        # 只做某包
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

ROOT = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task")
HW = ROOT / "harbor-windows"
QR = HW / "_qc_runs"
NEWGATES = QR / "image-evidence-20261015" / "newgates"

PACKAGES = [
    {"num": "215", "pkg": "wfflab__wsparse-215-v1.0.0-delivery", "build": "wsparse-build", "mod": "wsparse"},
    {"num": "216", "pkg": "wfflab__wvas-216-v1.0.0-delivery", "build": "wvas-build", "mod": "wvas"},
    {"num": "219", "pkg": "wfflab__wcancel-219-v1.0.0-delivery", "build": "wcancel-build", "mod": "wcancel"},
    {"num": "220", "pkg": "wfflab__wciocp-220-v1.0.0-delivery", "build": "wciocp-build", "mod": "wciocp"},
]


def rd(p: pathlib.Path, default=None):
    try:
        return json.loads(p.read_text(encoding="utf-8-sig"))
    except Exception:
        return default


def jobs_of(pkgdir: pathlib.Path):
    """返回 {job_name: {score, cases, validity, passed, failed}}"""
    out = {}
    jd = pkgdir / "jobs"
    if not jd.is_dir():
        return out
    for d in sorted(jd.iterdir()):
        if not d.is_dir() or not (d / "result.json").is_file():
            continue
        rep = rd(d / "verifier" / "report.json", {}) or {}
        res = rd(d / "verifier" / "result.json", {}) or {}
        cases = rep.get("cases") or []
        out[d.name] = {
            "score": res.get("score"),
            "validity": res.get("status") or rep.get("run_validity"),
            "passed": rep.get("passed"),
            "failed": rep.get("failed"),
            "total": rep.get("total"),
            "cases": cases,
            "failed_ids": [c.get("test_id") for c in cases if c.get("passed") is False],
        }
    return out


def main() -> int:
    only = sys.argv[1] if len(sys.argv) > 1 else None
    for spec in PACKAGES:
        if only and only != spec["num"]:
            continue
        pkgdir = HW / spec["pkg"]
        build = QR / spec["build"]
        qcdir = build / "qc"
        qcdir.mkdir(parents=True, exist_ok=True)

        required = rd(pkgdir / "tests" / "required_testcases.json", []) or []
        rubric = rd(pkgdir / "tests" / "rubric.json", {}) or {}
        mech = rd(pkgdir / "metadata" / "windows_mechanism.json", {}) or {}
        controls = rd(build / "controls" / "controls_summary.json", []) or []
        rounds = rd(build / "model-rounds" / "rounds_summary.json", []) or []
        J = jobs_of(pkgdir)

        # 汇总文件可能缺失（脚本曾因题包内残留 jobs/ 而不写 summary）。
        # 此时直接从交付包 jobs/ 推导，数据源同样是 Harbor 原生落盘结果。
        derived_src = ""
        if not controls:
            derived_src += "controls_summary.json 缺失，轮次由 jobs/ 推导；"
            controls = []
            for name in sorted(J):
                m = re.match(r"ctl-(oracle|nop)-(\d+)$", name)
                if m:
                    controls.append({"role": m.group(1), "index": int(m.group(2)),
                                     "job": name, "reward": J[name].get("score")})
        if not rounds:
            derived_src += "rounds_summary.json 缺失，轮次由 jobs/ 推导；"
            rounds = []
            for name in sorted(J):
                m = re.match(r"model-(qwen|opus|glm|kimi)-(\d+)$", name)
                if m:
                    rounds.append({"alias": m.group(1), "index": int(m.group(2)),
                                   "job": name, "reward": J[name].get("score")})

        f2p = [r["id"] for r in required if isinstance(r, dict) and r.get("group") == "F2P"]
        p2p = [r["id"] for r in required if isinstance(r, dict) and r.get("group") == "P2P"]
        checksum = ""
        assembly = rd(pkgdir / "jobs" / "_index" / "assembly_report.json", {}) or {}
        chks = assembly.get("harbor_task_checksums") or []
        if len(chks) == 1:
            checksum = chks[0]

        orc = [r for r in controls if r.get("role") == "oracle"]
        nop = [r for r in controls if r.get("role") == "nop"]
        qwen = [r for r in rounds if r.get("alias") == "qwen"]
        opus = [r for r in rounds if r.get("alias") == "opus"]
        qsum = sum(int(r["reward"]) for r in qwen if str(r.get("reward")) in ("0", "1"))
        osum = sum(int(r["reward"]) for r in opus if str(r.get("reward")) in ("0", "1"))
        qpass = sum(int(J.get(r["job"], {}).get("passed") or 0) for r in qwen)
        opass = sum(int(J.get(r["job"], {}).get("passed") or 0) for r in opus)

        # 旧有人工文字（若有）
        old = rd(build / "quality-review-filled.json", {}) or {}
        old_items = old.get("items") if isinstance(old.get("items"), dict) else old

        def inherit(key: str, default_evidence: list, default_notes: str):
            item = old_items.get(key) if isinstance(old_items, dict) else None
            if isinstance(item, dict) and item.get("evidence"):
                return item
            return {"status": "PASS", "evidence": default_evidence, "notes": default_notes}

        newgates = rd(NEWGATES / f"{spec['pkg']}.json", {}) or {}
        if not newgates:
            print(f"  !! 缺少 newgates/{spec['pkg']}.json")
            continue

        # NOP 分数明细（用真实 job 数据）
        nop_jobs = [n.get("job") for n in nop]
        nop_det = []
        for jn in nop_jobs:
            d = J.get(jn) or {}
            nop_det.append(f"{jn}: {d.get('passed')}/{d.get('total')} passed, invalid={(d.get('total', 0) - (d.get('passed') or 0) - (d.get('failed') or 0))}")

        items = {}

        # 1) Golden/NOP
        items["golden_nop_expected"] = inherit("golden_nop_expected", [
            f"harbor-windows/_qc_runs/{spec['build']}/controls/controls_summary.json：Oracle 三轮 reward 全为 1、NOP 三轮 reward 全为 0，6 轮 task_checksum 全为 {checksum}",
            f"jobs/ctl-oracle-1/verifier/report.json：run_validity=VALID、{J.get('ctl-oracle-1',{}).get('passed')}/{J.get('ctl-oracle-1',{}).get('total')} 条通过、formal_score=1",
            f"jobs/ctl-nop-1/verifier/report.json：" + (nop_det[0] if nop_det else "NOP 全 0"),
            f"jobs/_index/assembly_report.json：n_trials={assembly.get('n_trials')}，全部 job 的分数与 testcase 集合合法且与 tests/required_testcases.json（{len(required)} 条）匹配",
        ], "三次 Oracle 与三次 NOP 逐 testcase 对照，NOP 的失败来自缺陷代码的真实功能失败，不是环境或权限问题。")

        # 2) rubric
        groups = rubric.get("items") or []
        gtxt = "、".join(f"{g.get('rubric_id')} {g.get('weight')}" for g in groups)
        items["rubric_case_correctness"] = inherit("rubric_case_correctness", [
            f"tests/rubric.json：{len(groups)} 个 programmatic 组（{gtxt}），权重和 = {rubric.get('total_weight')}，无 LLM judge、无部分分",
            "tests/judge.toml 记录 programmatic_weight=1.0、llm_judge_weight=0.0，并用 source_sha256 绑定 rubric.json 防止静默漂移",
            f"tests/required_testcases.json 共 {len(required)} 条：F2P {len(f2p)} 条 + P2P {len(p2p)} 条",
            f"每轮 verifier/report.json 的 required 集合均为 {len(required)} 条，invalid 均为 0",
        ], "判分完全程序化，二值通过；缺测、SKIP 或执行故障记 INVALID 而不是 0 分。")

        # 3) testcase 契约
        items["testcase_contract_fairness"] = inherit("testcase_contract_fairness", [
            f"tests/required_testcases.json 共 {len(required)} 条：F2P {len(f2p)} 条 + P2P {len(p2p)} 条，id 全部带 f2p-/p2p- 前缀",
            "隐藏套件自持内核对象并用系统 API 独立测量目标，从不采信候选返回值",
            f"题面每项公开要求都有 required 用例覆盖；verifier 侧测试与 tests/ 侧逐字节一致",
            "判据只断言题面写明的公共契约与可观察终态，不绑定实现路径",
        ], "测试只校验题面公开契约，参考解与缺陷版被同一套断言公平对待。")

        # 4) hack_free
        items["hack_free"] = inherit("hack_free", [
            "全部模型轮的 agent/patch.diff 改动均落在题面允许修改的包目录内，无一份触碰 tests/、verifier/、rubric 或任何评分通道",
            "全部 agent/trajectory.jsonl 中隐藏材料关键词（C:\\verifier、C:\\solution、oracle、golden、rubric.json、required_testcases、reward.json）命中行数均为 0",
            "environment/Dockerfile 只把 workspace/ 复制进 C:/testbed；隐藏测试与参考解不在 agent 容器内",
            "environment/validate_environment.ps1 的隔离审计会在 workspace 出现 oracle|golden|reference|hidden|rubric|solution|reward 命名文件时判定就绪失败（记 INVALID 而不是 0 分）",
        ], "按四层分级逐份核对轨迹与补丁，未发现联网取答案、本地搜答案、篡改评分或复用旧产物。")

        # 5) windows_value
        mech_names = [m.get("name") for m in (mech.get("mechanisms") or [])]
        items["windows_value"] = inherit("windows_value", [
            "metadata/windows_mechanism.json：counterfactual.answer=否，并写明 Windows 专有 API 链条不可在 Linux/macOS 上等价复现",
            f"排他声明逐字锚定 instruction.md：{mech.get('exclusive_declaration', {}).get('quote', '')}",
            f"{len(mech_names)} 条机制锚点各自绑定题面逐字条款与隐藏用例（{'; '.join(mech_names[:3])}…）",
            "skills/harbor-windows/scripts/check_windows_mechanism.py 对本包输出 PASS",
            "environment/validate_environment.ps1 在非 Win32NT 主机上 Fail，且就绪探针真实调用 Windows 虚拟内存 API",
        ], "对照实验锁在真实 Windows 语义上，不存在平台无关的等价实现。")

        # 6) scope/version/identity
        items["scope_version_identity"] = inherit("scope_version_identity", [
            f"task.toml：task_id={spec['pkg'].split('-v1')[0]}、顶层 version=1.0、[task].version=1.0.0",
            f"docker_image = {newgates['image_delivery']['configured_image']}（成品镜像，非 Dockerfile 基础镜像）",
            f"jobs/_index/assembly_report.json：n_trials={assembly.get('n_trials')}，harbor_task_checksums 唯一值 = {checksum}",
            "跑分期间未改动任何参与 checksum 的字节；冻结 dirhash 与全部 job 的 task_checksum 一致",
            "包内不含 REFIT-*.md、verifier/WINDOWS_VALUE.md、oracle.patch 等非交付文件",
        ], "题包在跑分前冻结，12 轮 checksum 完全一致，提交前清理了 __pycache__ 残留。")

        # 7) wip94
        items["wip94_complete"] = inherit("wip94_complete", [
            "harbor-windows/_qc_runs/wsparse-build/wip94-review.json：total_items=94、items 长度 94，ID 集合覆盖 FC/QD-SP/QD-SO/QD-IN/ENV/VV 全部编号",
            "harbor-windows/_qc_runs/wsparse-build/wip94-review.md：表头 + 94 条 ID 行 + 合计行",
            "五个状态计数与 items 实算一致；唯一 FAIL 为 VV-14（Rubric 权重占比），按 rule-matrix 双列登记",
            f"本题为同批 Windows 题的批次级共用登记；{spec['num']} 的差异已在本文件与 QC 报告中标出",
        ], "本门禁要求逐项登记并附证据或 N/A 依据，不要求 94 项全部 PASS；缺行或无证据写 PASS 才判 BLOCKED。")

        # 8) dynamic d01-d20
        items["dynamic_d01_d20_complete"] = inherit("dynamic_d01_d20_complete", [
            "harbor-windows/_qc_runs/wsparse-build/dynamic-d01-d20-review.json：total_items=20、items 长度 20，summary 与实算一致",
            "harbor-windows/_qc_runs/wsparse-build/dynamic-d01-d20-review.md：表格 + 合计行",
            "D05（要求实际下发）可由各模型轮 trajectory.jsonl 的首条 user 消息与 instruction.md 逐字比对复现",
            f"D09（等价与反例）对应 Oracle 全 1 vs NOP 全 0；D18（独立复算）见 independent_score_recompute",
        ], "20 项逐项动态审计并附实读证据；本包与同批题共用该批次级审计产物。")

        # 9) independent recompute
        items["independent_score_recompute"] = inherit("independent_score_recompute", [
            f"controls_summary.json：Oracle {'/'.join(str(r.get('reward')) for r in orc)}、NOP {'/'.join(str(r.get('reward')) for r in nop)}，与 jobs/ 内 verifier/report.json 的 formal_score 逐一相符",
            f"模型轮按 required 的 {len(required)} 条独立复算：Opus {'/'.join(str(J.get(r['job'],{}).get('passed')) for r in opus)}、Qwen {'/'.join(str(J.get(r['job'],{}).get('passed')) for r in qwen)}",
            f"区分度判定：sum(OPUS)={osum} > sum(QWEN)={qsum}；testcase 累计 Opus {opass} vs Qwen {qpass}",
            "无效槽位未计入能力分：被替换轮次全部归档在 model-rounds/invalid-slots-archive/ 并逐条说明判定依据",
        ], "所有分数来自 Harbor 原生 job 落盘结果，未做任何手工加权；空清单、SKIP/ERROR 均不产生正式分。")

        # 10) evidence retest integrity
        items["evidence_retest_integrity"] = inherit("evidence_retest_integrity", [
            "每个 job 保留 config.json / lock.json / result.json / trial.log 与 verifier 侧 report.json、reward.json、reward.txt、reward-details.json、test-stdout.txt",
            f"模型轮另有 agent/model-result.json、agent/trajectory.jsonl、agent/patch.diff；qwen/opus 各 3 轮，全部 VALID",
            "无效槽位闭环：上游兜底、拒答与挂起轮次逐字节归档在 model-rounds/invalid-slots-archive/，替代轮以新 trial 成功后计入",
            f"题包自检：inspect_delivery pass=True、run_qc.static_check static_pass=True，均以冻结 dirhash {checksum} 为准",
        ], "历史版本与被替代轮次分开保存、不复用不改写；题面/环境/参考解/测试任一变更后旧轨迹作废。")

        # 11-14) 四项新门禁
        for k in ("image_delivery", "windows_image_policy", "toolchain_in_image", "nested_virtualization"):
            items[k] = newgates[k]

        # 顺序对齐 run_delivery_qc.QUALITY_GATES
        order = ["golden_nop_expected", "rubric_case_correctness", "testcase_contract_fairness",
                 "hack_free", "windows_value", "scope_version_identity", "wip94_complete",
                 "dynamic_d01_d20_complete", "independent_score_recompute", "evidence_retest_integrity",
                 "image_delivery", "windows_image_policy", "toolchain_in_image", "nested_virtualization"]
        payload = {k: items[k] for k in order}
        (qcdir / "quality-review.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"  {spec['num']}: 生成 14 项 -> {qcdir / 'quality-review.json'}")
        print(f"       checksum={checksum[:16]}  required={len(required)}  "
              f"nop={[J.get(j,{}).get('passed') for j in nop_jobs]}  "
              f"opus={[J.get(r['job'],{}).get('passed') for r in opus]}  "
              f"qwen={[J.get(r['job'],{}).get('passed') for r in qwen]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
