import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from nested_virtualization_review import NESTED_CHECKS, validate_nested_virtualization
from run_delivery_qc import QUALITY_GATES, load_quality_review
from review_fixtures import passing_windows_image, passing_tools, passing_nested_virtualization
from image_delivery_review import IMAGE_CHECKS, image_review_template


IMAGE = "fixture.example/windows-server:2025"
IDENTITY = {"task_id": "demo", "task_version": "1.0.0", "task_hash": "a" * 64}


class NestedVirtualizationReviewTests(unittest.TestCase):
    def test_evidenced_nested_chain_schema_passes(self):
        self.assertFalse(validate_nested_virtualization(passing_nested_virtualization(IMAGE), IMAGE, IDENTITY))

    def test_physical_host_hyperv_or_single_guest_is_not_nested(self):
        for depth in (0, 1, True, None):
            with self.subTest(depth=depth):
                item = passing_nested_virtualization(IMAGE)
                item["virtualization_depth"] = depth
                self.assertTrue(validate_nested_virtualization(item, IMAGE, IDENTITY))

    def test_cpu_support_or_exposed_extensions_only_is_insufficient(self):
        for field in ("inner_virtualization_enabled", "task_runtime_in_nested_layer"):
            item = passing_nested_virtualization(IMAGE)
            item[field] = False
            self.assertTrue(validate_nested_virtualization(item, IMAGE, IDENTITY))

    def test_missing_topology_and_runtime_check_cannot_pass(self):
        for key in NESTED_CHECKS:
            with self.subTest(key=key):
                item = passing_nested_virtualization(IMAGE)
                del item["checks"][key]
                self.assertTrue(validate_nested_virtualization(item, IMAGE, IDENTITY))

    def test_only_hyperv_flag_and_local_oracle_log_cannot_grant_pass(self):
        item = {"status": "PASS", "evidence": ["fixture/local-oracle.log"],
                "notes": "Docker --isolation=hyperv works"}
        self.assertTrue(validate_nested_virtualization(item, IMAGE, IDENTITY))

    def test_different_image_or_old_task_cannot_grant_pass(self):
        for field in ("configured_image", "task_id", "task_version", "task_hash"):
            item = passing_nested_virtualization(IMAGE)
            item[field] = "b" * 64 if field == "task_hash" else "different"
            self.assertTrue(validate_nested_virtualization(item, IMAGE, IDENTITY))

    def test_fail_and_blocked_need_no_fabricated_success_metadata(self):
        for status in ("FAIL", "BLOCKED"):
            self.assertFalse(validate_nested_virtualization({"status": status}, IMAGE, IDENTITY))

    def review(self):
        review = {key: {"status": "PASS", "evidence": ["fixture/review.md"], "notes": "fixture"}
                  for key in QUALITY_GATES}
        image = image_review_template()
        image.update(status="PASS", evidence=["fixture/image-review.md"], configured_image=IMAGE,
                     resolved_image_digest="sha256:" + "b" * 64,
                     target_profile={"windows_build": "20348", "architecture": "amd64",
                                     "isolation": "hyperv", "can_build_images": False})
        image["checks"] = {key: {"status": "PASS", "evidence": ["fixture/image.log"], "notes": "fixture"}
                           for key in IMAGE_CHECKS}
        review["image_delivery"] = image
        review["windows_image_policy"] = passing_windows_image(IMAGE)
        review["toolchain_in_image"] = passing_tools()
        review["nested_virtualization"] = passing_nested_virtualization(IMAGE)
        return review

    def load(self, review):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "review.json"
            path.write_text(json.dumps(review), encoding="utf-8")
            return load_quality_review(path, IMAGE, IDENTITY)

    def test_old_thirteen_gate_review_is_blocked(self):
        review = self.review()
        del review["nested_virtualization"]
        result = self.load(review)
        self.assertEqual(result["conclusion"], "BLOCKED")
        self.assertTrue(any("nested_virtualization" in error for error in result["errors"]))

    def test_confirmed_non_nested_run_remains_fail(self):
        review = self.review()
        review["nested_virtualization"] = {
            "status": "FAIL", "evidence": ["fixture/physical-process-runtime.log"],
            "notes": "Confirmed runtime not nested"}
        self.assertEqual(self.load(review)["conclusion"], "FAIL")

    def test_unknown_outer_host_is_blocked_not_model_zero(self):
        review = self.review()
        review["nested_virtualization"] = {
            "status": "BLOCKED", "evidence": ["fixture/outer-host-unavailable.log"],
            "notes": "Cannot verify outer VM topology"}
        self.assertEqual(self.load(review)["conclusion"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
