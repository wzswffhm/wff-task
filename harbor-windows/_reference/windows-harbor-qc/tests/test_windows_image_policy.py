import copy
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from windows_image_policy import inspect_windows_dockerfile, validate_windows_image, validate_tools
from review_fixtures import passing_windows_image, passing_tools


class WindowsImagePolicyTests(unittest.TestCase):
    def inspect(self, dockerfile):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "environment").mkdir()
            (root / "environment" / "Dockerfile").write_text(dockerfile, encoding="utf-8")
            return inspect_windows_dockerfile(root)

    def test_nano_and_servercore_are_both_prohibited_runtime_bases(self):
        for image in ("windows/nanoserver:ltsc2025", "windows/servercore:ltsc2025",
                      "powershell:7.5-windowsservercore-ltsc2022"):
            with self.subTest(image=image):
                result = self.inspect("FROM mcr.microsoft.com/" + image + "\n")
                self.assertTrue(result["errors"])

    def test_stage_alias_and_default_arg_cannot_hide_prohibited_runtime(self):
        result = self.inspect("ARG BASE=mcr.microsoft.com/windows/servercore:ltsc2025\n"
                              "FROM ${BASE} AS runtime\nFROM runtime AS final\n")
        self.assertTrue(result["errors"])

    def test_unused_builder_is_not_the_delivered_runtime(self):
        result = self.inspect("FROM mcr.microsoft.com/windows/servercore:ltsc2025 AS build\n"
                              "FROM mcr.microsoft.com/windows/server:ltsc2025\n"
                              "COPY --from=build C:/build C:/app\n")
        self.assertFalse(result["errors"])

    def test_older_than_2019_is_rejected(self):
        self.assertTrue(self.inspect("FROM mcr.microsoft.com/windows:1709\n")["errors"])
        item = passing_windows_image("fixture:tag")
        item.update(windows_build=14393, release_year=2016)
        self.assertTrue(validate_windows_image(item, "fixture:tag"))

    def test_complete_2019_and_2022_are_allowed_without_2025_requirement(self):
        for build, year in ((17763, 2019), (20348, 2022), (26100, 2025)):
            item = passing_windows_image("fixture:tag")
            item.update(windows_build=build, release_year=year)
            self.assertFalse(validate_windows_image(item, "fixture:tag"))

    def test_unknown_custom_image_is_not_assumed_full_from_its_name(self):
        result = self.inspect("FROM private.example/windows-full:2025\n")
        self.assertFalse(result["errors"])
        item = passing_windows_image("private.example/windows-full:2025")
        item["runtime_bases"] = []
        self.assertTrue(validate_windows_image(item, item["configured_image"]))

    def test_custom_wrapper_with_nano_lineage_cannot_grant_pass(self):
        item = passing_windows_image("private.example/windows-full:2025")
        item["runtime_bases"][0]["family"] = "nanoserver"
        self.assertTrue(validate_windows_image(item, item["configured_image"]))

    def test_image_metadata_must_be_bound_to_delivered_reference(self):
        self.assertTrue(validate_windows_image(passing_windows_image("old:tag"), "new:tag"))

    def test_unknown_tool_inventory_or_path_only_evidence_cannot_grant_pass(self):
        item = passing_tools()
        item["tools"] = []
        self.assertTrue(validate_tools(item))
        item = passing_tools()
        item["tools"][0]["runtime_evidence"] = []
        self.assertTrue(validate_tools(item))
        item = passing_tools()
        item["tools"][0]["functional_probe"] = ""
        self.assertTrue(validate_tools(item))

    def test_host_manual_installation_is_not_valid_provisioning(self):
        item = passing_tools()
        item["tools"][0]["provisioning_kind"] = "host_manual"
        self.assertTrue(validate_tools(item))

    def test_installed_or_verified_base_tool_schema_can_pass(self):
        for mode in ("installed", "base_inherited"):
            item = passing_tools()
            item["tools"][0]["provisioning_kind"] = mode
            self.assertFalse(validate_tools(item))

    def test_confirmed_fail_and_block_need_no_fabricated_success_data(self):
        for status in ("FAIL", "BLOCKED"):
            self.assertFalse(validate_windows_image({"status": status}))
            self.assertFalse(validate_tools({"status": status}))


if __name__ == "__main__":
    unittest.main()
