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

    def proposal(self, proposal_type, sources):
        return {
            "benchmark": "programbench",
            "domain": "Software/CLI",
            "related_question": self.related_question,
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

    def issue_codes(self, proposal_type, sources):
        issues = validate_document(
            self.proposal(proposal_type, sources),
            "programbench_test",
            self.mapping,
        )
        return [issue.code for issue in issues]

    def package_issues(self, source_entries):
        with tempfile.TemporaryDirectory() as temp_dir:
            package = Path(temp_dir) / "programbench_test"
            sources = package / "sources"
            sources.mkdir(parents=True)
            (package / "proposal.json").write_text(
                json.dumps(self.proposal("A", "internal source description")),
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

    def test_type_a_does_not_require_git_repository_url(self):
        self.assertEqual(self.issue_codes("A", "internal source description"), [])

    def test_type_b_requires_git_repository_url(self):
        self.assertEqual(
            self.issue_codes("B", "internal source description"),
            ["missing_git_repository_url"],
        )
        self.assertEqual(
            self.issue_codes("B", "https://github.com/example/repository"),
            [],
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
