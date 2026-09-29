"""End-to-end judgments over real temporary evidence; replaces obsolete H01/checklist tests."""
import copy
import tempfile
import unittest
from pathlib import Path

from review_fixture import packet_and_review
from obm_hack_scan import scan
from review_common import canonical, digest, seal
from validate_review_payload import finalize, score_status


class TestReviewTools(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.packet, self.review = packet_and_review(self.root)

    def reseal(self):
        self.packet["packet_id"] = seal(self.packet)
        self.review["packet_id"] = self.packet["packet_id"]

    def result(self):
        value = finalize(self.packet, self.review)
        self.assertTrue(value["valid"], value["validation_errors"])
        return value

    def test_threshold_boundaries_and_worst_axis(self):
        for score, expected in [(0, "FAIL"), (19, "FAIL"), (19.99, "FAIL"),
                                (20, "REVIEW"), (49, "REVIEW"), (49.99, "REVIEW"),
                                (50, "ACCEPT"), (100, "ACCEPT")]:
            with self.subTest(score=score):
                self.review["relevance"]["vertical_domain"]["score"] = score
                self.review["relevance"]["core_capability"]["score"] = 100
                self.assertEqual(self.result()["conclusion"], expected)
        self.review["relevance"]["vertical_domain"]["score"] = 100
        self.review["relevance"]["core_capability"]["score"] = 19
        self.assertEqual(self.result()["conclusion"], "FAIL")

    def test_score_rejects_boolean_nan_and_out_of_range(self):
        for value in [True, False, float("nan"), float("inf"), -1, 101, "80"]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                score_status(value)
        self.assertEqual(score_status(None), "REVIEW")

    def test_missing_prompt_allows_only_null_review(self):
        self.packet["benchmark"]["documents"] = []
        self.packet["benchmark"]["issues"] = [{"path": "image", "reason": "missing"}]
        self.reseal()
        self.assertFalse(finalize(self.packet, self.review)["valid"])
        for item in self.review["relevance"].values():
            item.update(score=None, proposal_quotes=[], benchmark_quotes=[])
        self.assertEqual(self.result()["conclusion"], "REVIEW")

    def test_misquoted_evidence_and_packet_mismatch_are_invalid(self):
        self.review["relevance"]["vertical_domain"]["proposal_quotes"][0]["quote"] = "fabricated"
        self.assertFalse(finalize(self.packet, self.review)["valid"])
        self.review["packet_id"] = "different"
        self.assertTrue(any("another packet" in e for e in finalize(self.packet, self.review)["validation_errors"]))

    def test_source_mutation_and_new_file_invalidate_prior_review(self):
        self.assertEqual(self.result()["conclusion"], "ACCEPT")
        source = self.root / "case/sources/fixture.json"
        original = source.read_bytes()
        source.write_bytes(b'{"changed":true}')
        self.assertTrue(any("evidence changed" in e for e in finalize(self.packet, self.review)["validation_errors"]))
        source.write_bytes(original)
        (source.parent / "new.json").write_text("{}")
        self.assertTrue(any("membership changed" in e for e in finalize(self.packet, self.review)["validation_errors"]))

    def test_confirmed_hack_short_circuits_without_downstream_judgments(self):
        task = self.root / "terminal_bench3/tasks/dispatch"
        (task / "specific.json").write_bytes((self.root / "case/sources/fixture.json").read_bytes())
        self.packet["source_comparison"] = scan(self.root / "case/sources", [task])
        candidate = self.packet["source_comparison"]["candidates"][0]
        self.reseal()
        minimal = {"schema_version": 2, "packet_id": self.packet["packet_id"], "reviewer": "test",
                   "source_reuse": {"status": "REJECT", "reason": "Confirmed task-specific input reuse.",
                                    "candidate_reviews": [{
                                        "candidate_id": candidate["candidate_id"],
                                        "classification": "task_specific_reuse",
                                        "reason": "Specific patient records copied byte-for-byte.",
                                        "task_specific_evidence": "Fixture hash and values match task asset."
                                    }]}}
        result = finalize(self.packet, minimal)
        self.assertTrue(result["valid"], result["validation_errors"])
        self.assertEqual(result["conclusion"], "REJECT")
        self.assertEqual(result["codes"], ["H02"])
        self.assertTrue(result["early_stop"])
        self.assertNotIn("relevance", result["review"])

    def test_boilerplate_match_can_pass_but_unresolved_match_cannot(self):
        task = self.root / "terminal_bench3/tasks/dispatch"
        text = "Permission is hereby granted, free of charge, to any person obtaining a copy."
        (task / "LICENSE").write_text(text)
        (self.root / "case/sources/LICENSE").write_text(text)
        self.packet["source_comparison"] = scan(self.root / "case/sources", [task])
        candidate = self.packet["source_comparison"]["candidates"][0]
        self.reseal()
        item = {"candidate_id": candidate["candidate_id"], "classification": "boilerplate",
                "reason": "Shared MIT license text; no task inputs or answer."}
        self.review["source_reuse"]["candidate_reviews"] = [item]
        self.assertEqual(self.result()["conclusion"], "ACCEPT")
        item["classification"] = "unresolved"
        self.assertEqual(self.result()["conclusion"], "REVIEW")

    def test_upstream_fail_does_not_become_accept(self):
        self.packet["upstream"]["status"] = "FAIL"
        self.reseal()
        self.assertEqual(self.result()["conclusion"], "FAIL")

    def test_empty_sources_cannot_prove_no_hack(self):
        (self.root / "case/sources/fixture.json").unlink()
        self.packet["source_comparison"] = scan(self.root / "case/sources",
                                               [self.root / "terminal_bench3/tasks/dispatch"])
        self.reseal()
        self.assertEqual(self.result()["conclusion"], "REVIEW")

    def test_public_change_must_be_verified_and_distinct_from_baseline(self):
        repo = "https://github.com/example/dispatch"
        candidate = {"repository": repo, "kind": "commit", "sha": "a" * 40,
                     "url": repo + "/commit/" + "a" * 40, "text": "+repair_frozen_routes()",
                     "public_verified": True}
        candidate["candidate_id"] = digest(canonical(candidate))
        self.packet["git_provenance"].update(repositories=[repo], issues=[], candidates=[candidate])
        self.reseal()
        history = self.review["public_history"]
        history.update(status="PASS", new_delta="Closure repair with frozen commitments.",
                       repository_reviews=[{"repository": repo, "reason": "Checked commits and PRs."}],
                       evidence=[{"document": "proposal.A_modification_idea", "quote": "Add closure repair"}],
                       candidate_reviews=[{"candidate_id": candidate["candidate_id"],
                                           "classification": "base_functionality",
                                           "reason": "Existing base; distinct task increment."}])
        self.assertEqual(self.result()["conclusion"], "ACCEPT")
        history["status"] = "REJECT"
        item = history["candidate_reviews"][0]
        item.update(classification="derived_from_public_change", time_basis="public_at_review",
                    evidence=[{"document": "git:" + candidate["candidate_id"], "quote": "+repair_frozen_routes()"}])
        self.assertEqual(self.result()["conclusion"], "REJECT")
        self.assertEqual(self.result()["codes"], ["R02"])
        candidate["public_verified"] = False
        self.reseal()
        self.assertFalse(finalize(self.packet, self.review)["valid"])

    def test_missing_difficulty_mapping_prevents_skill_pass(self):
        self.review["difficulty_skill_map"] = []
        result = finalize(self.packet, self.review)
        self.assertFalse(result["valid"])
        self.assertTrue(any("skill mapping" in error for error in result["validation_errors"]))
