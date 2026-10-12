import json
import hashlib
import base64
import asyncio
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, AsyncMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
try:
    from windows_qc_env import WindowsQCEnvironment, DockerEnvironment, NetworkMode, powershell_command
    from harbor.models.task.config import NetworkPolicy
except ImportError:
    WindowsQCEnvironment = None


@unittest.skipIf(WindowsQCEnvironment is None, "Run with installed Harbor Python to test adapter")
class WindowsAdapterTests(unittest.TestCase):
    def environment(self):
        obj = object.__new__(WindowsQCEnvironment)
        obj._is_windows_container = True
        obj._network_policy = NetworkPolicy(network_mode=NetworkMode.NO_NETWORK)
        obj._environment_dir = Path("no-sidecars")
        obj.extra_docker_compose_paths = []
        obj._qc_isolation = "hyperv"
        obj._qc_force_build = False
        obj.task_env_config = SimpleNamespace(docker_image=None)
        return obj

    def test_no_network_overlay_enforces_null_network_and_hyperv(self):
        obj = self.environment()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "override.json"
            path.write_text('{"services":{"main":{"environment":{"X":"Y"}}}}')
            with patch.object(DockerEnvironment, "_write_env_compose_file", return_value=path):
                obj._write_env_compose_file()
            main = json.loads(path.read_text())["services"]["main"]
            self.assertEqual(main["network_mode"], "none")
            self.assertEqual(main["isolation"], "hyperv")
            self.assertEqual(main["build"]["isolation"], "hyperv")
            self.assertEqual(main["environment"]["X"], "Y")

    def test_no_network_cannot_be_relaxed_in_another_phase(self):
        obj = self.environment()
        with self.assertRaises(ValueError):
            obj.validate_network_policy_support(NetworkPolicy(network_mode=NetworkMode.PUBLIC))

    def test_public_cannot_claim_phase_network_isolation(self):
        obj = self.environment()
        obj._network_policy = NetworkPolicy(network_mode=NetworkMode.PUBLIC)
        with self.assertRaises(ValueError):
            obj.validate_network_policy_support(NetworkPolicy(network_mode=NetworkMode.NO_NETWORK))

    def test_directory_and_file_checks_handle_native_paths_and_quotes(self):
        obj = self.environment()
        for require_dir, kind in ((True, "Container"), (False, "Leaf")):
            command = obj._path_kind_check_command("C:/logs/a b's", require_dir=require_dir)
            script = base64.b64decode(command.split()[-1]).decode("utf-16le")
            self.assertIn("-LiteralPath 'C:\\logs\\a b''s'", script)
            self.assertIn("-PathType " + kind, script)

    def test_nano_log_path_checks_do_not_require_powershell(self):
        obj = self.environment()
        command = obj._path_kind_check_command("C:/logs/verifier", require_dir=True)
        self.assertNotIn("powershell", command)
        self.assertIn("C:\\logs\\verifier\\.", command)

    def test_root_artifact_user_maps_only_on_windows(self):
        obj = self.environment()
        obj.default_user = "BenchAgent"
        self.assertEqual(obj._resolve_user("root"), "ContainerAdministrator")
        self.assertEqual(obj._resolve_user(None), "BenchAgent")
        self.assertEqual(obj._resolve_user("CustomUser"), "CustomUser")
        obj._is_windows_container = False
        self.assertEqual(obj._resolve_user("root"), "root")

    def test_hash_evidence_reads_exact_bytes_without_runtime_dependency(self):
        obj = self.environment()
        obj._qc_oracle_candidate = "C:/testbed/src/Publisher.cs"
        obj._qc_oracle_reference = "C:/solution/Publisher.cs"
        data = b"source\r\n"
        digest = hashlib.sha256(data).hexdigest()
        async def download(**kwargs):
            Path(kwargs["target_path"]).write_bytes(data)
        mock = AsyncMock(side_effect=download)
        with patch.object(DockerEnvironment, "download_file", mock):
            result = asyncio.run(obj._oracle_hashes())
        self.assertEqual(result, {"candidate": digest, "reference": digest})
        self.assertEqual(mock.await_count, 2)
        for call in mock.await_args_list:
            self.assertIn(call.kwargs["source_path"], (obj._qc_oracle_candidate, obj._qc_oracle_reference))

    def test_failed_hash_collection_cannot_create_pass_evidence(self):
        obj = self.environment()
        obj._qc_oracle_candidate = "C:/missing.cs"
        obj._qc_oracle_reference = "C:/solution/ref.cs"
        mock = AsyncMock(side_effect=RuntimeError("missing"))
        with patch.object(DockerEnvironment, "download_file", mock), self.assertRaises(RuntimeError):
            asyncio.run(obj._oracle_hashes())


if __name__ == "__main__":
    unittest.main()
