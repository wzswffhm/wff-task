import io
import bz2
import gzip
import json
import lzma
import tarfile
import tempfile
import unittest
from pathlib import Path
import zipfile

import review_fixture
from obm_hack_scan import collect, compare, scan


class TestHackScan(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.sources = self.root / "sources"
        self.bench = self.root / "benchmark/task"
        self.sources.mkdir()
        self.bench.mkdir(parents=True)
        self.data = [{"record": "task-specific-patient-%02d" % i, "measurement": i * 13} for i in range(8)]
        (self.bench / "original.json").write_text(json.dumps(self.data))

    def test_renamed_and_reformatted_data_matches(self):
        (self.sources / "renamed.dat").write_text(json.dumps(self.data, indent=2, sort_keys=True))
        result = scan(self.sources, [self.bench])
        self.assertTrue(result["coverage_complete"])
        self.assertEqual(result["candidates"][0]["method"], "normalized_content")
        self.assertEqual(result["decision"], "REQUIRES_ANALYST")

    def test_partial_records_are_candidates(self):
        changed = self.data[:4] + [{"different": "independent data"}]
        (self.sources / "subset.json").write_text(json.dumps(changed))
        result = scan(self.sources, [self.bench])
        self.assertTrue(any(c["method"] == "partial_content" for c in result["candidates"]))

    def test_zip_and_tar_members_match_without_extraction(self):
        raw = json.dumps(self.data).encode()
        with zipfile.ZipFile(self.sources / "zip-fixtures.zip", "w") as archive:
            archive.writestr("nested/renamed.json", raw)
            archive.writestr("../escaped.json", raw)
        with tarfile.open(self.sources / "tar-fixtures.tgz", "w:gz") as archive:
            info = tarfile.TarInfo("nested/input.json")
            info.size = len(raw)
            archive.addfile(info, io.BytesIO(raw))
        result = scan(self.sources, [self.bench])
        matches = [c["source"]["path"] for c in result["candidates"]]
        self.assertTrue(any(".zip!/nested/renamed.json" in p for p in matches))
        self.assertTrue(any(".tgz!/nested/input.json" in p for p in matches))
        self.assertFalse((self.root / "escaped.json").exists())
        self.assertFalse(result["coverage_complete"])
        self.assertTrue(any(i["reason"] == "unsafe_or_large_member" for i in result["issues"]))

    def test_link_only_is_not_a_hack_and_license_is_only_a_candidate(self):
        (self.sources / "benchmark.json").write_text('{"url":"https://github.com/harbor-framework/terminal-bench"}')
        self.assertEqual(scan(self.sources, [self.bench])["candidates"], [])
        license_text = "Permission is hereby granted, free of charge, to any person obtaining a copy."
        (self.sources / "LICENSE").write_text(license_text)
        (self.bench / "LICENSE").write_text(license_text)
        result = scan(self.sources, [self.bench])
        self.assertEqual(len(result["candidates"]), 1)
        self.assertEqual(result["decision"], "REQUIRES_ANALYST")
        self.assertNotIn("REJECT", json.dumps(result))

    def test_empty_large_and_unsupported_inputs_have_coverage_gaps(self):
        self.assertFalse(scan(self.sources, [self.bench])["coverage_complete"])
        (self.sources / "huge.bin").write_bytes(b"x" * 200)
        (self.sources / "hidden.7z").write_bytes(b"7zip")
        result = scan(self.sources, [self.bench], max_file=100)
        self.assertFalse(result["coverage_complete"])
        self.assertTrue(any("byte limit" in i["reason"] for i in result["issues"]))
        self.assertTrue(any(i["reason"] == "unsupported_compression" for i in result["issues"]))

    def test_candidate_limit_is_reported(self):
        (self.sources / "a.json").write_text(json.dumps(self.data))
        (self.sources / "b.json").write_text(json.dumps(self.data))
        result = compare(collect(self.sources), [collect(self.bench)], max_candidates=1)
        self.assertEqual(len(result["candidates"]), 1)
        self.assertFalse(result["coverage_complete"])
        self.assertTrue(any(i["reason"] == "candidate_limit" for i in result["issues"]))

    def test_renamed_compression_streams_and_zip_are_opened(self):
        raw = json.dumps(self.data).encode()
        for name, encode in [("gzip", gzip.compress), ("bzip", bz2.compress), ("xz", lzma.compress)]:
            (self.sources / (name + ".dat")).write_bytes(encode(raw))
        with zipfile.ZipFile(self.sources / "disguised.dat", "w") as archive:
            archive.writestr("records.dat", raw)
        result = scan(self.sources, [self.bench])
        self.assertTrue(result["coverage_complete"], result["issues"])
        self.assertEqual(len(result["candidates"]), 4)
        self.assertTrue(all("!/" in c["source"]["path"] for c in result["candidates"]))

    def test_large_files_still_have_exact_hash_matches(self):
        raw = b"large task binary content\n" * 100
        (self.sources / "large.bin").write_bytes(raw)
        (self.bench / "renamed.bin").write_bytes(raw)
        result = scan(self.sources, [self.bench], max_file=100)
        self.assertTrue(any(c["method"] == "exact_bytes" for c in result["candidates"]))
        self.assertFalse(result["coverage_complete"])
        self.assertEqual(result["source"]["files"][0]["scan_mode"], "exact_hash_only")

    def test_zero_byte_file_does_not_count_as_readable_source_content(self):
        (self.sources / "empty").write_bytes(b"")
        result = scan(self.sources, [self.bench])
        self.assertFalse(result["coverage_complete"])
        self.assertTrue(any(i["reason"] == "no_readable_content" for i in result["issues"]))
