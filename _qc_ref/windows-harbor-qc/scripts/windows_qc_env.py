"""Project-local Harbor extension for static Windows container isolation.

Uses the supplier's Dockerfile unchanged. A no-network task is enforced by
Docker's null network, including every phase. Phase policy changes and sidecars
are rejected; this extension does not claim to support Windows allowlists.
"""
from __future__ import annotations
import asyncio
import base64
import hashlib
import json
import re
import tempfile
from pathlib import Path
from harbor.environments.docker.docker import DockerEnvironment
from harbor.models.task.config import NetworkMode
from harbor.constants import MAIN_SERVICE_NAME

def powershell_command(script):
    encoded = base64.b64encode(script.encode("utf-16le")).decode("ascii")
    return f"powershell.exe -NoLogo -NoProfile -NonInteractive -EncodedCommand {encoded}"


class WindowsQCEnvironment(DockerEnvironment):
    def __init__(self, *args, isolation="hyperv", qc_oracle_candidate=None, qc_oracle_reference=None, **kwargs):
        if isolation not in ("hyperv", "process"):
            raise ValueError("isolation must be hyperv or process")
        self._qc_isolation = isolation
        self._qc_oracle_candidate = qc_oracle_candidate
        self._qc_oracle_reference = qc_oracle_reference
        super().__init__(*args, **kwargs)
        if self._is_windows_container:
            # Windows host bind mounts do not honor in-container per-user ACLs.
            # Keep scoring assets on the container's own NTFS volume, and use
            # Harbor's non-mounted tar download path for logs/rewards instead.
            for mount in self._mounts:
                target = mount["target"].replace("/", "\\").casefold().rstrip("\\")
                if target not in ("c:\\logs\\agent", "c:\\logs\\verifier", "c:\\logs\\artifacts"):
                    raise ValueError("Windows QC requires explicit review of non-log host mounts")
            self._mounts = []

    @property
    def capabilities(self):
        result = super().capabilities
        if self._is_windows_container:
            return result.model_copy(update={"disable_internet": True, "mounted": False})
        return result

    def _resolve_user(self, user):
        # Harbor's generic artifact collector asks for root. Windows has no
        # such account; preserve that privileged request with its native name.
        if self._is_windows_container and user == "root":
            user = "ContainerAdministrator"
        return super()._resolve_user(user)

    def validate_network_policy_support(self, network_policy=None):
        policy = network_policy or self.network_policy
        if self._is_windows_container and policy.network_mode == NetworkMode.NO_NETWORK:
            if self.network_policy.network_mode != NetworkMode.NO_NETWORK:
                raise ValueError("Cannot change a Windows public network to no-network by phase")
            if self._uses_compose:
                raise ValueError("No-network Windows QC supports a single Dockerfile task only")
            return
        if self._is_windows_container and self.network_policy.network_mode == NetworkMode.NO_NETWORK:
            raise ValueError("Cannot relax a Windows no-network task by phase")
        return super().validate_network_policy_support(policy)

    def _write_env_compose_file(self):
        path = super()._write_env_compose_file()
        if self._is_windows_container:
            document = json.loads(path.read_text(encoding="utf-8"))
            main = document.setdefault("services", {}).setdefault(MAIN_SERVICE_NAME, {})
            main["isolation"] = self._qc_isolation
            if self.task_env_config.docker_image is None or self._qc_force_build:
                main["build"] = {"isolation": self._qc_isolation}
            if self.network_policy.network_mode == NetworkMode.NO_NETWORK:
                main["network_mode"] = "none"
            path.write_text(json.dumps(document), encoding="utf-8")
        return path

    async def _apply_network_policy(self, network_policy):
        if self._is_windows_container and self.network_policy.network_mode == NetworkMode.NO_NETWORK:
            self.validate_network_policy_support(network_policy)
            return
        return await super()._apply_network_policy(network_policy)

    def _path_kind_check_command(self, path, *, require_dir):
        if self._is_windows_container:
            path = path.replace("/", "\\")
            # Nano Server Go tasks have cmd/tar but no PowerShell. Standard
            # Harbor log paths do not need quotes, avoiding cmd/subprocess
            # double-quote escaping and any dependency on powershell.exe.
            if re.fullmatch(r"[A-Za-z]:\\[A-Za-z0-9_.\\-]+", path):
                directory = path.rstrip("\\") + "\\."
                if require_dir:
                    return f"if exist {directory} (exit /b 0) else (exit /b 1)"
                return f"if not exist {path} exit /b 1 & if exist {directory} exit /b 1 & exit /b 0"
            literal = path.replace("'", "''")
            kind = "Container" if require_dir else "Leaf"
            return powershell_command(f"if (Test-Path -LiteralPath '{literal}' -PathType {kind}) {{ exit 0 }} else {{ exit 1 }}")
        return super()._path_kind_check_command(path, require_dir=require_dir)

    async def exec(self, command, **kwargs):
        oracle = (self._is_windows_container and self._qc_oracle_candidate and
                  "c:\\solution\\solve." in command.replace("/", "\\").casefold())
        before = None
        if oracle:
            before = await self._oracle_hashes()
        result = await super().exec(command=command, **kwargs)
        if oracle:
            after = await self._oracle_hashes()
            proof = {"before": before, "after": after, "oracle_exit_code": result.return_code}
            path = self.trial_paths.agent_dir / "qc-oracle-application.json"
            path.write_text(json.dumps(proof, indent=2), encoding="utf-8")
        return result

    async def _oracle_hashes(self):
        values = {}
        for key, path in (("candidate", self._qc_oracle_candidate), ("reference", self._qc_oracle_reference)):
            if '"' in path or any(c in path for c in "\r\n%"):
                raise ValueError("Unsafe oracle evidence path")
            # Read exact bytes via Harbor's Windows tar transport, which works
            # on Nano Server without certutil or Windows PowerShell installed.
            with tempfile.TemporaryDirectory(prefix="wqc-oracle-") as directory:
                local = Path(directory) / "asset"
                await super().download_file(source_path=path, target_path=local)
                with local.open("rb") as stream:
                    values[key] = hashlib.file_digest(stream, "sha256").hexdigest()
        return values

    async def start(self, force_build):
        self._qc_force_build = force_build
        await super().start(force_build)
        if self._is_windows_container and self.network_policy.network_mode == NetworkMode.NO_NETWORK:
            proc = await asyncio.create_subprocess_exec(
                "docker", "inspect", self._windows_container_name,
                "--format", "{{.HostConfig.NetworkMode}}", stdout=asyncio.subprocess.PIPE)
            stdout, _ = await proc.communicate()
            if proc.returncode != 0 or stdout.strip() != b"none":
                raise RuntimeError("Windows container no-network enforcement not verified")
            self.logger.info("QC verified Docker NetworkMode=none for %s", self._windows_container_name)
        if self._is_windows_container:
            created = await self.exec(command=(
                "if not exist C:\\logs\\agent mkdir C:\\logs\\agent & "
                "if not exist C:\\logs\\verifier mkdir C:\\logs\\verifier & "
                "if not exist C:\\logs\\artifacts mkdir C:\\logs\\artifacts"))
            if created.return_code != 0:
                raise RuntimeError("Cannot create native Windows log directories")
            proc = await asyncio.create_subprocess_exec(
                "docker", "inspect", self._windows_container_name,
                "--format", "{{.Image}} {{.HostConfig.Isolation}} {{.HostConfig.NetworkMode}} {{len .Mounts}}",
                stdout=asyncio.subprocess.PIPE)
            stdout, _ = await proc.communicate()
            if proc.returncode != 0:
                raise RuntimeError("Cannot verify Windows container identity")
            self.logger.info("QC actual image/isolation/network/mount-count: %s", stdout.decode().strip())
            identity = await self.exec(command="ver & echo ARCH=%PROCESSOR_ARCHITECTURE%")
            self.logger.info("QC native Windows: %s", identity.stdout.strip())
