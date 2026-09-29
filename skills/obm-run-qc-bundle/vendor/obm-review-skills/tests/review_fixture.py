"""Temporary real files shared by content-review regression tests."""
import json
from pathlib import Path
import sys

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from obm_inventory import prepare, draft
from review_common import write_json


def case(root, benchmark="terminal_bench3"):
    source = root / "case" / "sources"
    source.mkdir(parents=True)
    (source / "fixture.json").write_text('{"city":"delta","demand":37}', encoding="utf-8")
    for version in ("terminal_bench3", "terminal_bench4"):
        task = root / version / "tasks" / "dispatch"
        task.mkdir(parents=True)
        (task / "instruction.md").write_text(
            "Repair dispatch under closures. Keep committed routes frozen. " + version,
            encoding="utf-8")
    config = root / "locations.json"
    write_json(config, {"benchmarks": {v: {"root": v, "tasks": "tasks",
                                         "instruction": "instruction.md"}
                                        for v in ("terminal_bench3", "terminal_bench4")}})
    proposal = {
        "benchmark": benchmark, "related_question": "dispatch", "proposal_type": "C",
        "domain": "Operations/Dispatch", "allow_network": False,
        "proposal": {"A_modification_idea": "Add closure repair with frozen commitments.",
                     "B_modification_details": "Return globally minimal changes.",
                     "C_agent_task": "Repair dispatch under closures; freeze committed routes.",
                     "D_task_difficulties": ["Freeze committed routes."]},
        "proposal_sources": "Original work fixtures in sources/fixture.json; no Git repository.",
        "proposal_scene": "Airport dispatch recovery.",
        "proposal_verify": "Enumerate legal schedules and compare global optimum.",
        "expert_experience_skill": "Separate frozen commitments from future decisions."}
    path = source.parent / "proposal.json"
    write_json(path, proposal)
    return path, config


def packet_and_review(root):
    path, config = case(root)
    packet = prepare(path, root, config, attestation="Fixture validated", corpus="related")
    review = draft(packet)
    review.update(reviewer="regression-test", scope_read=[str(path.parent / "sources")],
                  summary="Independent dispatch task; audit fixture.", next_actions=[])
    review["source_reuse"].update(status="PASS", reason="Read original work fixtures.")
    bench = packet["benchmark"]["documents"][0]
    for value in review["relevance"].values():
        value.update(score=80, confidence="high", reason="Shared constrained dispatch mechanism.",
                     proposal_quotes=[{"document": "proposal.C_agent_task", "quote": "Repair dispatch"}],
                     benchmark_quotes=[{"document": "benchmark:" + bench["sha256"],
                                        "quote": "Repair dispatch"}])
    review["public_history"].update(
        status="NOT_APPLICABLE", reason="Work fixture with no repository.",
        evidence=[{"document": "proposal_sources", "quote": "no Git repository."}])
    for value in review["content_checks"].values():
        value.update(status="PASS", reason="Audited contract and fixture for this scenario.",
                     evidence=[{"document": "proposal.C_agent_task", "quote": "freeze committed routes."}])
    review["difficulty_skill_map"] = [{"difficulty_index": 0, "skill_quotes": [
        {"document": "expert_experience_skill", "quote": "Separate frozen commitments"}]}]
    return packet, review
