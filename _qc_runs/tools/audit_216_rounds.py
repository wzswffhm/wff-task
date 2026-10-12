"""汇总 runner runs 目录每一轮的 identity / 证据完整性（只读）。"""
import json
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
for run in sorted(p for p in root.iterdir() if p.is_dir()):
    for label_dir in sorted(p for p in run.iterdir() if p.is_dir()):
        res = label_dir / "result.json"
        has_agent_log = (label_dir / "agent.log").is_file()
        has_ident_file = (label_dir / "task_identity.json").is_file()
        has_prompt_sys = (label_dir / "prompt.system.txt").is_file()
        has_prompt_task = (label_dir / "prompt.task.txt").is_file()
        has_test_log = (label_dir / "test.log").is_file()
        has_checks = (label_dir / "checks.json").is_file()
        info = {}
        if res.is_file():
            try:
                info = json.loads(res.read_text(encoding="utf-8-sig"))
            except Exception as exc:  # noqa: BLE001
                info = {"_error": str(exc)}
        ident = info.get("task_identity") or {}
        print(
            f"{run.name:<52} label={label_dir.name:<18} "
            f"ver={info.get('task_version')} verdict={info.get('verdict')} "
            f"ident={'Y' if ident else 'N'} hash={(ident.get('task_hash') or '-')[:16]} "
            f"digest={(ident.get('docker_image_digest') or '-')[:20]} "
            f"[agent.log={has_agent_log} ident.json={has_ident_file} "
            f"psys={has_prompt_sys} ptask={has_prompt_task} test.log={has_test_log} checks={has_checks}]"
        )
