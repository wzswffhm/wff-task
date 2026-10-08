import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from run_qc import dynamic_gate, safe_extract, static_check


class PortableEntryPointTests(unittest.TestCase):
    def make_task(self, root: Path, *, hidden=False):
        (root / "environment").mkdir(parents=True)
        (root / "tests").mkdir()
        (root / "solution").mkdir()
        (root / "task.toml").write_text(
            'version = "1.0"\ndocker_image = "example/windows:20261001"\n\n[metadata]\ntask_id = "demo-001"\n',
            encoding="utf-8")
        (root / "source.json").write_text(json.dumps({
            "task_id": "demo-001", "source_type": "expert_constructed", "license": "internal",
            "lineage": "test", "authorization": "internal"}), encoding="utf-8")
        (root / "instruction.md").write_text("# Task\n", encoding="utf-8")
        for name in ("adapter.toml", "Dockerfile", "prepare.ps1", "validate_environment.ps1",
                     "run.ps1", "restore.ps1", "cleanup.ps1"):
            (root / "environment" / name).write_text("", encoding="utf-8")
        for name in ("test.ps1", "run_tests.ps1", "aggregate_results.ps1", "judge.toml"):
            (root / "tests" / name).write_text("", encoding="utf-8")
        (root / "tests" / "rubric.json").write_text(json.dumps({"task_id": "demo-001"}), encoding="utf-8")
        (root / "tests" / "required_testcases.json").write_text(json.dumps([
            {"id": "f2p-main", "group": "F2P"}, {"id": "p2p-regression", "group": "P2P"}
        ]), encoding="utf-8")
        (root / "solution" / "README.md").write_text("reference", encoding="utf-8")
        (root / "solution" / "solve.ps1").write_text("", encoding="utf-8")
        (root / "tests" / "judge.toml").write_text("", encoding="utf-8")
        if hidden:
            (root / "tests" / "test.bat").write_text("go test hidden_test.go", encoding="utf-8")

    def test_valid_shape_and_hidden_entrypoint_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "demo-001"
            self.make_task(root)
            report = static_check(root)
            self.assertTrue(report["static_pass"], report["errors"])

    def test_hidden_test_reference_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "demo-001"
            self.make_task(root, hidden=True)
            report = static_check(root)
            self.assertFalse(report["static_pass"])
            self.assertTrue(any("hidden test" in item for item in report["errors"]))

    def test_zip_path_traversal_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "bad.zip"
            with zipfile.ZipFile(archive, "w") as zf:
                zf.writestr("../escape.txt", "bad")
            with self.assertRaises(ValueError):
                safe_extract(archive, root / "out")

    def test_dynamic_gate_requires_oracle_one_nop_zero_p2p_and_f2p_failure(self):
        def run(agent, attempt, score, f2p, p2p="PASS"):
            return {"agent": agent, "attempt": attempt, "status": "VALID",
                    "formal_results": [{"validity": "VALID", "score": score, "cases": [
                        {"group": "F2P", "status": f2p}, {"group": "P2P", "status": p2p}]}]}
        runs = [run("oracle", i, 1, "PASS") for i in (1, 2, 3)]
        runs += [run("nop", i, 0, "FAIL") for i in (1, 2, 3)]
        self.assertTrue(dynamic_gate(runs, 3)["pass"])
        runs[-1]["formal_results"][0]["cases"][1]["status"] = "FAIL"
        self.assertFalse(dynamic_gate(runs, 3)["pass"])


if __name__ == "__main__":
    unittest.main()
