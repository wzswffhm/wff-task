import json
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from validate_proposals import (
    DEFAULT_MAPPING,
    load_mapping,
    validate_document,
    validate_package,
)


class TestValidateProposals(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mapping = load_mapping(DEFAULT_MAPPING)
        cls.related_question = next(
            iter(cls.mapping["benchmarks"]["programbench"]["tasks"])
        )

    def proposal(
        self,
        proposal_type,
        sources,
        *,
        benchmark="programbench",
        domain="Software/CLI",
        related_question=None,
    ):
        if related_question is None:
            related_question = next(
                iter(self.mapping["benchmarks"][benchmark]["tasks"])
            )
        return {
            "benchmark": benchmark,
            "domain": domain,
            "related_question": related_question,
            "proposal_type": proposal_type,
            "allow_network": False,
            "proposal": {
                "A_modification_idea": "idea",
                "B_modification_details": "details",
                "C_agent_task": "task",
                "D_task_difficulties": ["difficulty"],
            },
            "proposal_sources": sources,
            "proposal_scene": "scene",
            "proposal_verify": "verify",
            "expert_experience_skill": "skill",
        }

    def issue_codes(self, proposal_type, sources, **overrides):
        issues = validate_document(
            self.proposal(proposal_type, sources, **overrides),
            f"{overrides.get('benchmark', 'programbench')}_test",
            self.mapping,
        )
        return [issue.code for issue in issues]

    def package_issues(self, source_entries):
        with tempfile.TemporaryDirectory() as temp_dir:
            package = Path(temp_dir) / "programbench_test"
            sources = package / "sources"
            sources.mkdir(parents=True)
            (package / "proposal.json").write_text(
                json.dumps(self.proposal("C", "internal source description")),
                encoding="utf-8",
            )
            for name, contents in source_entries.items():
                path = sources / name
                if contents is None:
                    path.mkdir()
                else:
                    path.write_text(contents, encoding="utf-8")
            return validate_package(package, self.mapping).issues

    def test_default_mapping_is_bundled_with_skill(self):
        self.assertEqual(
            DEFAULT_MAPPING,
            SKILL_ROOT / "references" / "benchmark_tasks.json",
        )
        self.assertTrue(DEFAULT_MAPPING.is_file())

    def test_type_a_and_b_require_git_repository_url(self):
        for proposal_type in ("A", "B"):
            with self.subTest(proposal_type=proposal_type):
                self.assertEqual(
                    self.issue_codes(proposal_type, "internal source description"),
                    ["missing_git_repository_url"],
                )
                self.assertEqual(
                    self.issue_codes(
                        proposal_type,
                        "来源仓库：https://github.com/example/repository",
                    ),
                    [],
                )

    def test_type_c_does_not_require_git_repository_url(self):
        self.assertEqual(
            self.issue_codes("C", "internal source description"),
            [],
        )

    def test_domain_has_two_or_three_clean_levels(self):
        cases = {
            "Software": "invalid_domain_depth",
            "Software/CLI/Tools/Extra": "invalid_domain_depth",
            "Software//CLI": "invalid_domain_segment",
            " Software/CLI": "invalid_domain_segment",
            "Software/CLI ": "invalid_domain_segment",
        }
        for domain, expected in cases.items():
            with self.subTest(domain=domain):
                self.assertIn(
                    expected,
                    self.issue_codes(
                        "C", "internal source description", domain=domain
                    ),
                )
        self.assertEqual(
            self.issue_codes(
                "C", "internal source description", domain="Software/CLI"
            ),
            [],
        )

    def test_related_question_must_be_a_real_task_folder(self):
        self.assertIn(
            "unknown_related_question",
            self.issue_codes(
                "C",
                "internal source description",
                related_question="not-a-real-task-folder",
            ),
        )

    def test_official_domain_prefix_for_every_classified_benchmark(self):
        for benchmark, entry in self.mapping["benchmarks"].items():
            if entry["domain_policy"] != "official_prefix":
                continue
            related_question, official = next(iter(entry["tasks"].items()))
            with self.subTest(benchmark=benchmark):
                self.assertEqual(
                    self.issue_codes(
                        "C",
                        "internal source description",
                        benchmark=benchmark,
                        related_question=related_question,
                        domain=official,
                    ),
                    [],
                )
                wrong = "Wrong/Category"
                self.assertIn(
                    "domain_mismatch",
                    self.issue_codes(
                        "C",
                        "internal source description",
                        benchmark=benchmark,
                        related_question=related_question,
                        domain=wrong,
                    ),
                )

    def test_one_level_official_domain_is_namespaced_by_benchmark(self):
        mapping = {
            "benchmarks": {
                name: {
                    "domain_policy": "freeform",
                    "task_count": 1,
                    "tasks": {"task": None},
                }
                for name in self.mapping["benchmarks"]
            }
        }
        mapping["benchmarks"]["terminal_bench3"] = {
            "domain_policy": "official_prefix",
            "task_count": 1,
            "tasks": {"single-category-task": "Database"},
        }
        good = self.proposal(
            "C",
            "internal source description",
            benchmark="terminal_bench3",
            related_question="single-category-task",
            domain="terminal_bench3/Database",
        )
        bad = dict(good)
        bad["domain"] = "Database/Storage"
        self.assertEqual(
            validate_document(good, "terminal_bench3_test", mapping), []
        )
        self.assertIn(
            "domain_mismatch",
            [
                issue.code
                for issue in validate_document(
                    bad, "terminal_bench3_test", mapping
                )
            ],
        )

    def test_empty_sources_directory_does_not_require_readme(self):
        self.assertEqual(self.package_issues({}), [])

    def test_nonempty_sources_directory_requires_readme(self):
        issues = self.package_issues({"fixture.txt": "data"})
        self.assertEqual(
            [(issue.code, issue.location) for issue in issues],
            [("missing_entry", "sources/README.md")],
        )

    def test_nonempty_sources_directory_accepts_readme_file(self):
        self.assertEqual(
            self.package_issues(
                {
                    "README.md": "Source documentation",
                    "fixture.txt": "data",
                }
            ),
            [],
        )

    def test_sources_readme_must_be_a_file(self):
        issues = self.package_issues({"README.md": None})
        self.assertEqual(
            [(issue.code, issue.location) for issue in issues],
            [("wrong_entry_type", "sources/README.md")],
        )


if __name__ == "__main__":
    unittest.main()
