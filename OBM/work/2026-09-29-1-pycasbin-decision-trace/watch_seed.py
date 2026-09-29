#!/usr/bin/env python3
"""Watch the Seed experiment run-root and report every 180 seconds.

Prints one status line per check (stage / turns / elapsed). Exits as soon as
MONITOR_RESULT.json appears (terminal state), emitting the final result so the
calling session gets notified. Read-only: never touches experiment files.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

RUN_ROOT = Path(__file__).resolve().parent / "agent-runs-3"
INTERVAL_SECONDS = 180


def last_snapshot() -> dict | None:
    log = RUN_ROOT / "MONITOR_STATUS.jsonl"
    if not log.is_file():
        return None
    try:
        lines = [line for line in log.read_text(encoding="utf-8").splitlines() if line.strip()]
    except OSError:
        return None
    for line in reversed(lines):
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            return data
    return None


def report_line(snapshot: dict | None) -> str:
    if not snapshot:
        return "[watch] 尚无状态快照（监控器可能仍在启动）"
    turns = snapshot.get("turns") or {}
    no = turns.get("no_skill") if isinstance(turns, dict) else None
    with_ = turns.get("with_skill") if isinstance(turns, dict) else None
    return (
        "[watch] {observed_at} stage={stage} elapsed={elapsed}s "
        "no_skill_turns={no} with_skill_turns={with_}".format(
            observed_at=snapshot.get("observed_at", "?"),
            stage=snapshot.get("stage", "?"),
            elapsed=snapshot.get("elapsed_seconds", "?"),
            no=no if no is not None else 0,
            with_=with_ if with_ is not None else 0,
        )
    )


def main() -> int:
    print(f"[watch] 开始看护 {RUN_ROOT}（每 {INTERVAL_SECONDS}s 一次）", flush=True)
    while True:
        monitor_result = RUN_ROOT / "MONITOR_RESULT.json"
        snapshot = last_snapshot()
        print(report_line(snapshot), flush=True)
        if monitor_result.is_file():
            try:
                result = json.loads(monitor_result.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                print(f"[watch] 终态但 MONITOR_RESULT.json 不可读：{exc}", flush=True)
                return 1
            print("[watch] SEED 已到终态：", flush=True)
            print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
            for name in ("EXPERIMENT_RESULT.json", "TURN_STATS.json"):
                path = RUN_ROOT / name
                print(f"[watch] {name}: {'存在' if path.is_file() else '缺失'}", flush=True)
            experiment = RUN_ROOT / "EXPERIMENT_RESULT.json"
            if experiment.is_file():
                try:
                    data = json.loads(experiment.read_text(encoding="utf-8"))
                    print(
                        "[watch] EXPERIMENT_RESULT.status = {}".format(data.get("status")),
                        flush=True,
                    )
                except (OSError, json.JSONDecodeError):
                    pass
            return 0
        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    sys.exit(main())
