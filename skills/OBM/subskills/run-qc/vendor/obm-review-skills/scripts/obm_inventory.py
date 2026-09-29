#!/usr/bin/env python3
"""Prepare per-delivery evidence packets and unresolved analyst review drafts."""
from __future__ import annotations

import argparse
from pathlib import Path

from benchmark_evidence import DEFAULT_CONFIG, locations, resolve
from git_provenance import search
from obm_hack_scan import scan
from review_common import (canonical, digest, load_json, seal, snapshot,
                           walk_files, write_json)

CHECKS = ("source_assets", "feasibility", "original_task", "verifier",
          "skill_alignment", "skill_leakage")


def upstream_status(proposal_path, report_path=None, attestation=None):
    result = {"status": "UNKNOWN", "reason": "upstream result not supplied"}
    if report_path:
        report = load_json(report_path)
        evidence = snapshot(report_path)
        matches = [r for r in report.get("results", [])
                   if Path(r.get("package", "")).expanduser().resolve() == proposal_path.parent.resolve()]
        if len(matches) != 1 or type(matches[0].get("valid")) is not bool:
            result.update(reason="validator report does not uniquely identify this package",
                          report=evidence)
        else:
            result = {"status": "PASS" if matches[0]["valid"] and not report.get("scan_issues") else "FAIL",
                      "result": matches[0], "report": evidence,
                      "binding_note": "validator has no content hashes; supplied report bound at collection time"}
    elif attestation:
        result = {"status": "PASS", "attestation": attestation,
                  "binding_note": "explicit user attestation applies to current collected package"}
    return result


def prepare(proposal_path, workspace, config=DEFAULT_CONFIG, upstream=None,
            attestation=None, corpus="all", git_report=None, pull=False,
            document_paths=None, extra_evidence=None, governing_document=None):
    proposal_path = Path(proposal_path).absolute()
    seed = snapshot(proposal_path)
    proposal = load_json(proposal_path)
    benchmark = resolve(proposal, workspace, config, pull, document_paths)
    locs = locations(workspace, config)
    related_root = benchmark.get("task_root")
    if corpus == "related":
        roots = [related_root] if related_root else []
    elif corpus == "benchmark":
        location = locs.get(proposal.get("benchmark"))
        roots = [location["tasks_root"]] if location else []
    else:
        # Related task first aids inspection; avoid duplicating it inside its corpus.
        roots = [v["tasks_root"] for k, v in sorted(locs.items(),
                 key=lambda kv: kv[0] != proposal.get("benchmark"))]
    source = scan(proposal_path.parent / "sources", roots)
    source["scope_mode"] = corpus
    source["scope_note"] = ("Local task files only. Image-only assets, remote downloads and semantic rewrites "
                            "require analyst follow-up; zero candidates is not an originality proof.")
    history = load_json(git_report) if git_report else search(proposal)
    if history.get("proposal_sha256") != digest(canonical(proposal)):
        raise ValueError("Git report belongs to a different proposal")
    packet = {
        "schema_version": 2, "review_phase": "initial_review",
        "case_path": str(proposal_path.relative_to(Path(workspace).resolve()))
        if proposal_path.is_relative_to(Path(workspace).resolve()) else str(proposal_path),
        "proposal": seed, "proposal_data": proposal,
        "upstream": upstream_status(proposal_path, upstream, attestation),
        "benchmark": benchmark, "source_comparison": source, "git_provenance": history,
        "extra_evidence": [snapshot(path) for path in (extra_evidence or [])],
        "governing_document": snapshot(
            Path(governing_document).expanduser().absolute()
            if governing_document else
            Path(__file__).resolve().parents[1] / "references/OBM Source 收集说明书.md"
        ),
    }
    if git_report:
        packet["git_report_file"] = snapshot(git_report)
    packet["packet_id"] = seal(packet)
    return packet


def draft(packet):
    return {
        "schema_version": 2, "packet_id": packet["packet_id"],
        "reviewer": "", "scope_read": [], "summary": "",
        "source_reuse": {"status": "REVIEW", "reason": "Inspect sources and classify every candidate",
                         "candidate_reviews": [{"candidate_id": c["candidate_id"],
                                                "classification": "unresolved", "reason": ""}
                                               for c in packet["source_comparison"]["candidates"]]},
        "relevance": {
            axis: {"score": None, "confidence": "low", "reason": "",
                   "proposal_quotes": [], "benchmark_quotes": []}
            for axis in ("vertical_domain", "core_capability")},
        "public_history": {"status": "REVIEW", "reason": "", "new_delta": "",
                           "repository_reviews": [], "candidate_reviews": [], "evidence": []},
        "content_checks": {name: {"status": "REVIEW", "reason": "", "evidence": []}
                           for name in CHECKS},
        "difficulty_skill_map": [],
        "coverage_resolutions": [],
        "redlines": [],
        "next_actions": []
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", action="append", required=True, help="Package, proposal.json, or batch root")
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--upstream-report")
    parser.add_argument("--upstream-attestation", help="Verbatim explicit user confirmation; do not invent")
    parser.add_argument("--corpus", choices=["all", "benchmark", "related"], default="all")
    parser.add_argument("--git-report", help="For a single proposal; run git_provenance.py first")
    parser.add_argument("--document-path", action="append")
    parser.add_argument("--extra-evidence", action="append", help="Read-only UTF-8 follow-up evidence snapshots")
    parser.add_argument(
        "--governing-document",
        help="Authoritative current requirement document; defaults to the bundled reference",
    )
    parser.add_argument("--pull", action="store_true")
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    paths, issues = set(), []
    for root in args.root:
        root = Path(root).expanduser().absolute()
        if root.is_file():
            if root.name != "proposal.json":
                parser.error("only current proposal.json is supported")
            paths.add(root)
        elif (root / "proposal.json").is_file():
            paths.add(root / "proposal.json")
        else:
            paths.update(p for p in walk_files(root, issues) if p.name == "proposal.json"
                         and "sources" not in p.relative_to(root).parts)
    if not paths:
        parser.error("no proposal.json found")
    if args.git_report and len(paths) != 1:
        parser.error("--git-report requires exactly one proposal")
    output = Path(args.output_dir).absolute()
    for path in paths:
        if output == path.parent or path.parent in output.parents:
            parser.error("output-dir must be outside submitted packages")
    index = {"cases": [], "discovery_issues": issues, "deduplication": "none; one record per real path"}
    for path in sorted(paths):
        try:
            print("collecting: " + str(path), flush=True)
            packet = prepare(path, args.workspace, args.config, args.upstream_report,
                             args.upstream_attestation, args.corpus, args.git_report,
                             args.pull, args.document_path, args.extra_evidence,
                             args.governing_document)
            folder = output / digest(str(path).encode())[:16]
            write_json(folder / "evidence.json", packet)
            write_json(folder / "review.draft.json", draft(packet))
            index["cases"].append({"case_path": packet["case_path"], "packet_id": packet["packet_id"],
                                   "evidence": str(folder / "evidence.json"),
                                   "draft": str(folder / "review.draft.json")})
        except (OSError, ValueError, KeyError, TypeError) as error:
            index["cases"].append({"case_path": str(path), "error": str(error)})
    write_json(output / "index.json", index)
    print("cases=%d output=%s" % (len(paths), output))
    return 1 if any("error" in c for c in index["cases"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
