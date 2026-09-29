import io
import json
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from review_fixture import case
from benchmark_evidence import docker_documents, resolve
from review_common import load_json, write_json


class TestBenchmarkEvidence(unittest.TestCase):
    def test_resolve_keeps_terminal_bench_versions_separate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path, config = case(root)
            proposal = load_json(path)
            first = resolve(proposal, root, config)
            proposal["benchmark"] = "terminal_bench4"
            second = resolve(proposal, root, config)
            self.assertIn("terminal_bench3", first["documents"][0]["text"])
            self.assertIn("terminal_bench4", second["documents"][0]["text"])
            self.assertNotEqual(first["documents"][0]["sha256"], second["documents"][0]["sha256"])
            proposal["related_question"] = "../dispatch"
            self.assertFalse(resolve(proposal, root, config)["documents"])

    def test_missing_programbench_image_does_not_use_metadata_as_prompt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task = root / "pb/tasks/tool__app.abcdef"
            task.mkdir(parents=True)
            (task / "task.yaml").write_text("repository: tool/app\n")
            config = root / "locations.json"
            write_json(config, {"benchmarks": {"programbench": {
                "root": "pb", "tasks": "tasks", "image": "programbench/{task_image}:task_cleanroom_v6"}}})
            with patch("benchmark_evidence.run", side_effect=ValueError("image unavailable")) as call:
                result = resolve({"benchmark": "programbench", "related_question": task.name}, root, config)
            self.assertEqual(result["documents"], [])
            self.assertEqual(result["container"]["image"], "programbench/tool_1776_app.abcdef:task_cleanroom_v6")
            self.assertIn("repository: tool/app", result["metadata"]["text"])
            self.assertTrue(call.called)

    def test_docker_documents_reads_stopped_container_and_cleans_up(self):
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w") as archive:
            info = tarfile.TarInfo("README.md")
            raw = b"Reimplement documented behavior of a reference binary."
            info.size = len(raw)
            archive.addfile(info, io.BytesIO(raw))
        calls = []

        def command(args, **kwargs):
            calls.append(args)
            if args[1:3] == ["image", "inspect"]:
                return json.dumps([{"Id": "sha256:fixture", "RepoDigests": ["repo@sha256:fixture"]}]).encode()
            if args[1] == "create":
                return b"stopped-container"
            if args[1] == "cp":
                return buffer.getvalue()
            if args[1] == "rm":
                return b"stopped-container"
            raise AssertionError(args)

        with patch("benchmark_evidence.run", side_effect=command):
            result = docker_documents("repo:fixture", ["/docs"])
        self.assertEqual(result["issues"], [])
        self.assertIn("reference binary", result["documents"][0]["text"])
        self.assertEqual(calls[-1], ["docker", "rm", "-v", "stopped-container"])
        self.assertFalse(any(c[1] in {"start", "run", "exec", "pull"} for c in calls))
