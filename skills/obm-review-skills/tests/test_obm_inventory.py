import tempfile
import unittest
from pathlib import Path

from review_fixture import case
from obm_inventory import draft, prepare, upstream_status
from review_common import load_json, write_json


class TestInventory(unittest.TestCase):
    def test_upstream_report_matches_exact_package_and_honors_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path, _ = case(root)
            report = root / "report.json"
            write_json(report, {"valid": False, "results": [
                {"package": str(path.parent), "valid": False, "issues": [{"code": "domain_mismatch"}]}]})
            result = upstream_status(path, report)
            self.assertEqual(result["status"], "FAIL")
            self.assertEqual(result["result"]["issues"][0]["code"], "domain_mismatch")
            write_json(report, {"valid": True, "results": [
                {"package": str(root / "another"), "valid": True, "issues": []}]})
            self.assertEqual(upstream_status(path, report)["status"], "UNKNOWN")
            self.assertEqual(upstream_status(path, attestation="User confirmed")["status"], "PASS")

    def test_source_change_invalidates_packet_and_draft_starts_unresolved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path, config = case(root)
            first = prepare(path, root, config, corpus="related")
            (path.parent / "sources/fixture.json").write_text('{"city":"different"}')
            second = prepare(path, root, config, corpus="related")
            self.assertNotEqual(first["packet_id"], second["packet_id"])
            review = draft(second)
            self.assertEqual(review["source_reuse"]["status"], "REVIEW")
            self.assertIsNone(review["relevance"]["vertical_domain"]["score"])
            self.assertNotIn("conclusion", review)
            self.assertEqual(first["upstream"]["status"], "UNKNOWN")

    def test_git_report_for_different_proposal_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path, config = case(root)
            history = root / "history.json"
            write_json(history, {"proposal_sha256": "wrong"})
            with self.assertRaisesRegex(ValueError, "different proposal"):
                prepare(path, root, config, corpus="related", git_report=history)
