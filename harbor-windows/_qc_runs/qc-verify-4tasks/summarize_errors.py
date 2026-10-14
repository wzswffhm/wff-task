# -*- coding: utf-8 -*-
"""归类 validate_jobs 的错误类型分布，并统计每个 job 的缺失文件。"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(r"C:\Users\Administrator\Desktop\wff-task")
src = ROOT / "harbor-windows" / "_qc_runs" / "qc-verify-4tasks" / "validate-jobs-result.json"
data = json.loads(src.read_text(encoding="utf-8"))

for label, tasks in data.items():
    print("#" * 88)
    print("# 副本 %s" % label)
    print("#" * 88)
    for name, info in tasks.items():
        errs = info.get("errors") or []
        if not errs:
            print("\n%s : PASS（0 错误）" % name)
            continue
        pats = [
            (r"is missing (agent/trajectory\.jsonl)", "缺失 agent/trajectory.jsonl"),
            (r"is missing (verifier/verifier\.log)", "缺失 verifier/verifier.log"),
            (r"is missing (agent/model-result\.json)", "缺失 agent/model-result.json"),
            (r"is missing (artifacts/manifest\.json)", "缺失 artifacts/manifest.json"),
            (r"is missing (verifier/test-stdout\.txt)", "缺失 verifier/test-stdout.txt"),
            (r"is missing (lock\.json)", "缺失 lock.json"),
            (r"is missing (\S+)", "缺失文件(其他): {}"),
            (r"has no recognized Qwen/Opus/GLM/Kimi alias", "模型 alias 不可识别"),
            (r"was run against a different Task checksum", "task_checksum 与交付包不一致"),
            (r"testcase set does not match tests/required_testcases\.json", "testcase 集合与 required_testcases.json 不符"),
            (r"has non-terminal status", "testcase 状态非终态(NONE)"),
            (r"verifier status is not VALID", "verifier status 非 VALID"),
            (r"verifier score is not binary 0/1", "verifier score 非二值"),
            (r"verifier/result/reward values are inconsistent", "reward 三处不一致"),
            (r"Oracle evidence is not VALID/1.*", "Oracle 证据不合规"),
            (r"NOP evidence must be VALID/0.*", "NOP 证据不合规"),
            (r"has Harbor exception_info", "存在 exception_info"),
            (r"model-result\.json.*", "model-result.json 问题"),
            (r"model provenance is unreadable.*", "model 溯源不可读"),
            (r"trajectory\.jsonl is empty", "trajectory 为空"),
            (r"contains the forbidden.*", "含禁用标签"),
            (r"contains a possible credential.*", "疑似凭据"),
            (r"jobs/ contains (\d+) (\w+) model jobs.*", "模型轮次数量异常: {}"),
            (r"jobs/ contains (\d+) (oracle|nop) jobs.*", "控制组数量异常: {}"),
            (r"jobs were run against different.*", "job 间 checksum 不一致"),
            (r"jobs/ must contain 12.*", "job 总数不合规"),
            (r"jobs/ is missing Harbor parent job file: (\S+)", "jobs/ 父级缺: {}"),
        ]
        counter: Counter = Counter()
        for e in errs:
            for pat, tpl in pats:
                m = re.search(pat, e)
                if m:
                    counter[tpl.format(*m.groups())] += 1
                    break
            else:
                counter["其他: " + e[:70]] += 1
        print("\n%s : FAIL（%d 条错误）" % (name, len(errs)))
        for k, v in counter.most_common():
            print("    %-46s × %d" % (k, v))
