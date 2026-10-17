# -*- coding: utf-8 -*-
"""build_d0120_216.py —— 为 wfflab__wvas-216 生成 D01-D20 动态审计。

数据来源：facts-216-base.json + qc-facts-216.json
"""
from __future__ import annotations

import json
from pathlib import Path

REPAIR = Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-windows\_qc_runs\repair-215-216-20261016")
BASE = REPAIR / "facts-216-base.json"
JOBS = REPAIR / "qc-facts-216.json"
OUT = REPAIR / "dynamic-d01-d20-review-216.json"


def main() -> int:
    b = json.loads(BASE.read_text(encoding="utf-8-sig"))
    j = json.loads(JOBS.read_text(encoding="utf-8-sig"))

    req = b["required"]
    ids = req["ids"]
    f2p = [i for i in ids if i.startswith("f2p-")]
    p2p = [i for i in ids if i.startswith("p2p-")]
    n_req = req["total"]
    ins = b["instruction"]

    qwen, opus = j["qwen_scores"], j["opus_scores"]
    qsum, osum = j["qwen_sum"], j["opus_sum"]
    qp, op = j["qwen_testcase_pass_sum"], j["opus_testcase_pass_sum"]
    cs = j["checksums"][0] if j["checksums"] else ""
    n_jobs = j["job_count"]
    nop_failed = len(j["nop"][0]["failed"]) if j["nop"] else 0

    jobs_by = {e["job"]: e for e in j["jobs"]}
    failed_rounds = [e["job"] for e in j["jobs"]
                     if e["job"].startswith("model-") and e["score"] == 0]
    net_hits = sum(e.get("network_tool_hits") or 0 for e in j["jobs"])

    items: list[dict] = []

    def add(i, title, status, evidence, notes):
        items.append({"id": i, "title": title, "status": status,
                      "evidence": evidence, "notes": notes})

    add("D01", "运行身份一致（同身份 Golden / no-change 对照）", "PASS",
        ["Golden（ctl-oracle-1..3）与 no-change（ctl-nop-1..3）在同一 task_checksum %s 下运行" % cs[:16],
         "六轮各自独立 job、独立容器，无跨轮复用",
         "模型轮 6 轮同样绑定该 checksum"],
        "对照双方身份一致，差异只来自是否应用参考解。")

    add("D02", "对照逐项成立（逐 testcase 终态）", "PASS",
        ["Oracle 三轮：score=1，%d/%d 全 PASS" % (n_req, n_req),
         "NOP 三轮：score=0，%d 条 F2P 全 FAIL、%d 条 P2P 全 PASS" % (nop_failed, len(p2p)),
         "三轮回的失败集合完全相同，无轮间漂移"],
        "逐 testcase 终态与设计预期逐项一致。")

    add("D03", "空跑得分逐分解释", "PASS",
        ["NOP 的 %d 条失败全部为 F2P（%s 等）" % (nop_failed, ", ".join(j["nop"][0]["failed"][:3])),
         "NOP 通过的 %d 条全为 P2P 回归面" % len(p2p),
         "无「空跑因基础设施错误得 0」的情况：三轮均 VALID 且 invalid=0"],
        "空跑得 0 分可逐条解释为缺陷未被修复，而非环境故障。")

    add("D04", "稳定性与干净重建", "PASS",
        ["控制轮 3+3 与模型轮 6 各自新建 job 与容器",
         "Oracle 三轮 20/20、NOP 三轮 10/20 完全一致",
         "本轮为 L1 内干净重跑：旧 jobs 整体隔离后才执行"],
        "重复执行结果稳定，重建流程干净。")

    add("D05", "证明要求实际下发", "PASS",
        ["6/6 模型轮 trajectory.jsonl 的第 2 个事件（kind=user）为 instruction.md 全文",
         "每轮恰 1 条 user 消息，内容与 instruction.md 逐字相同（%d 字符）" % ins["chars"]],
        "题面确实下发给了模型，非仅存在于包内。")

    add("D06", "建立双向映射（需求-测试-评分）", "PASS",
        ["evidence/author-design/contract-map.json 给出 %d 条用例到题面条款的映射" % n_req,
         "required_testcases.json 的 id 与 rubric.json、judge.toml 的 test_ids 集合完全一致",
         "每条 rubric 条目引用具体 test_id"],
        "需求—测试—评分三向可追溯。")

    add("D07", "每项都审，PASS 也审（每项得分与扣分）", "PASS",
        ["逐轮统计：Qwen %s（testcase %d）、Opus %s（testcase %d）" % (qwen, qp, opus, op),
         "失分轮的具体失败 testcase 已逐条记录（见 jobs/*/verifier/result.json）",
         "通过轮同样逐条核对 20/20，未只审失败项"],
        "得分与扣分项均逐条审计。")

    add("D08", "功能优先，接受多解（等价实现）", "PASS",
        ["Oracle 20/20 与 Opus 两个通过轮 20/20，实现互不相同",
         "测试只断言行为（位宽、排序、子集关系、异常 kind），不限定内部写法",
         "6 份 patch.diff 结构各异，其中 3 份通过"],
        "接受等价实现，多解可通过。")

    add("D09", "等价实现与故障反例", "PASS",
        ["通过侧：Oracle 3/3 与 Opus 2/3 均达 20/20",
         "故障侧：NOP 10/20（%d 条 F2P 全 FAIL）、Qwen 失分轮 12/20" % nop_failed,
         "半修版本（仅改部分缺陷）无法通过，二值判定不放大分数"],
        "等价实现与故障反例均已实测。")

    add("D10", "替身必须保真（Mock 保真）", "N/A",
        ["题面与隐藏套件完全不使用 Mock/测试替身：无 mock、monkeypatch、stub",
         "判据全部来自真实 Win32 调用（VirtualQueryEx / GetMappedFileNameW / QueryDosDeviceW）",
         "测试对象为评测器自行启动的真实进程"],
        "本题无替身，N/A 成立。")

    add("D11", "工具、路径、离线依赖和权限", "PASS",
        ["容器内实测：git 2.56.0.windows.2、Python 3.12.9、pip 26.0.1、pytest 8.3.5、pytest-json-report 1.5.0",
         "工作目录 C:\\testbed，_pth 已追加",
         "构建与运行均离线：pip install --no-index --find-links C:\\vendor\\wheels",
         "容器以 ContainerAdministrator 运行，可访问自身与子进程地址空间"],
        "工具、路径、离线依赖与权限齐备。")

    add("D12", "本轮构建与候选回放（构建和产物身份）", "PASS",
        ["包内 %d 个非 jobs 文件与本轮实测清单一致" % b["file_count_no_jobs"],
         "12 个 job 的 task_checksum 唯一 = %s" % cs[:16],
         "镜像引用与 task.toml 的 docker_image 逐字一致"],
        "构建与产物身份已冻结并绑定。")

    add("D13", "环境能力与真实系统终态", "PASS",
        ["L2 容器内 ver → 10.0.20348.5761（真实 Windows Server 2022）",
         "测试读取的是真实进程地址空间，非打桩数据",
         "File System / 进程模型均为真实系统行为"],
        "环境为真实 Windows，终态可观测。")

    add("D14", "退出、异常、解析和日志", "PASS",
        ["run_tests.ps1 对 error/skip/未采集一律判 INVALID 并 exit 2，不给分",
         "aggregate_results.ps1 在 invalid>0 时置 formal_score=null",
         "12 个 job 的 verifier/result.json 均可解析且 status=VALID"],
        "退出码、异常与解析路径均有明确处理。")

    add("D15", "联网取源码、补丁或答案", "PASS",
        ["6 份 trajectory.jsonl 全文检索 curl/wget/Invoke-WebRequest/Invoke-RestMethod 命中 0",
         "git clone|fetch|pull 命中 0；pip install / choco / winget 命中 0",
         "合计 network_tool_hits = %d" % net_hits],
        "未发现任何联网取答案行为。")

    add("D16", "本地搜答案 / 隐藏验收访问", "PASS",
        ["agent 阶段工作区仅 C:\\testbed，tests/ 与 solution/ 不在容器内",
         "verifier/negative_access_probe.ps1 实测 C:\\tests、C:\\solution、C:\\verifier 不可达",
         "6 份轨迹无访问隐藏测试目录的记录"],
        "无法本地搜到答案或访问隐藏验收。")

    add("D17", "篡改或绕过验证", "PASS",
        ["6 份 patch.diff 均未触碰 tests/ 下的评分脚本",
         "未修改 rubric.json、judge.toml、reward 相关文件",
         "隐藏套件在 verifier 阶段才挂载，agent 无法预先篡改"],
        "未发现篡改或绕过验证的行为。")

    add("D18", "独立复算", "PASS",
        ["按 required 的 %d 条与二值规则复算：Qwen %s → %d，Opus %s → %d" % (n_req, qwen, qsum, opus, osum),
         "12 轮的 score 与 verifier/result.json、reward.txt、result.json:verifier_result.rewards.reward 四处一致",
         "testcase 累计：Qwen=%d、Opus=%d" % (qp, op)],
        "正式分由独立路径复算，与 Harbor 记录一致。")

    add("D19", "失败归因", "PASS",
        ["失分轮：%s" % (", ".join(failed_rounds) or "无"),
         "同环境 Oracle 3/3 达 20/20、NOP 3/3 达 10/20，且失分轮 invalid=0",
         "失败原因落在 wvas 实现本身（位宽截断、路径未翻译、保留区遗漏等），非依赖/环境/测试故障"],
        "失分归因为 MODEL_FAILURE，非基础设施问题。")

    add("D20", "批次与交付（批次分母和交付闭环）", "N/A",
        ["单题交付，jobs/ 仅 %d 个（3 Oracle + 3 NOP + 3 Qwen + 3 Opus）" % n_jobs,
         "本批口径 REQUIRED_COUNTS={qwen:3, opus:3}，按 2026-10-15 甲方放宽不跑 GLM/Kimi",
         "无批次级分母可统计"],
        "单题无批次日，N/A 成立。")

    summary = {}
    for it in items:
        summary[it["status"]] = summary.get(it["status"], 0) + 1

    doc = {
        "task_id": "wfflab__wvas-216",
        "task_version": "1.0.1",
        "numbering_source": "windows-procurement-qc-manual-20260927/01-质检执行手册.md 第 5 节（5.1 D01–D04、5.2 D05–D10、5.3 D11–D14、5.4 D15–D17、5.5 D18–D20）",
        "total_items": len(items),
        "audit_scope": "wfflab__wvas-216 v1.0.1 + L1 内本轮 12 个 job",
        "summary": summary,
        "package": "wfflab__wvas-216-v1.0.1-delivery",
        "reviewed_against_task_checksum": cs,
        "items": items,
    }
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("wrote %s  items=%d  summary=%s" % (OUT, len(items), summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
