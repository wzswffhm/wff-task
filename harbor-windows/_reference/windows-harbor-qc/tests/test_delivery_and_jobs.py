import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from inspect_delivery import harbor_dirhash, inspect_delivery, task_hash
from validate_model_gate import evaluate
from validate_model_jobs import validate_jobs
from run_delivery_qc import QUALITY_GATES, execute
from image_delivery_review import IMAGE_CHECKS, image_review_template
from review_fixtures import passing_windows_image, passing_tools, passing_nested_virtualization


# 甲方 2026-10-15 放宽：交付只含 Qwen 与 Opus。
MODELS = (("qwen3.8-max-0902", "QWEN", "qwen", (0, 0, 0)),
          ("claude-opus-5", "OPUS", "opus", (1, 1, 0)))
REQUIRED_CASES = (
    ("f2p-core", "F2P"),
    ("f2p-edge-1", "F2P"),
    ("f2p-edge-2", "F2P"),
    ("p2p-regression-1", "P2P"),
    ("p2p-regression-2", "P2P"),
)


class DeliveryAndJobsTests(unittest.TestCase):
    def test_prohibited_dockerfile_is_rejected_by_both_entrypoints(self):
        from run_qc import static_check
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "delivery"
            root.mkdir()
            self.make_delivery(root)
            (root / "environment" / "Dockerfile").write_text(
                "FROM mcr.microsoft.com/windows/servercore:ltsc2025\n", encoding="utf-8")
            layout = inspect_delivery(root)
            self.assertFalse(layout["pass"])
            self.assertTrue(any("Server Core" in error for error in layout["errors"]))
            static = static_check(root)
            self.assertFalse(static["static_pass"])
            self.assertTrue(any("Server Core" in error for error in static["errors"]))

    def write_job(self, jobs: Path, name: str, checksum: str, *, kind: str,
                  score: int, alias: str | None = None, model_name: str | None = None):
        job = jobs / name
        (job / "agent").mkdir(parents=True)
        (job / "artifacts").mkdir()
        (job / "verifier").mkdir()
        agent = {"name": kind}
        metadata = None
        if kind == "model":
            agent = {"name": "model_bridge:ModelBridge", "kwargs": {"alias": alias}}
            metadata = {"alias": alias, "model": model_name}
        config = {"agent": agent, "trial_name": name}
        result = {
            "id": f"run-{name}", "task_name": "vendor/demo", "task_checksum": checksum,
            "exception_info": None, "config": {"agent": agent},
            "agent_result": {"metadata": metadata},
            "verifier_result": {"rewards": {"reward": score}},
        }
        cases = {
            case_id: ("FAIL" if not score and case_id == "f2p-core" else "PASS")
            for case_id, _ in REQUIRED_CASES
        }
        verifier = {
            "task_id": "demo", "task_version": "1.0.0", "status": "VALID", "score": score,
            "items": [{"test_id": case_id, "outcome": "PASSED" if value == "PASS" else "FAILED"}
                      for case_id, value in cases.items()],
        }
        (job / "config.json").write_text(json.dumps(config), encoding="utf-8")
        (job / "lock.json").write_text("{}", encoding="utf-8")
        (job / "result.json").write_text(json.dumps(result), encoding="utf-8")
        (job / "trial.log").write_text("complete", encoding="utf-8")
        (job / "artifacts" / "manifest.json").write_text("[]", encoding="utf-8")
        (job / "verifier" / "result.json").write_text(json.dumps(verifier), encoding="utf-8")
        (job / "verifier" / "reward.txt").write_text(str(score), encoding="utf-8")
        (job / "verifier" / "test-stdout.txt").write_text("complete", encoding="utf-8")
        (job / "verifier" / "verifier.log").write_text("complete", encoding="utf-8")
        if kind == "model":
            (job / "agent" / "model-result.json").write_text(json.dumps({
                "alias": alias, "model": model_name, "protocol": "anthropic",
                "runner_sha256": "a" * 64,
            }), encoding="utf-8")
            (job / "agent" / "trajectory.jsonl").write_text(
                json.dumps({"type": "user", "content": "请帮我把这个 Windows 程序的问题修好，并把现有测试跑通。"}, ensure_ascii=False) + "\n",
                encoding="utf-8")
        elif kind == "oracle":
            (job / "agent" / "oracle.txt").write_text("applied", encoding="utf-8")
            (job / "agent" / "qc-oracle-application.json").write_text(json.dumps({
                "oracle_exit_code": 0}), encoding="utf-8")
        return job

    def make_delivery(self, root: Path):
        jobs = root / "jobs"
        (root / "environment" / "workspace").mkdir(parents=True)
        (root / "tests").mkdir()
        (root / "solution").mkdir()
        jobs.mkdir()
        (root / "task.toml").write_text(
            'version = "1.0"\ndocker_image = "demo/windows:1.0.0"\n'
            '[metadata]\ntask_id = "demo"\n'
            '[task]\nname = "vendor/demo"\nid = "demo"\nversion = "1.0.0"\n'
            'instruction = "instruction.md"\nworkspace = "environment/workspace"\n'
            'setup = "environment/prepare.ps1"\ntest = "tests/test.ps1"\n'
            'golden = "solution/solve.ps1"\n', encoding="utf-8")
        (root / "instruction.md").write_text("请修复这个 Windows 程序。", encoding="utf-8")
        (root / "environment" / "adapter.toml").write_text(
            'prepare="prepare.ps1"\nvalidate="validate_environment.ps1"\nrun="run.ps1"\n'
            'restore="restore.ps1"\ncleanup="cleanup.ps1"\nworkspace="workspace"\n', encoding="utf-8")
        for name in ("Dockerfile", "prepare.ps1", "validate_environment.ps1", "run.ps1",
                     "restore.ps1", "cleanup.ps1"):
            (root / "environment" / name).write_text("", encoding="utf-8")
        (root / "tests" / "test.ps1").write_text("", encoding="utf-8")
        (root / "tests" / "run_tests.ps1").write_text("", encoding="utf-8")
        (root / "tests" / "aggregate_results.ps1").write_text("", encoding="utf-8")
        (root / "tests" / "judge.toml").write_text("", encoding="utf-8")
        (root / "tests" / "rubric.json").write_text(json.dumps({"task_id": "demo"}), encoding="utf-8")
        (root / "tests" / "required_testcases.json").write_text(json.dumps([
            {"id": case_id, "group": group} for case_id, group in REQUIRED_CASES
        ]), encoding="utf-8")
        (root / "solution" / "README.md").write_text("reference", encoding="utf-8")
        (root / "solution" / "solve.ps1").write_text("", encoding="utf-8")
        for name in ("config.json", "lock.json", "result.json"):
            (jobs / name).write_text("{}", encoding="utf-8")
        (jobs / "job.log").write_text("complete", encoding="utf-8")

        checksum = harbor_dirhash(root)
        for model_name, alias, _, scores in MODELS:
            for index, score in enumerate(scores, 1):
                self.write_job(jobs, f"model-{alias.lower()}-{index}", checksum,
                               kind="model", score=score, alias=alias, model_name=model_name)
        for index in range(1, 4):
            self.write_job(jobs, f"oracle-{index}", checksum, kind="oracle", score=1)
            self.write_job(jobs, f"nop-{index}", checksum, kind="nop", score=0)
        return {"task_id": "demo", "task_version": "1.0.0", "task_hash": task_hash(root),
                "harbor_task_checksum": checksum}

    def test_direct_layout_and_twelve_jobs_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "delivery"
            root.mkdir()
            self.make_delivery(root)
            layout = inspect_delivery(root)
            self.assertTrue(layout["pass"], layout["errors"])
            jobs = validate_jobs(root / "jobs", root, layout["task"])
            self.assertTrue(jobs["pass"], jobs["errors"])
            gate = evaluate(jobs["evidence"], layout["task"])
            self.assertTrue(gate["pass"], gate["errors"])

    def test_legacy_demo_wrapper_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "outside_harbor").mkdir()
            report = inspect_delivery(root)
            self.assertFalse(report["pass"])
            self.assertTrue(any("legacy Demo wrapper" in item for item in report["errors"]))

    def test_fewer_than_five_testcases_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "delivery"
            root.mkdir()
            self.make_delivery(root)
            manifest = root / "tests" / "required_testcases.json"
            manifest.write_text(json.dumps([
                {"id": f"case-{index}", "group": "F2P" if index < 2 else "P2P"}
                for index in range(4)
            ]), encoding="utf-8")
            report = inspect_delivery(root)
            self.assertFalse(report["pass"])
            self.assertTrue(any("at least 5" in item for item in report["errors"]))

    def test_more_than_twenty_seven_testcases_only_warns(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "delivery"
            root.mkdir()
            self.make_delivery(root)
            manifest = root / "tests" / "required_testcases.json"
            manifest.write_text(json.dumps([
                {"id": f"case-{index}", "group": "F2P" if index < 14 else "P2P"}
                for index in range(28)
            ]), encoding="utf-8")
            report = inspect_delivery(root)
            self.assertTrue(report["pass"], report["errors"])
            self.assertTrue(any("more than 27" in item for item in report["warnings"]))

    def test_extra_job_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "delivery"
            root.mkdir()
            self.make_delivery(root)
            shutil.copytree(root / "jobs" / "model-qwen-1", root / "jobs" / "extra-qwen")
            layout = inspect_delivery(root)
            jobs = validate_jobs(root / "jobs", root, layout["task"])
            self.assertFalse(jobs["pass"])

    def test_combined_entrypoint_merges_all_gates(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            delivery = workspace / "delivery"
            delivery.mkdir()
            self.make_delivery(delivery)
            out = workspace / "qc"

            def fake_harbor(args):
                args.out.mkdir(parents=True)
                (args.out / "report.json").write_text(json.dumps({
                    "conclusion": "PASS", "tasks": [], "runs": []}), encoding="utf-8")
                return 0

            review = workspace / "quality-review.json"
            review_data = {
                key: {"status": "PASS", "evidence": [f"evidence/{key}.md"], "notes": "checked"}
                for key in QUALITY_GATES
            }
            image_review = image_review_template()
            image_review.update(status="PASS", evidence=["image-delivery/review.md"],
                                configured_image="demo/windows:1.0.0",
                                resolved_image_digest="sha256:" + "a" * 64,
                                target_profile={"windows_build": "20348", "architecture": "amd64",
                                                "isolation": "process", "can_build_images": False})
            image_review["checks"] = {
                key: {"status": "PASS", "evidence": [f"image-delivery/{key}.log"], "notes": "fixture"}
                for key in IMAGE_CHECKS
            }
            review_data["image_delivery"] = image_review
            review_data["windows_image_policy"] = passing_windows_image("demo/windows:1.0.0")
            review_data["toolchain_in_image"] = passing_tools()
            review_data["nested_virtualization"] = passing_nested_virtualization(
                "demo/windows:1.0.0", inspect_delivery(delivery)["task"])
            review.write_text(json.dumps(review_data), encoding="utf-8")
            args = SimpleNamespace(input=delivery, out=out, attempts=3,
                                   environment=None, force_build=False,
                                   quality_review=review)
            with patch("run_delivery_qc.run_harbor_qc", side_effect=fake_harbor):
                code = execute(args)
            self.assertEqual(code, 0)
            report = json.loads((out / "report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["conclusion"], "PASS")

    def test_missing_quality_review_blocks_final_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            delivery = workspace / "delivery"
            delivery.mkdir()
            self.make_delivery(delivery)
            out = workspace / "qc"

            def fake_harbor(args):
                args.out.mkdir(parents=True)
                (args.out / "report.json").write_text(json.dumps({
                    "conclusion": "PASS", "tasks": [], "runs": []}), encoding="utf-8")
                return 0

            args = SimpleNamespace(input=delivery, out=out, attempts=3,
                                   environment=None, force_build=False,
                                   quality_review=None)
            with patch("run_delivery_qc.run_harbor_qc", side_effect=fake_harbor):
                code = execute(args)
            self.assertEqual(code, 2)
            report = json.loads((out / "report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["automated_conclusion"], "PASS")
            self.assertEqual(report["quality_review"]["conclusion"], "BLOCKED")
            self.assertEqual(report["conclusion"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
