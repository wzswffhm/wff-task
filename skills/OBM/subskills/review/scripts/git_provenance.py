#!/usr/bin/env python3
"""Search public repository history for A/B proposal deltas; never infer originality."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

from review_common import canonical, digest, load_json, run, snapshot, write_json


def repo_url(value):
    """Canonical repository locator; strip auth, query, fragment and commit/PR suffix."""
    value = value.strip()
    if value.startswith("git@"):
        value = "https://" + value[4:].replace(":", "/", 1)
    elif "://" not in value:
        value = "https://" + value
    parsed = urlsplit(value)
    if not parsed.hostname:
        raise ValueError("invalid repository URL")
    parts = [p for p in parsed.path.split("/") if p]
    for marker in ("commit", "commits", "pull", "pulls", "tree", "blob", "-"):
        if marker in parts:
            parts = parts[:parts.index(marker)]
            break
    if parsed.hostname.lower() == "github.com":
        parts = parts[:2]
    if len(parts) < 2:
        raise ValueError("repository path requires owner and name")
    parts[-1] = re.sub(r"\.git$", "", parts[-1])
    return "https://" + parsed.hostname.lower() + "/" + "/".join(parts)


def extract_repositories(text):
    found = set()
    for url in re.findall(r"(?:https?://|git@)[^\s<>\"'，。；）)]+", text):
        try:
            parsed = urlsplit(url if "://" in url else "ssh://" + url.replace(":", "/", 1))
            # Generic webpages are not automatically asserted to be git repos.
            if parsed.hostname in {"github.com", "gitlab.com", "bitbucket.org"} or ".git" in url:
                found.add(repo_url(url.rstrip(".,;")))
        except ValueError:
            pass
    return sorted(found)


def github_get(url):
    request = Request(url, headers={"Accept": "application/vnd.github+json",
                                   "User-Agent": "OBM-content-review/6"})
    with urlopen(request, timeout=20) as response:
        raw = response.read(8 * 1024 * 1024 + 1)
        if len(raw) > 8 * 1024 * 1024:
            raise ValueError("HTTP response byte limit")
        return json.loads(raw), {"url": url, "sha256": digest(raw),
                                 "rate_remaining": response.headers.get("X-RateLimit-Remaining"),
                                 "link": response.headers.get("Link")}


def local_search(url, local, queries, limit):
    evidence = {"repository": url, "method": "local_git", "queries": queries,
                "candidates": [], "issues": []}
    try:
        def git(*args):
            return run(["git", "-C", str(local), *args], max_bytes=2 * 1024 * 1024).decode("utf-8", "replace")
        origin = git("remote", "get-url", "origin").strip()
        if repo_url(origin).casefold() != url.casefold():
            raise ValueError("local origin does not match declared repository")
        evidence["shallow"] = git("rev-parse", "--is-shallow-repository").strip() == "true"
        evidence["refs"] = git("for-each-ref", "--format=%(refname) %(objectname)").splitlines()
        evidence["git_head"] = git("rev-parse", "HEAD").strip()
        if evidence["shallow"]:
            evidence["issues"].append("shallow_history")
        shas = set()
        for query in queries:
            for search in (["--fixed-strings", "--regexp-ignore-case", "--grep=" + query],
                           ["-G" + re.escape(query)]):
                rows = git("log", "--all", "--format=%H", "-n", str(limit + 1),
                           *search, "--").splitlines()
                if len(rows) > limit:
                    evidence["issues"].append("local_result_limit: " + query)
                shas.update(rows[:limit])
        if len(shas) > limit:
            evidence["issues"].append("local_candidate_limit")
        for sha in sorted(shas)[:limit]:
            try:
                patch = git("show", "--format=fuller", "--no-ext-diff", "--no-textconv", sha, "--")
                candidate = {"repository": url, "kind": "commit", "sha": sha,
                             "url": url + "/commit/" + sha, "text": patch,
                             "committed_at": git("show", "-s", "--format=%cI", sha).strip(),
                             "public_verified": False, "origin": "local_git"}
                candidate["candidate_id"] = digest(canonical(candidate))
                evidence["candidates"].append(candidate)
            except (OSError, ValueError) as error:
                evidence["issues"].append("commit " + sha + ": " + str(error))
        evidence["issues"].append("local_refs_do_not_establish_publication_or_cover_all_PRs")
    except (OSError, ValueError) as error:
        evidence["issues"].append(str(error))
    return evidence


def public_search(url, queries, pages=2, limit=20, explicit=None):
    report = {"repository": url, "method": "github_public_api", "requests": [],
              "candidates": [], "issues": [], "queries": queries}
    if urlsplit(url).hostname != "github.com":
        report["issues"].append("non_github_requires_external_history_evidence")
        return report
    repo = urlsplit(url).path.strip("/")
    targets = set(explicit or [])
    for query in queries:
        for kind, endpoint, suffix in (("commit", "commits", ""),
                                       ("pr", "issues", " is:pr")):
            for page in range(1, pages + 1):
                search_url = "https://api.github.com/search/" + endpoint + "?" + urlencode({
                    "q": "repo:" + repo + " " + query + suffix, "per_page": 30, "page": page})
                try:
                    data, request = github_get(search_url)
                    report["requests"].append(request)
                    if data.get("incomplete_results"):
                        report["issues"].append("incomplete_search_results")
                    for item in data.get("items", []):
                        targets.add((kind, item["sha"] if kind == "commit" else str(item["number"])))
                    if data.get("total_count", 0) <= page * 30:
                        break
                    if page == pages:
                        report["issues"].append("search_pagination_limit: " + query)
                except (OSError, ValueError, KeyError) as error:
                    report["issues"].append("search_failed: " + str(error))
                    break
    if len(targets) > limit:
        report["issues"].append("public_candidate_limit")
    for kind, ident in sorted(targets)[:limit]:
        api_url = "https://api.github.com/repos/" + repo + ("/commits/" if kind == "commit" else "/pulls/") + ident
        try:
            data, request = github_get(api_url)
            report["requests"].append(request)
            if kind == "pr":
                sha = data["head"]["sha"]
                commit, commit_request = github_get("https://api.github.com/repos/" + repo + "/commits/" + sha)
                report["requests"].append(commit_request)
                # Compare PR base..head, not just the last commit.
                diff, diff_request = github_get("https://api.github.com/repos/" + repo +
                                               "/compare/" + data["base"]["sha"] + "..." + sha)
                report["requests"].append(diff_request)
                title = str(data.get("title", "")) + "\n" + str(data.get("body") or "")
                date = data.get("created_at")
            else:
                sha, commit, diff = data["sha"], data, data
                title = data["commit"]["message"]
                date = data["commit"]["committer"]["date"]
            files = diff.get("files", [])
            patches_complete = all("patch" in item for item in files) and len(files) < 300
            if not patches_complete:
                report["issues"].append("missing_or_truncated_diff: " + ident)
            candidate = {"repository": url, "kind": kind, "sha": sha,
                         "url": data["html_url"], "public_verified": True,
                         "published_at": date, "publication_time_note":
                         "PR created_at is public event metadata; commit date alone is not proof of first publication",
                         "text": title + "\n\n" + "\n\n".join(
                             item["filename"] + "\n" + item.get("patch", "[patch unavailable]") for item in files),
                         "diff_complete": patches_complete, "origin": "github_public_api",
                         "request": request}
            candidate["candidate_id"] = digest(canonical(candidate))
            report["candidates"].append(candidate)
        except (OSError, ValueError, KeyError) as error:
            report["issues"].append("candidate_fetch_failed: " + str(error))
    return report


def search(proposal, queries=None, mappings=None, repositories=None, public=False,
           pages=2, limit=20):
    queries = list(dict.fromkeys(q.strip() for q in (queries or []) if q.strip()))
    mappings = mappings or {}
    text = proposal.get("proposal_sources", "")
    repos = sorted(set(extract_repositories(text)) | {repo_url(r) for r in (repositories or [])})
    result = {"schema_version": 1, "searched_at": datetime.now(timezone.utc).isoformat(),
              "proposal_sha256": digest(canonical(proposal)), "repositories": repos,
              "queries": queries, "searches": [], "candidates": [], "issues": [],
              "decision": "REQUIRES_ANALYST",
              "scope_note": "Search coverage is bounded; no hits do not prove originality."}
    if not queries:
        result["issues"].append("no_analyst_derived_queries")
    if not repos:
        result["issues"].append("no_repository_resolved_from_sources; analyst must verify applicability")
    for repo in repos:
        local = mappings.get(repo)
        searches = []
        if local:
            searches.append(local_search(repo, local, queries, limit))
        if public:
            explicit = []
            for kind, ident in re.findall(re.escape(repo) + r"/(commit|pull)/([A-Za-z0-9]+)", text):
                explicit.append(("pr" if kind == "pull" else kind, ident))
            searches.append(public_search(repo, queries, pages, limit, explicit))
        if not searches:
            result["issues"].append("repository_not_searched: " + repo)
        for item in searches:
            result["searches"].append(item)
            result["candidates"].extend(item["candidates"])
            result["issues"].extend(repo + ": " + str(i) for i in item["issues"])
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("proposal")
    parser.add_argument("--query", action="append", default=[])
    parser.add_argument("--repo", action="append", default=[])
    parser.add_argument("--repo-map", help="JSON object canonical URL -> local checkout")
    parser.add_argument("--public", action="store_true", help="Query public GitHub commits and PRs")
    parser.add_argument("--pages", type=int, default=2)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if args.pages < 1 or args.limit < 1:
        parser.error("pages and limit must be positive")
    result = search(load_json(args.proposal), args.query,
                    load_json(args.repo_map) if args.repo_map else {}, args.repo,
                    args.public, args.pages, args.limit)
    write_json(args.output, result)
    print("repositories=%d candidates=%d issues=%d" %
          (len(result["repositories"]), len(result["candidates"]), len(result["issues"])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
