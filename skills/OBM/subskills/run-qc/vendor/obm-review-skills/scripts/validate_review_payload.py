#!/usr/bin/env python3
"""Validate analyst judgments against a bound packet and compute the review conclusion."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import math
from pathlib import Path
import re

from obm_inventory import CHECKS
from review_common import canonical, digest, load_json, read_bytes, seal, write_json

EXIT = {"ACCEPT": 0, "REVIEW": 2, "FAIL": 3, "REJECT": 4}
LABEL = {"ACCEPT": "通过初验", "REVIEW": "需人工复核/补证据", "FAIL": "不通过/需重做",
         "REJECT": "拒绝当前交付"}
CLAUSES = {
    "R01": "proposal存在矛盾/错误、不存在可能解",
    "R03": "解决方案 与已有 patch 高度相似",
    "R04": "修改公开 benchmark 的名字/数字形成新题；",
    "R05": "Verifier 只是复制已有 tests",
    "R07": "Skill 泄漏或基于test书写",
    "R08": "任务可以通过搜索直接找到 solution",
}


def score_status(value):
    if value is None:
        return "REVIEW"
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 100:
        raise ValueError("score must be a finite number 0..100, or null; bool is invalid")
    return "FAIL" if value < 20 else "REVIEW" if value < 50 else "PASS"


def documents(packet):
    proposal = packet["proposal_data"]
    docs = {}
    for key, value in proposal.items():
        if isinstance(value, str):
            docs[key] = value
        elif key == "proposal":
            for name, text in value.items():
                docs["proposal." + name] = text if isinstance(text, str) else "\n".join(text)
    for item in packet["benchmark"]["documents"]:
        docs["benchmark:" + item["sha256"]] = item["text"]
    for item in packet["source_comparison"]["source"]["files"]:
        if "!/" not in item["path"]:
            try:
                docs["source:" + item["sha256"]] = read_bytes(item["path"]).decode("utf-8-sig")
            except (ValueError, OSError, UnicodeError):
                pass
        else:
            docs["source:" + item["sha256"]] = item["excerpt"]
    for item in packet["git_provenance"]["candidates"]:
        docs["git:" + item["candidate_id"]] = item["text"]
    for item in packet.get("extra_evidence", []):
        docs["extra:" + item["sha256"]] = item["text"]
    return docs


def verify_bindings(packet):
    errors = []
    if packet.get("schema_version") != 2 or packet.get("packet_id") != seal(packet):
        errors.append("packet hash/schema mismatch")
    expected = packet.get("proposal", {}).get("text", "")
    try:
        import json
        if json.loads(expected) != packet["proposal_data"]:
            errors.append("proposal_data does not match raw proposal snapshot")
    except (ValueError, KeyError):
        errors.append("invalid proposal snapshot")
    items = [packet["proposal"], packet["governing_document"]]
    items.extend(packet["benchmark"]["documents"])
    items.extend(packet.get("extra_evidence", []))
    if "git_report_file" in packet:
        items.append(packet["git_report_file"])
    if "report" in packet["upstream"]:
        items.append(packet["upstream"]["report"])
    items.extend(packet["source_comparison"]["source"]["files"])
    for scope in packet["source_comparison"]["benchmark_scope"]:
        items.extend(scope["files"])
    checked = set()
    for item in items:
        path = item["path"]
        if path.startswith("docker:") or "!/" in path or path in checked:
            continue
        checked.add(path)
        try:
            # Read streaming so a large manifest entry does not allocate unbounded memory.
            import hashlib
            if Path(path).is_symlink():
                raise ValueError("changed to symlink")
            h = hashlib.sha256()
            with Path(path).open("rb") as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    h.update(block)
            if h.hexdigest() != item["sha256"]:
                errors.append("evidence changed: " + path)
        except (OSError, ValueError) as error:
            errors.append("evidence unavailable: " + path + ": " + str(error))
    # New or deleted source files must invalidate stale packets as well.
    from review_common import walk_files
    root = packet["source_comparison"]["source"]["root"]
    observed = {str(p.absolute()) for p in walk_files(root, [])}
    recorded = {i["path"] for i in packet["source_comparison"]["source"]["files"] if "!/" not in i["path"]}
    skipped = {i["path"] for i in packet["source_comparison"]["issues"]}
    if observed - recorded - skipped or recorded - observed:
        errors.append("source tree membership changed; recollect evidence")
    return errors


def finalize(packet, review):
    errors = verify_bindings(packet)
    blockers, warnings, codes = [], [], []
    docs = documents(packet)

    def require(condition, message):
        if not condition:
            errors.append(message)

    def reason(item, label):
        require(isinstance(item.get("reason"), str) and bool(item["reason"].strip()),
                label + ": explanation required")

    def quotes(items, label, prefix=None, required=True):
        require(isinstance(items, list), label + ": quotes must be an array")
        if not isinstance(items, list):
            return
        if required:
            require(bool(items), label + ": evidence quotes required")
        for quote in items:
            if not isinstance(quote, dict):
                errors.append(label + ": quote must be object")
                continue
            key, text = quote.get("document", ""), quote.get("quote", "")
            require(key in docs and isinstance(text, str) and bool(text.strip())
                    and text in docs.get(key, ""), label + ": quote does not match evidence")
            if prefix:
                require(key.startswith(prefix), label + ": wrong evidence source")

    def coverage_gaps(scope, issues):
        unresolved = []
        for issue in issues:
            if isinstance(issue, dict) and issue.get("reason") == "excluded_metadata":
                continue
            ident = digest(canonical(issue))
            resolutions = [r for r in review.get("coverage_resolutions", [])
                           if r.get("scope") == scope and r.get("issue_id") == ident]
            if len(resolutions) != 1:
                unresolved.append(issue)
                continue
            reason(resolutions[0], "coverage resolution")
            quotes(resolutions[0].get("evidence", []), "follow-up coverage", "extra:")
        return unresolved

    require(review.get("schema_version") == 2, "review schema_version must be 2")
    require(review.get("packet_id") == packet.get("packet_id"), "review belongs to another packet")
    require(bool(review.get("reviewer", "").strip()), "reviewer required")
    source = review.get("source_reuse", {})
    reason(source, "source_reuse")
    candidates = {c["candidate_id"]: c for c in packet["source_comparison"]["candidates"]}
    seen, confirmed = set(), []
    for item in source.get("candidate_reviews", []):
        ident, classification = item.get("candidate_id"), item.get("classification")
        require(ident in candidates and ident not in seen, "unknown or duplicate source candidate")
        seen.add(ident)
        reason(item, "source candidate")
        require(classification in {"task_specific_reuse", "common_upstream", "boilerplate",
                                   "provenance_only", "unrelated", "unresolved"},
                "invalid source classification")
        if classification == "task_specific_reuse":
            require(bool(item.get("task_specific_evidence")), "explain why reused content is task-specific")
            confirmed.append(ident)
        elif classification == "unresolved":
            warnings.append("unresolved source match: " + str(ident))
    if confirmed:
        # H02 early stop: no downstream relevance/quality judgment is required or emitted.
        codes.append("H02")
        result = "REJECT"
    else:
        require(seen == set(candidates), "every source candidate must be classified")
        require(source.get("status") in {"PASS", "REVIEW"}, "source status must be PASS or REVIEW")
        if source.get("status") != "PASS":
            warnings.append("source content audit unresolved")
        if coverage_gaps("source", packet["source_comparison"]["issues"]):
            warnings.append("source/benchmark scan has coverage gaps")
        if not review.get("scope_read"):
            errors.append("scope_read must identify manually inspected source assets")
        upstream = packet["upstream"]["status"]
        if upstream == "FAIL":
            blockers.append("upstream validation failed")
        elif upstream != "PASS":
            warnings.append("upstream validation not confirmed")
        axis_results = {}
        prompt_complete = bool(packet["benchmark"]["documents"]) and not packet["benchmark"]["issues"]
        for axis in ("vertical_domain", "core_capability"):
            item = review.get("relevance", {}).get(axis, {})
            reason(item, axis)
            status = score_status(item.get("score"))
            axis_results[axis] = status
            if item.get("score") is not None:
                require(prompt_complete, "actual benchmark prompt missing/incomplete; score must be null")
                require(item.get("confidence") in {"low", "medium", "high"}, axis + ": confidence required")
                quotes(item.get("proposal_quotes", []), axis, "proposal.C_agent_task")
                quotes(item.get("benchmark_quotes", []), axis, "benchmark:")
            if status == "FAIL":
                blockers.append(axis + " relevance below 20%")
            elif status == "REVIEW":
                warnings.append(axis + " relevance below 50% or evidence missing")
        history = review.get("public_history", {})
        reason(history, "public_history")
        require(history.get("status") in {"PASS", "REVIEW", "REJECT", "NOT_APPLICABLE"},
                "invalid public_history status")
        repos = set(packet["git_provenance"]["repositories"])
        if history.get("status") == "NOT_APPLICABLE":
            require(not repos, "public history cannot be N/A when repositories are cited")
            quotes(history.get("evidence", []), "history applicability")
        else:
            if history.get("status") in {"PASS", "REJECT"}:
                require(bool(history.get("new_delta", "").strip()), "identify original delta versus base functionality")
                quotes(history.get("evidence", []), "history delta", "proposal.")
                checked_repos = {r.get("repository") for r in history.get("repository_reviews", [])}
                require(checked_repos == repos and bool(repos), "every source repository needs a history review")
                for repo_review in history.get("repository_reviews", []):
                    reason(repo_review, "repository review")
            if history.get("status") == "REVIEW":
                warnings.append("public history audit unresolved")
            if coverage_gaps("history", packet["git_provenance"]["issues"]):
                warnings.append("public history search has coverage gaps")
            git_candidates = {c["candidate_id"]: c for c in packet["git_provenance"]["candidates"]}
            git_seen, derived = set(), False
            for item in history.get("candidate_reviews", []):
                ident = item.get("candidate_id")
                require(ident in git_candidates and ident not in git_seen, "unknown or duplicate Git candidate")
                git_seen.add(ident)
                reason(item, "Git candidate")
                require(item.get("classification") in {"base_functionality", "unrelated", "unresolved",
                                                       "derived_from_public_change"}, "invalid Git classification")
                if item.get("classification") == "unresolved":
                    warnings.append("unresolved public change")
                if item.get("classification") == "derived_from_public_change":
                    candidate = git_candidates.get(ident, {})
                    require(candidate.get("public_verified") is True and
                            bool(re.fullmatch(r"[a-fA-F0-9]{40}", candidate.get("sha", ""))),
                            "public derivation requires public immutable commit evidence")
                    require(item.get("time_basis") in {"known_before_submission", "public_at_review"},
                            "public finding requires explicit timing basis")
                    if item.get("time_basis") == "known_before_submission":
                        quotes(item.get("timing_evidence", []), "publication before submission")
                    quotes(item.get("evidence", []), "public change match", "git:" + str(ident))
                    derived = True
            require(git_seen == set(git_candidates), "every Git candidate must be classified")
            if history.get("status") == "REJECT":
                require(derived, "history REJECT requires a confirmed public change")
            if derived:
                codes.append("R02")
        for name in CHECKS:
            item = review.get("content_checks", {}).get(name, {})
            reason(item, name)
            require(item.get("status") in {"PASS", "FAIL", "REVIEW"}, name + ": invalid status")
            quotes(item.get("evidence", []), name, required=item.get("status") != "REVIEW")
            if item.get("status") == "FAIL":
                blockers.append(name)
            elif item.get("status") != "PASS":
                warnings.append(name + " unresolved")
        mapping = review.get("difficulty_skill_map", [])
        difficulties = packet["proposal_data"].get("proposal", {}).get("D_task_difficulties", [])
        if review.get("content_checks", {}).get("skill_alignment", {}).get("status") == "PASS":
            require({m.get("difficulty_index") for m in mapping} == set(range(len(difficulties))),
                    "D difficulties require complete zero-based skill mapping")
            for row in mapping:
                quotes(row.get("skill_quotes", []), "D/skill mapping", "expert_experience_skill")
        for redline in review.get("redlines", []):
            code = redline.get("code")
            require(code in CLAUSES and redline.get("clause") == CLAUSES.get(code),
                    "redline must quote current governing clause exactly")
            require(redline.get("clause", "") in packet["governing_document"]["text"],
                    "redline clause absent from governing document")
            reason(redline, "redline")
            quotes(redline.get("evidence", []), "redline")
            if code in CLAUSES:
                codes.append(code)
        result = "REJECT" if codes else "FAIL" if blockers else "REVIEW" if warnings else "ACCEPT"
    return {"schema_version": 2, "packet_id": packet["packet_id"], "case_path": packet["case_path"],
            "valid": not errors, "validation_errors": errors,
            "conclusion": result if not errors else None, "label": LABEL[result] if not errors else None,
            "early_stop": bool(confirmed), "codes": codes, "blockers": blockers, "warnings": warnings,
            "confirmed_source_evidence": [candidates[ident] for ident in confirmed if ident in candidates],
            "relevance_status": {} if confirmed else axis_results,
            "reviewed_at": datetime.now(timezone.utc).isoformat(),
            "review": ({"reviewer": review.get("reviewer"), "source_reuse": source}
                       if confirmed else review),
            "scope": "initial_review; solvability and actual Skill gain require later rollout"}


def markdown(result):
    lines = ["# OBM 内容审查", "", "题目路径：" + result["case_path"], "",
             "结论：" + str(result["label"] or "结果格式/证据校验失败"), "",
             "证据包：" + result["packet_id"], ""]
    review = result["review"]
    if result["early_stop"]:
        lines += ["H02：确认任务特有内容复用，停止后续审查。", "",
                  review["source_reuse"].get("reason", "")]
        for match in result["confirmed_source_evidence"]:
            for side in ("source", "benchmark"):
                evidence = match[side]
                lines += ["", side + "：" + evidence["path"], "",
                          "SHA-256：" + evidence["sha256"], "", evidence["excerpt"]]
    else:
        for axis, label in (("vertical_domain", "垂直领域"), ("core_capability", "核心能力")):
            item = review.get("relevance", {}).get(axis, {})
            lines += [label + "：" + (str(item.get("score")) + "%" if item.get("score") is not None else "未评分"),
                      "判定：" + result["relevance_status"].get(axis, "REVIEW"),
                      "", item.get("reason", ""), ""]
        lines += [review.get("summary", ""), ""]
    for title, key in (("不通过项", "blockers"), ("待复核项", "warnings"), ("校验错误", "validation_errors")):
        if result[key]:
            lines += ["## " + title, ""] + ["- " + item for item in result[key]] + [""]
    lines += ["## 证据判断", "", "```json",
              __import__("json").dumps(review, ensure_ascii=False, indent=2), "```", "",
              "初验结论不代表已证明可解或 Skill 实际有效。", ""]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("review")
    parser.add_argument("--evidence", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        result = finalize(load_json(args.evidence), load_json(args.review))
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        write_json(args.output, {"valid": False, "validation_errors": [str(error)], "conclusion": None})
        print("invalid review: " + str(error))
        return 1
    write_json(args.output, result)
    Path(args.output).with_suffix(".md").write_text(markdown(result), encoding="utf-8")
    print("valid=%s conclusion=%s" % (result["valid"], result["conclusion"]))
    return EXIT[result["conclusion"]] if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
