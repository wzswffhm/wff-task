#!/usr/bin/env python3
"""Run the deepSWE verifier for this task and write reward.json.

The verifier applies the agent patch to a clean checkout of the upstream
project, injects the held-out tests, runs them, and reports a binary reward.
A node id that produced no report counts as a failure; a skipped test is not a
pass. The reward is 1 only when every required F2P and P2P test passes.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

F2P = [
    "tests/test_batch_atomic.py::test_batch_commits_every_write_at_once",
    "tests/test_batch_atomic.py::test_batch_is_invisible_to_other_handles_before_commit",
    "tests/test_batch_atomic.py::test_batch_supports_read_your_writes",
    "tests/test_batch_atomic.py::test_batch_rollback_discards_every_write",
    "tests/test_batch_atomic.py::test_batch_rollback_leaves_no_files_behind",
    "tests/test_batch_atomic.py::test_batch_last_write_wins_for_one_key",
    "tests/test_batch_atomic.py::test_batch_delete_then_no_reset_removes_key",
    "tests/test_batch_atomic.py::test_batch_add_respects_staged_state",
    "tests/test_batch_atomic.py::test_batch_accepts_expire_only_after_commit",
    "tests/test_batch_atomic.py::test_batch_tagged_keys_join_tag_eviction_after_commit",
    "tests/test_batch_atomic.py::test_batch_rejects_nesting",
    "tests/test_batch_atomic.py::test_batch_rejects_operations_that_cannot_be_staged",
    "tests/test_batch_atomic.py::test_batch_crash_leaves_cache_unchanged",
]

P2P = [
    "tests/test_core.py::test_init",
    "tests/test_core.py::test_getsetdel",
    "tests/test_core.py::test_get_keyerror1",
    "tests/test_core.py::test_get_keyerror4",
    "tests/test_core.py::test_read",
    "tests/test_core.py::test_set_twice",
    "tests/test_core.py::test_raw",
    "tests/test_core.py::test_get",
    "tests/test_core.py::test_get_expired_fast_path",
    "tests/test_core.py::test_get_ioerror_fast_path",
    "tests/test_core.py::test_get_expired_slow_path",
    "tests/test_core.py::test_pop",
    "tests/test_core.py::test_delete",
    "tests/test_core.py::test_del",
    "tests/test_core.py::test_del_expired",
    "tests/test_core.py::test_stats",
    "tests/test_core.py::test_expire_rows",
    "tests/test_core.py::test_check",
    "tests/test_core.py::test_expire",
    "tests/test_core.py::test_evict",
    "tests/test_core.py::test_clear",
    "tests/test_core.py::test_tag",
    "tests/test_core.py::test_with",
    "tests/test_core.py::test_contains",
    "tests/test_core.py::test_touch",
    "tests/test_core.py::test_add",
    "tests/test_core.py::test_incr",
    "tests/test_core.py::test_decr",
    "tests/test_core.py::test_iter",
    "tests/test_core.py::test_reversed",
    "tests/test_core.py::test_push_pull",
]


class ResultCollector:
    """Collect the outcome of every requested node id."""

    def __init__(self):
        self.outcomes = {}

    def pytest_runtest_logreport(self, report):
        if report.when == 'call':
            self.outcomes[report.nodeid] = report.outcome
        elif report.when == 'setup' and report.outcome == 'skipped':
            self.outcomes.setdefault(report.nodeid, 'skipped')
        elif report.when == 'setup' and report.outcome == 'error':
            self.outcomes.setdefault(report.nodeid, 'error')


def apply_patch(app: Path, patch: Path) -> dict:
    """Apply the agent patch. Returns a structured record."""
    if not patch.is_file():
        return {"applied": False, "reason": "model.patch not found"}

    for command in (
        ['git', 'apply', '--3way', '--whitespace=nowarn', str(patch)],
        ['git', 'apply', '--reject', '--whitespace=nowarn', str(patch)],
        ['patch', '-p1', '-f', '-i', str(patch)],
    ):
        result = subprocess.run(command, cwd=str(app), capture_output=True, text=True)
        if result.returncode == 0:
            return {"applied": True, "command": ' '.join(command)}
    return {
        "applied": False,
        "reason": "patch did not apply",
        "stderr": result.stderr[-2000:],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app', default='/app')
    parser.add_argument('--artifacts', default='/logs/artifacts')
    parser.add_argument('--logs', default='/logs/verifier')
    parser.add_argument('--skip-patch', action='store_true',
                        help='run against the current work tree (local NOP/Oracle check)')
    args = parser.parse_args()

    app = Path(args.app).resolve()
    artifacts = Path(args.artifacts).resolve()
    logs = Path(args.logs).resolve()
    logs.mkdir(parents=True, exist_ok=True)

    report = {"benchmark": "deepSWE", "task": "2026-09-28-2-diskcache-atomic-write-batch"}

    if args.skip_patch:
        report["patch"] = {"applied": True, "command": "skipped"}
    else:
        report["patch"] = apply_patch(app, artifacts / 'model.patch')

    node_ids = F2P + P2P
    collector = ResultCollector()
    os.chdir(str(app))
    sys.path.insert(0, str(app))

    if report["patch"]["applied"]:
        pytest.main(
            ['-p', 'no:cacheprovider', '-o', 'addopts=', '--tb=line', '-q', *node_ids],
            plugins=[collector],
        )

    def status(nodeid):
        outcome = collector.outcomes.get(nodeid)
        if outcome is None:
            # A test that never reported is treated as a failure.
            return 'missing' if report["patch"]["applied"] else 'not_run'
        return outcome

    f2p = {nodeid: status(nodeid) for nodeid in F2P}
    p2p = {nodeid: status(nodeid) for nodeid in P2P}

    f2p_passed = [n for n, s in f2p.items() if s == 'passed']
    p2p_passed = [n for n, s in p2p.items() if s == 'passed']
    reward = 1 if len(f2p_passed) == len(F2P) and len(p2p_passed) == len(P2P) else 0

    report.update({
        "reward": reward,
        "f2p_total": len(F2P),
        "f2p_passed": len(f2p_passed),
        "p2p_total": len(P2P),
        "p2p_passed": len(p2p_passed),
        "f2p": f2p,
        "p2p": p2p,
        "failures": [n for n, s in list(f2p.items()) + list(p2p.items())
                     if s != 'passed'],
    })

    (logs / 'reward.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8'
    )
    print(json.dumps({k: report[k] for k in
                      ('reward', 'f2p_passed', 'f2p_total', 'p2p_passed', 'p2p_total')},
                     indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
