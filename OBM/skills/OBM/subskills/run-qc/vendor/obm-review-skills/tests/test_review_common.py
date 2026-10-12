import tempfile
import unittest
from pathlib import Path
import os
import sys

import review_fixture
from review_common import load_json, read_bytes, run, seal


class TestReviewCommon(unittest.TestCase):
    def test_read_bytes_bound_and_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "data"
            path.write_bytes(b"12345")
            self.assertEqual(read_bytes(path, 5), b"12345")
            with self.assertRaisesRegex(ValueError, "byte limit"):
                read_bytes(path, 4)
            link = Path(tmp) / "link"
            try:
                link.symlink_to(path)
            except OSError as error:
                if os.name == "nt" and getattr(error, "winerror", None) == 1314:
                    self.skipTest("Windows symlink privilege is unavailable")
                raise
            with self.assertRaisesRegex(ValueError, "symlink"):
                read_bytes(link)

    def test_seal_order_and_nonfinite_json(self):
        self.assertEqual(seal({"b": 2, "a": 1}), seal({"a": 1, "b": 2, "packet_id": "old"}))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "value.json"
            path.write_text('{"score": NaN}')
            with self.assertRaisesRegex(ValueError, "non-finite"):
                load_json(path)

    def test_run_success_error_timeout_and_output_limit(self):
        self.assertEqual(run([sys.executable, "-c", "print('ok')"]).replace(b"\r\n", b"\n"), b"ok\n")
        with self.assertRaisesRegex(ValueError, "exit 7"):
            run([sys.executable, "-c", "raise SystemExit(7)"])
        with self.assertRaisesRegex(ValueError, "timeout"):
            run([sys.executable, "-c", "import time; time.sleep(1)"], timeout=0.05)
        with self.assertRaisesRegex(ValueError, "output limit"):
            run([sys.executable, "-c", "print('x'*5000)"], max_bytes=100)
