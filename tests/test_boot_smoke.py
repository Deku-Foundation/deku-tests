import hashlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.boot_smoke import _SHA256, sha256_file

SCRIPT = Path(__file__).parents[1] / "tools" / "boot_smoke.py"


class BootSmokeUnitTests(unittest.TestCase):
    def test_sha256_streaming(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "sample.iso"
            path.write_bytes(b"not-an-iso-fixture")
            self.assertEqual(sha256_file(path), hashlib.sha256(b"not-an-iso-fixture").hexdigest())

    def test_sha256_contract_is_canonical(self):
        self.assertTrue(_SHA256.fullmatch("a" * 64))
        self.assertFalse(_SHA256.fullmatch("A" * 64))
        self.assertFalse(_SHA256.fullmatch("a" * 63))

    def test_help_includes_evidence_directory(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--help"],
            check=False,
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--evidence-dir", result.stdout)

    def test_result_evidence_is_valid_json(self):
        from tools.boot_smoke import save_result

        with tempfile.TemporaryDirectory() as temp_dir:
            save_result(Path(temp_dir), {"status": "failed", "schema_version": 1})
            result = Path(temp_dir, "boot-result.json").read_text(encoding="utf-8")
            self.assertIn('"status": "failed"', result)
            self.assertIn('"schema_version": 1', result)


if __name__ == "__main__":
    unittest.main()
