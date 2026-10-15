import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from image_delivery_review import IMAGE_CHECKS, image_review_template
from run_delivery_qc import QUALITY_GATES, load_quality_review
from review_fixtures import passing_windows_image, passing_tools, passing_nested_virtualization


class ImageDeliveryReviewTests(unittest.TestCase):
    def review(self):
        review = {
            key: {"status": "PASS", "evidence": [f"review/{key}.md"], "notes": "unit fixture"}
            for key in QUALITY_GATES
        }
        image = image_review_template()
        image.update(status="PASS", evidence=["image-delivery/review.md"],
                     configured_image="wcb-test:final", resolved_image_digest="sha256:" + "b" * 64,
                     target_profile={"windows_build": "20348", "architecture": "amd64",
                                     "isolation": "process", "can_build_images": False})
        image["checks"] = {
            key: {"status": "PASS", "evidence": [f"image-delivery/{key}.log"],
                  "notes": "unit fixture; raw execution requires manual examination"}
            for key in IMAGE_CHECKS
        }
        review["image_delivery"] = image
        review["windows_image_policy"] = passing_windows_image("wcb-test:final")
        review["toolchain_in_image"] = passing_tools()
        review["nested_virtualization"] = passing_nested_virtualization("wcb-test:final")
        return review

    def load(self, review, expected_image="wcb-test:final"):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "quality-review.json"
            path.write_text(json.dumps(review), encoding="utf-8")
            return load_quality_review(path, expected_image)

    def test_old_ten_gate_review_cannot_grant_final_pass(self):
        review = self.review()
        del review["image_delivery"]
        result = self.load(review)
        self.assertEqual(result["conclusion"], "BLOCKED")
        self.assertTrue(any("image_delivery" in error for error in result["errors"]))

    def test_bare_pass_and_local_oracle_log_do_not_prove_delivery(self):
        review = self.review()
        review["image_delivery"] = {
            "status": "PASS", "evidence": ["local/oracle-success.log"], "notes": "local works"}
        result = self.load(review)
        self.assertEqual(result["conclusion"], "BLOCKED")

    def test_short_image_name_is_not_automatically_rejected(self):
        result = self.load(self.review())
        self.assertEqual(result["conclusion"], "PASS", result["errors"])
        self.assertIn("checks", result["items"]["image_delivery"])

    def test_other_image_evidence_cannot_grant_pass(self):
        result = self.load(self.review(), "registry.example.com/team/different:1")
        self.assertEqual(result["conclusion"], "BLOCKED")
        self.assertTrue(any("不一致" in error for error in result["errors"]))

    def test_no_recipient_access_or_target_evidence_blocks(self):
        baseline = self.review()
        for key in IMAGE_CHECKS:
            with self.subTest(key=key):
                review = copy.deepcopy(baseline)
                review["image_delivery"]["checks"][key]["evidence"] = []
                self.assertEqual(self.load(review)["conclusion"], "BLOCKED")

    def test_network_block_is_not_reported_as_package_fail(self):
        review = self.review()
        review["image_delivery"] = {
            "status": "BLOCKED", "evidence": ["image-delivery/network-failure.log"],
            "notes": "QC network unavailable; publication not established"}
        self.assertEqual(self.load(review)["conclusion"], "BLOCKED")

    def test_confirmed_delivery_failure_does_not_need_invented_success_fields(self):
        review = self.review()
        review["image_delivery"] = {
            "status": "FAIL", "evidence": ["image-delivery/not-found.log"],
            "notes": "Repository owner confirmed image does not exist"}
        self.assertEqual(self.load(review)["conclusion"], "FAIL")

    def test_target_and_resolved_remote_identity_are_required(self):
        for field in ("resolved_image_digest", "target_profile"):
            with self.subTest(field=field):
                review = self.review()
                del review["image_delivery"][field]
                self.assertEqual(self.load(review)["conclusion"], "BLOCKED")

    def test_legacy_eleven_gate_review_cannot_skip_new_system_and_tool_gates(self):
        review = self.review()
        del review["windows_image_policy"]
        del review["toolchain_in_image"]
        result = self.load(review)
        self.assertEqual(result["conclusion"], "BLOCKED")
        self.assertTrue(any("windows_image_policy" in error for error in result["errors"]))
        self.assertTrue(any("toolchain_in_image" in error for error in result["errors"]))

    def test_bare_pass_cannot_skip_actual_system_and_tool_metadata(self):
        for key in ("windows_image_policy", "toolchain_in_image"):
            with self.subTest(key=key):
                review = self.review()
                review[key] = {"status": "PASS", "evidence": ["fixture/summary.md"], "notes": "checked"}
                self.assertEqual(self.load(review)["conclusion"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
