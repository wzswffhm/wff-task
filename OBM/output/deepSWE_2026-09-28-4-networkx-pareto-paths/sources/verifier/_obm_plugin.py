"""Minimal pytest plugin: dump {nodeid: outcome} to $OBM_OUTCOMES.

Using pytest's own nodeid avoids any dependency on junit-xml attribute layout
(which differs across pytest versions and between package / class / path cases).
"""

import json
import os

_RESULTS = {}
_RANK = {"passed": 0, "skipped": 1, "failed": 2}


def pytest_runtest_logreport(report):
    if report.when == "call":
        outcome = report.outcome
    elif report.when == "setup" and report.outcome != "passed":
        outcome = "failed"  # 收集/夹具阶段出错即视为失败
    else:
        return
    previous = _RESULTS.get(report.nodeid)
    if previous is None or _RANK[outcome] > _RANK[previous]:
        _RESULTS[report.nodeid] = outcome


def pytest_sessionfinish(session, exitstatus):  # noqa: ARG001
    target = os.environ.get("OBM_OUTCOMES")
    if target:
        with open(target, "w", encoding="utf-8") as handle:
            json.dump(_RESULTS, handle, ensure_ascii=False)
