#!/usr/bin/env python3
"""Recall existing benchmark tasks and proposals similar to a candidate scene.

This script scans all available documents and ranks likely overlaps. It is a
recall aid, not a semantic duplicate detector; the final decision must follow
references/scene-dedup.md.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "by", "can",
    "for", "from", "has", "have", "if", "in", "into", "is", "it",
    "must", "of", "on", "or", "should", "that", "the", "their", "then",
    "this", "to", "using", "when", "where", "which", "with", "without",
}


@dataclass
class Document:
    source_type: str
    source_id: str
    title: str
    text: str
    repo: str = ""
    path: str = ""


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def text_values(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        if value.strip():
            yield value.strip()
    elif isinstance(value, dict):
        for child in value.values():
            yield from text_values(child)
    elif isinstance(value, list):
        for child in value:
            yield from text_values(child)


def find_named_string(value: Any, names: set[str]) -> str:
    if isinstance(value, dict):
        for key, child in value.items():
            if key.lower() in names and isinstance(child, str) and child.strip():
                return child.strip()
        for child in value.values():
            found = find_named_string(child, names)
            if found:
                return found
    elif isinstance(value, list):
        for child in value:
            found = find_named_string(child, names)
            if found:
                return found
    return ""


def tokenize(text: str) -> list[str]:
    raw = re.findall(r"[A-Za-z][A-Za-z0-9_+.-]*|[\u4e00-\u9fff]+|\d+", text.lower())
    tokens: list[str] = []
    for token in raw:
        if re.fullmatch(r"[\u4e00-\u9fff]+", token):
            if len(token) == 1:
                tokens.append(token)
            else:
                tokens.extend(token[i : i + 2] for i in range(len(token) - 1))
            continue
        token = token.strip("._+-")
        if len(token) > 1 and token not in STOPWORDS:
            tokens.append(token)
    return tokens


def features(text: str) -> Counter[str]:
    tokens = tokenize(text)
    counts: Counter[str] = Counter(tokens)
    for left, right in zip(tokens, tokens[1:]):
        counts[f"__bg__{left}:{right}"] += 1
    return counts


def cosine(left: Counter[str], right: Counter[str], idf: dict[str, float]) -> float:
    shared = left.keys() & right.keys()
    numerator = sum(left[key] * right[key] * idf[key] ** 2 for key in shared)
    left_norm = math.sqrt(sum((count * idf[key]) ** 2 for key, count in left.items()))
    right_norm = math.sqrt(sum((count * idf[key]) ** 2 for key, count in right.items()))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return numerator / (left_norm * right_norm)


def load_candidate(path: Path) -> tuple[Any, str, str, str]:
    raw = path.read_text(encoding="utf-8")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        data = raw
    text = "\n".join(text_values(data)) if not isinstance(data, str) else data
    title = find_named_string(
        data,
        {"candidate_title", "title", "name", "a_modification_idea"},
    )
    repo = find_named_string(
        data,
        {"upstream_repo", "repo", "repository", "repository_url"},
    )
    return data, text, title or path.stem, normalize_repo(repo)


def normalize_repo(repo: str) -> str:
    value = repo.strip().lower().removesuffix(".git").rstrip("/")
    value = re.sub(r"^https?://github\.com/", "", value)
    return value


def benchmark_documents(root: Path) -> list[Document]:
    manifest_path = root / "manifest.json"
    metadata: dict[str, dict[str, Any]] = {}
    if manifest_path.is_file():
        manifest = read_json(manifest_path)
        records = manifest if isinstance(manifest, list) else manifest.get("tasks", [])
        for record in records:
            if isinstance(record, dict) and record.get("task_id"):
                metadata[str(record["task_id"])] = record

    documents: list[Document] = []
    for instruction in sorted(root.glob("*/instruction.md")):
        task_id = instruction.parent.name
        record = metadata.get(task_id, {})
        title = str(record.get("display_title") or record.get("original_title") or task_id)
        meta_text = "\n".join(
            str(record.get(key, ""))
            for key in (
                "display_title", "display_description", "original_title",
                "category", "language", "repo",
            )
            if record.get(key)
        )
        documents.append(
            Document(
                source_type="benchmark",
                source_id=task_id,
                title=title,
                text=meta_text + "\n" + instruction.read_text(encoding="utf-8"),
                repo=normalize_repo(str(record.get("repo", ""))),
                path=str(instruction),
            )
        )
    return documents


def is_below(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def proposal_documents(project_root: Path, benchmark_root: Path, candidate: Path) -> list[Document]:
    documents: list[Document] = []
    candidate_resolved = candidate.resolve()
    for path in sorted(project_root.rglob("proposal.json")):
        if path.resolve() == candidate_resolved or is_below(path, benchmark_root):
            continue
        try:
            data = read_json(path)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        benchmark = str(data.get("benchmark", ""))
        if benchmark and benchmark.lower() != "deepswe":
            continue
        body = data.get("proposal", {})
        text = "\n".join(text_values(body))
        if not text:
            continue
        idea = body.get("A_modification_idea", "") if isinstance(body, dict) else ""
        source_id = path.parent.name
        documents.append(
            Document(
                source_type="proposal",
                source_id=source_id,
                title=str(idea or source_id),
                text=text + "\n" + str(data.get("proposal_scene", "")) + "\n" + str(data.get("proposal_verify", "")),
                repo=normalize_repo(find_named_string(data, {"upstream_repo", "repo", "repository", "repository_url"})),
                path=str(path),
            )
        )
    return documents


def registry_documents(project_root: Path) -> list[Document]:
    registry_path = project_root / "work" / "task-registry.json"
    if not registry_path.is_file():
        return []
    try:
        data = read_json(registry_path)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return []
    entries = data.get("entries", []) if isinstance(data, dict) else []
    documents: list[Document] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        if entry.get("status") not in {"reserved", "candidate"}:
            continue
        if str(entry.get("benchmark", "")).lower() != "deepswe":
            continue
        text = "\n".join(
            str(entry.get(key, ""))
            for key in ("scene_summary", "capability_type", "slug", "reference_tasks")
            if entry.get(key)
        )
        if not text.strip():
            continue
        proposal_name = str(entry.get("proposal_name") or entry.get("reservation_id") or "registry-entry")
        documents.append(
            Document(
                source_type="registry",
                source_id=proposal_name,
                title=str(entry.get("scene_summary") or proposal_name),
                text=text,
                repo=normalize_repo(str(entry.get("repository", ""))),
                path=str(registry_path),
            )
        )
    return documents


def language_warning(text: str) -> str:
    nonspace = [char for char in text if not char.isspace()]
    if not nonspace:
        return "Candidate profile is empty."
    cjk = sum("\u4e00" <= char <= "\u9fff" for char in nonspace)
    if cjk / len(nonspace) > 0.15:
        return (
            "Candidate profile contains substantial Chinese text. DeepSWE source tasks are "
            "English; add a concise English scene description before relying on recall."
        )
    return ""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--benchmark-root", type=Path, required=True)
    parser.add_argument("--project-root", type=Path)
    parser.add_argument("--top", type=int, default=20, help="0 prints every result")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()

    if not args.candidate.is_file():
        parser.error(f"candidate file not found: {args.candidate}")
    if not args.benchmark_root.is_dir():
        parser.error(f"benchmark root not found: {args.benchmark_root}")
    if args.top < 0:
        parser.error("--top must be 0 or a positive integer")

    _, candidate_text, candidate_title, candidate_repo = load_candidate(args.candidate)
    documents = benchmark_documents(args.benchmark_root)
    benchmark_count = len(documents)
    proposal_count = 0
    registry_count = 0
    if args.project_root:
        if not args.project_root.is_dir():
            parser.error(f"project root not found: {args.project_root}")
        proposals = proposal_documents(args.project_root, args.benchmark_root, args.candidate)
        registry = registry_documents(args.project_root)
        documents.extend(proposals)
        documents.extend(registry)
        proposal_count = len(proposals)
        registry_count = len(registry)
    if not documents:
        parser.error("no benchmark instructions or proposals were found")

    candidate_features = features(candidate_text)
    document_features = [features(document.text) for document in documents]
    all_features = document_features + [candidate_features]
    document_frequency: Counter[str] = Counter()
    for item in all_features:
        document_frequency.update(item.keys())
    population = len(all_features)
    idf = {
        key: math.log((population + 1) / (frequency + 1)) + 1
        for key, frequency in document_frequency.items()
    }

    results: list[dict[str, Any]] = []
    for document, doc_features in zip(documents, document_features):
        same_repo = bool(candidate_repo and document.repo and candidate_repo == document.repo)
        results.append(
            {
                "score": round(cosine(candidate_features, doc_features, idf), 6),
                "same_repo": same_repo,
                "source_type": document.source_type,
                "source_id": document.source_id,
                "title": document.title,
                "repo": document.repo,
                "path": document.path,
            }
        )
    results.sort(key=lambda item: (item["score"], item["same_repo"]), reverse=True)

    selected = results if args.top == 0 else results[: args.top]
    selected_ids = {(item["source_type"], item["source_id"], item["path"]) for item in selected}
    for item in results:
        identity = (item["source_type"], item["source_id"], item["path"])
        if item["same_repo"] and identity not in selected_ids:
            selected.append(item)
            selected_ids.add(identity)

    fingerprint = hashlib.sha256("\n".join(tokenize(candidate_text)).encode()).hexdigest()
    warning = language_warning(candidate_text)
    output = {
        "candidate": str(args.candidate),
        "candidate_title": candidate_title,
        "candidate_repo": candidate_repo,
        "candidate_fingerprint": fingerprint,
        "benchmark_documents_scanned": benchmark_count,
        "proposal_documents_scanned": proposal_count,
        "registry_documents_scanned": registry_count,
        "warning": warning,
        "results": selected,
        "notice": "Recall only. Apply references/scene-dedup.md for the semantic decision.",
    }

    if args.as_json:
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 0

    print("# Scene overlap candidates")
    print()
    print(f"Candidate: {candidate_title}")
    print(f"Fingerprint: {fingerprint}")
    print(
        f"Scanned: {benchmark_count} benchmark tasks, {proposal_count} local proposals, "
        f"{registry_count} active registry entries"
    )
    if candidate_repo:
        print(f"Repository: {candidate_repo}")
    if warning:
        print(f"Warning: {warning}")
    print()
    print("| Rank | Score | Same repo | Source | Title |")
    print("| ---: | ---: | :---: | --- | --- |")
    for index, item in enumerate(selected, 1):
        title = str(item["title"]).replace("|", "\\|").replace("\n", " ")
        source = f"{item['source_type']}:{item['source_id']}"
        print(
            f"| {index} | {item['score']:.4f} | "
            f"{'yes' if item['same_repo'] else 'no'} | {source} | {title} |"
        )
    print()
    print("Recall only. Review these tasks, active registry entries, all same-repository tasks, and semantic peers using references/scene-dedup.md.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
