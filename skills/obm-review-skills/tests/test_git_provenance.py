import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import review_fixture
from git_provenance import local_search, public_search, repo_url, search


class TestGitProvenance(unittest.TestCase):
    def test_repo_url_normalizes_and_removes_credentials(self):
        self.assertEqual(repo_url("git@github.com:owner/repo.git"), "https://github.com/owner/repo")
        self.assertEqual(repo_url("https://name:secret@github.com/owner/repo/commit/abc?q=secret"),
                         "https://github.com/owner/repo")
        self.assertEqual(repo_url("https://gitlab.com/group/sub/repo/-/merge_requests/1"),
                         "https://gitlab.com/group/sub/repo")

    def test_empty_or_unsearched_history_is_not_originality_proof(self):
        result = search({"proposal_sources": "https://github.com/a/b https://github.com/c/d"},
                        ["new feature"])
        self.assertEqual(len(result["repositories"]), 2)
        self.assertEqual(len(result["issues"]), 2)
        self.assertEqual(result["decision"], "REQUIRES_ANALYST")
        self.assertIn("no_analyst_derived_queries", search({"proposal_sources": ""})["issues"])

    def test_local_history_finds_actual_patch_without_claiming_publication(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            def git(*args):
                return subprocess.run(["git", "-C", tmp, *args], check=True, capture_output=True)
            git("init")
            git("config", "user.name", "Review Test")
            git("config", "user.email", "test@example.invalid")
            git("remote", "add", "origin", "https://github.com/example/dispatch.git")
            (root / "app.py").write_text("def repair_closure():\n    return 'frozen route'\n")
            git("add", "app.py")
            git("commit", "-m", "Add closure repair")
            result = local_search("https://github.com/example/dispatch", root, ["closure"], 10)
            self.assertEqual(len(result["candidates"]), 1)
            candidate = result["candidates"][0]
            self.assertIn("+def repair_closure", candidate["text"])
            self.assertEqual(len(candidate["sha"]), 40)
            self.assertFalse(candidate["public_verified"])
            self.assertTrue(result["refs"])
            self.assertIn("local_refs_do_not_establish_publication_or_cover_all_PRs", result["issues"])

    def test_public_search_records_commit_diff_and_pagination_gap(self):
        sha = "a" * 40
        calls = []
        def fetch(url):
            calls.append(url)
            if "/search/commits?" in url:
                data = {"total_count": 70, "incomplete_results": False, "items": [{"sha": sha}]}
            elif "/search/issues?" in url:
                data = {"total_count": 0, "items": []}
            else:
                data = {"sha": sha, "html_url": "https://github.com/example/dispatch/commit/" + sha,
                        "commit": {"message": "Closure repair", "committer": {"date": "2025-01-01T00:00:00Z"}},
                        "files": [{"filename": "app.py", "patch": "+repair_closure()"}]}
            return data, {"url": url, "sha256": "fixture"}
        with patch("git_provenance.github_get", side_effect=fetch):
            result = public_search("https://github.com/example/dispatch", ["closure"], pages=1)
        self.assertEqual(len(result["candidates"]), 1)
        self.assertTrue(result["candidates"][0]["public_verified"])
        self.assertIn("+repair_closure()", result["candidates"][0]["text"])
        self.assertTrue(any("pagination_limit" in item for item in result["issues"]))
        self.assertEqual(len(calls), 3)
