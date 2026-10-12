"""Stage immutable task copies, run real Harbor and retain full raw logs.

No reattempts after infrastructure/load failure. Each attempt is a fresh container.
"""
from __future__ import annotations
import argparse
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from qc_utils import read, save, sha, now


def run_command(command, log):
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    env["PYTHONPATH"] = str(Path(__file__).resolve().parent) + os.pathsep + env.get("PYTHONPATH", "")
    started = now()
    with log.open("w", encoding="utf-8") as stream:
        result = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT, env=env)
    return {"command": command, "started": started, "ended": now(), "exit_code": result.returncode,
            "log": str(log)}


def classify_job(job):
    results = []
    for file in job.glob("*/result.json"):
        if file.parent.name == "logs":
            continue
        data = read(file)
        verifier = data.get("verifier_result") or {}
        results.append({"trial_id": data.get("trial_name", file.parent.name),
                        "exception": data.get("exception_info"), "rewards": verifier.get("rewards"),
                        "result_path": str(file), "trial_root": str(file.parent)})
    return results


def formal_result(trial, task):
    """Reward alone is never proof of an executed, valid testcase set."""
    if trial.get("exception"):
        return {"validity": "BLOCKED", "score": None, "reason": "Harbor trial exception"}
    verifier = Path(trial["trial_root"]) / "verifier"
    reports = [p for p in (verifier / "results.json", verifier / "report.json") if p.is_file()]
    if not reports:
        stdout = verifier / 'test-stdout.txt'
        if stdout.is_file():
            try:
                data = json.loads(stdout.read_text(encoding='utf-8-sig'))
            except (ValueError, UnicodeError):
                data = None
            if isinstance(data, dict):
                reports = [stdout]
    if len(reports) != 1:
        return {"validity": "INVALID", "score": None, "reason": "Missing or ambiguous testcase report"}
    report = read(reports[0])
    if report.get('schema_version') == 'aggregate-v1':
        # This supplied protocol prints its report to stdout. Validate against
        # the frozen rubric, never the aggregator's observed result count.
        rubric_path = Path(task['root'])/'tests/rubric.json'
        rubric = read(rubric_path) if rubric_path.is_file() else {}
        items = rubric.get('items', [])
        if not isinstance(items,list) or any(not isinstance(item,dict) or not isinstance(item.get('test_ids',[]),list) for item in items):
            return {'validity':'INVALID','score':None,'reason':'Malformed fixed required testcase set'}
        expected_ids = [i for item in items for i in item.get('test_ids', [])]
        observed = report.get('cases', [])
        if not expected_ids or any(not isinstance(i,str) for i in expected_ids) or len(set(expected_ids)) != len(expected_ids) or not isinstance(observed, list):
            return {'validity':'INVALID','score':None,'reason':'Missing fixed required testcase set'}
        if any(not isinstance(c,dict) or not isinstance(c.get('test_id'),str) for c in observed):
            return {'validity':'INVALID','score':None,'reason':'Malformed aggregate testcase'}
        ids = [c.get('test_id') for c in observed]
        if len(ids)!=len(expected_ids) or len(set(ids))!=len(ids) or set(ids)!=set(expected_ids):
            return {'validity':'INVALID','score':None,'reason':'Missing/duplicate aggregate required testcase'}
        if any(not i.startswith(('f2p-', 'p2p-')) for i in expected_ids) or any(type(c.get('passed')) is not bool for c in observed):
            return {'validity':'INVALID','score':None,'reason':'Invalid aggregate testcase group or terminal status'}
        passed = sum(c['passed'] for c in observed)
        score = report.get('formal_score')
        if any(type(report.get(k)) is not int for k in ('total','passed','failed','invalid')) or report.get('run_validity')!='VALID' or report.get('invalid')!=0 or report.get('total')!=len(ids) or report.get('passed')!=passed or report.get('failed')!=len(ids)-passed:
            return {'validity':'INVALID','score':None,'reason':'Invalid aggregate execution/counts'}
        computed = int(passed == len(ids))
        if type(score) is not int or score!=computed or (trial.get('rewards') or {}).get('reward')!=computed:
            return {'validity':'INVALID','score':None,'reason':'Aggregate report/reward mismatch'}
        cases = [{'id':c['test_id'],'group':c['test_id'].split('-')[0].upper(),'status':'PASS' if c['passed'] else 'FAIL'} for c in observed]
        return {'validity':'VALID','score':score,'cases':cases,'report':str(reports[0]),'required_source':str(rubric_path)}
    if report.get("validity", report.get("status")) != "VALID":
        return {"validity": "INVALID", "score": None, "reason": report.get("reason", "Invalid testcase execution")}
    score = report.get("score")
    if type(score) is not int or score not in (0, 1):
        return {"validity": "INVALID", "score": None, "reason": "Not a binary integer score"}
    manifest = Path(task["root"]) / "tests" / "required_testcases.json"
    if manifest.is_file():
        expected = read(manifest)
        cases = report.get("testcases", [])
        ids = [c.get("id") for c in cases]
        expected_ids = [c["id"] for c in expected]
        if not ids or len(set(ids)) != len(ids) or sorted(ids) != sorted(expected_ids) or sorted(report.get("required", [])) != sorted(ids):
            return {"validity": "INVALID", "score": None, "reason": "Missing/duplicate required testcase"}
        groups = {c["id"]: c["group"] for c in expected}
        if any(c.get("status") not in ("PASS", "FAIL") or c.get("group") != groups[c["id"]] for c in cases):
            return {"validity": "INVALID", "score": None, "reason": "Invalid testcase status or group"}
    else:
        rubric_path = Path(task["root"]) / "tests" / "rubric.json"
        if rubric_path.is_file():
            rubric = read(rubric_path)
            frozen = {"f2p": rubric.get("required_fail_to_pass", []), "p2p": rubric.get("required_pass_to_pass", [])}
            if any(sorted(report.get(g, [])) != sorted(frozen[g]) for g in frozen):
                return {"validity": "INVALID", "score": None, "reason": "Report required set differs from supplied rubric"}
        required = [(i, g) for g in ("f2p", "p2p") for i in report.get(g, [])]
        log = verifier / "go-test.txt"
        if not required or len({i for i, _ in required}) != len(required):
            return {"validity": "INVALID", "score": None, "reason": "No complete testcase execution evidence"}
        if "tests" in report:
            observed = report["tests"]
            if not isinstance(observed, list) or len(observed) != len(required) or {c.get("test_id") for c in observed} != {i for i, _ in required}:
                return {"validity": "INVALID", "score": None, "reason": "Missing/duplicate PowerShell testcase"}
            statuses = {c["test_id"]: c.get("status") for c in observed}
            if any(s not in ("PASS", "FAIL") for s in statuses.values()):
                return {"validity": "INVALID", "score": None, "reason": "Invalid PowerShell testcase terminal status"}
            cases = [{"id": i, "group": g.upper(), "status": statuses[i]} for i, g in required]
        else:
            if not log.is_file():
                return {"validity": "INVALID", "score": None, "reason": "Missing Go test execution log"}
            terminals = re.findall(r"^--- (PASS|FAIL|SKIP): (\S+)", log.read_text(encoding="utf-8"), re.M)
            cases = []
            for test_id, group in required:
                observed = [s for s, i in terminals if i == test_id]
                if len(observed) != 1 or observed[0] not in ("PASS", "FAIL"):
                    return {"validity": "INVALID", "score": None, "reason": "Incomplete Go test terminal results"}
                cases.append({"id": test_id, "group": group.upper(), "status": observed[0]})
    computed = int(all(c["status"] == "PASS" for c in cases))
    rewards = trial.get("rewards") or {}
    if score != computed or rewards.get("reward") != computed:
        return {"validity": "INVALID", "score": None, "reason": "Report/reward aggregation mismatch"}
    return {"validity": "VALID", "score": score, "cases": cases, "report": str(reports[0])}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--stage-root", type=Path, required=True)
    parser.add_argument("--task-id")
    parser.add_argument("--environment")
    parser.add_argument("--force-build", action="store_true")
    parser.add_argument("--keep-environment", action="store_true", help="Forensic only; requires explicit cleanup after evidence collection")
    parser.add_argument("--agent", choices=("nop", "oracle"))
    parser.add_argument("--attempts", type=int, choices=(1, 3), default=3)
    parser.add_argument("--collect-oracle-proof", action="store_true")
    parser.add_argument("--oracle-candidate", default="C:/testbed/src/Publisher.cs")
    parser.add_argument("--oracle-reference", default="C:/solution/Publisher.cs")
    args = parser.parse_args()
    run, stage = args.run_dir.resolve(), args.stage_root.resolve()
    if stage.exists():
        raise RuntimeError("隔离目录已存在，不能复用")
    stage.mkdir(parents=True)
    inventory = read(run / "inventory.json")
    tasks = [t for e in inventory for t in e["tasks"]]
    tasks.sort(key=lambda x: x["task_id"] != "win-fs-001")
    results = []
    for index, task in enumerate(tasks):
        if args.task_id and task["task_id"] != args.task_id:
            continue
        copied = stage / ("task" + str(index))
        shutil.copytree(task["root"], copied)
        hashes = {name: sha(copied / name) for name in task["hashes"]}
        if hashes != task["hashes"]:
            raise RuntimeError("隔离副本 Hash 与原题不一致")
        save(run / ("stage-" + task["task_id"] + ".json"), {"root": str(copied), "hashes": hashes})
        for agent in ((args.agent,) if args.agent else ("nop", "oracle")):
            for attempt in range(1, args.attempts + 1):
                name = f"qc-{index}-{agent}-{attempt}"
                job = stage / "jobs" / name
                log = stage / f"{name}.log"
                command = [shutil.which("harbor"), "run", "--path", str(copied), "--agent", agent,
                           "--n-attempts", "1", "--n-concurrent", "1", "--max-retries", "0",
                           "--jobs-dir", str(stage / "jobs"), "--job-name", name, "--quiet"]
                if args.environment:
                    command.extend(["--env", args.environment])
                if args.collect_oracle_proof:
                    command.extend(["--ek", "qc_oracle_candidate=" + args.oracle_candidate,
                                    "--ek", "qc_oracle_reference=" + args.oracle_reference])
                if args.force_build:
                    command.append("--force-build")
                if args.keep_environment:
                    command.append("--no-delete")
                    command.extend(["--ek", "keep_containers=true"])
                print(f"{task['task_id']} {agent} {attempt}/{args.attempts} 开始", flush=True)
                row = {"task_id": task["task_id"], "agent": agent, "attempt": attempt,
                       "task_hashes_verified": True, "stage": str(copied)}
                row.update(run_command(command, log))
                row["trials"] = classify_job(job) if job.exists() else []
                row["status"] = "EXECUTED" if (row["exit_code"] == 0 and row["trials"] and
                    all(not t["exception"] and t["rewards"] is not None for t in row["trials"])) else "BLOCKED"
                row["formal_results"] = [formal_result(t, task) for t in row["trials"]]
                if row["status"] == "EXECUTED" and any(x["validity"] != "VALID" for x in row["formal_results"]):
                    row["status"] = "INVALID"
                results.append(row)
                save(run / ("runs-" + stage.name + ".json"), results)
                save(run / ("progress-" + stage.name + ".json"), {"phase": "dynamic", "at": now(), "task": task["task_id"],
                                            "agent": agent, "attempt": attempt, "status": row["status"]})
                print(f"{task['task_id']} {agent} {attempt}/{args.attempts} {row['status']}", flush=True)
                if row["status"] in ("BLOCKED", "INVALID"):
                    break
    # Keep a project-local copy of the raw jobs after execution.
    destination = run / "execution" / stage.name
    if os.name == "nt":
        destination = Path("\\\\?\\" + str(destination))
    shutil.copytree(stage, destination)
    save(run / ("progress-" + stage.name + ".json"), {"phase": "dynamic-finished", "at": now(), "attempts": len(results)})


if __name__ == "__main__":
    main()
