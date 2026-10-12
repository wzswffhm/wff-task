#!/usr/bin/env python3
"""Resolve exact benchmark prompts; inspect ProgramBench images without starting them."""
from __future__ import annotations

import argparse
import io
from pathlib import Path, PurePosixPath
import re
import tarfile

from review_common import digest, load_json, run, snapshot, write_json, MAX_FILE

DEFAULT_CONFIG = Path(__file__).resolve().parents[1] / "references/benchmark-locations.json"


def locations(workspace, config=DEFAULT_CONFIG):
    data = load_json(config)
    result = {}
    for key, value in data["benchmarks"].items():
        item = dict(value)
        item["root"] = str((Path(workspace) / item["root"]).resolve())
        item["tasks_root"] = str(Path(item["root"]) / item["tasks"])
        result[key] = item
    return result


def docker_documents(image, paths, pull=False):
    evidence = {"image": image, "documents": [], "issues": []}
    container = None
    try:
        if pull:
            run(["docker", "pull", image], timeout=300, max_bytes=MAX_FILE)
        info = __import__("json").loads(run(["docker", "image", "inspect", image]))[0]
        evidence.update(image_id=info["Id"], repo_digests=info.get("RepoDigests", []))
        if not paths:
            raise ValueError("ProgramBench document_paths not configured; locate real docs in image")
        # Creating a stopped container does not execute the image's entrypoint.
        container = run(["docker", "create", "--network", "none", "--entrypoint",
                         "/bin/true", info["Id"]]).decode().strip()
        for path in paths:
            if not path.startswith("/") or ".." in PurePosixPath(path).parts:
                evidence["issues"].append({"path": path, "reason": "invalid_container_path"})
                continue
            try:
                raw = run(["docker", "cp", container + ":" + path, "-"],
                          timeout=60, max_bytes=32 * MAX_FILE)
                with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
                    count = 0
                    for member in archive:
                        if member.isdir():
                            continue
                        count += 1
                        if count > 2000:
                            raise ValueError("document member limit")
                        if not member.isfile() or member.size > MAX_FILE:
                            evidence["issues"].append({"path": member.name,
                                                       "reason": "unsupported_or_large_document"})
                            continue
                        content = archive.extractfile(member).read(MAX_FILE + 1)
                        try:
                            text = content.decode("utf-8")
                        except UnicodeDecodeError:
                            evidence["issues"].append({"path": member.name,
                                                       "reason": "non_utf8_document"})
                            continue
                        evidence["documents"].append({
                            "path": "docker:" + info["Id"] + ":" + path + "!/" + member.name,
                            "sha256": digest(content), "bytes": len(content), "text": text})
            except (OSError, ValueError, tarfile.TarError) as error:
                evidence["issues"].append({"path": path, "reason": str(error)})
    except (OSError, ValueError, KeyError) as error:
        evidence["issues"].append({"path": image, "reason": str(error)})
    finally:
        if container:
            try:
                run(["docker", "rm", "-v", container])
            except (OSError, ValueError) as error:
                evidence["issues"].append({"path": container, "reason": "cleanup: " + str(error)})
    return evidence


def resolve(proposal, workspace, config=DEFAULT_CONFIG, pull=False, document_paths=None):
    benchmark, task = proposal.get("benchmark"), proposal.get("related_question")
    result = {"benchmark": benchmark, "related_question": task, "documents": [], "issues": []}
    loc = locations(workspace, config).get(benchmark)
    if loc is None or not isinstance(task, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+", task) or task in {".", ".."}:
        result["issues"].append({"path": str(task), "reason": "unresolved_benchmark_or_task"})
        return result
    root = Path(loc["tasks_root"])
    task_root = root / task
    result.update(repository_root=loc["root"], task_root=str(task_root))
    if task_root.is_symlink() or not task_root.is_dir():
        result["issues"].append({"path": str(task_root), "reason": "missing_task_or_symlink"})
        return result
    try:
        result["git_head"] = run(["git", "-C", loc["root"], "rev-parse", "HEAD"]).decode().strip()
    except (OSError, ValueError):
        result["git_head"] = None
    if benchmark == "programbench":
        try:
            result["metadata"] = snapshot(task_root / "task.yaml")
        except (OSError, ValueError, UnicodeError) as error:
            result["issues"].append({"path": str(task_root), "reason": str(error)})
        image = loc["image"].format(task_image=task.replace("__", "_1776_"), task=task)
        container = docker_documents(image, document_paths if document_paths is not None
                                     else loc.get("document_paths", []), pull)
        result["container"] = {k: v for k, v in container.items() if k != "documents"}
        result["documents"] = container["documents"]
        result["issues"].extend(container["issues"])
    else:
        try:
            result["documents"].append(snapshot(task_root / loc["instruction"]))
        except (OSError, ValueError, UnicodeError) as error:
            result["issues"].append({"path": str(task_root), "reason": str(error)})
    if not result["documents"] or not any(d["text"].strip() for d in result["documents"]):
        result["issues"].append({"path": str(task_root), "reason": "actual_prompt_unavailable"})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("proposal")
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--document-path", action="append")
    parser.add_argument("--pull", action="store_true", help="Explicitly allow Docker image downloads")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = resolve(load_json(args.proposal), args.workspace, args.config,
                     args.pull, args.document_path)
    write_json(args.output, report)
    print("documents=%d issues=%d" % (len(report["documents"]), len(report["issues"])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
