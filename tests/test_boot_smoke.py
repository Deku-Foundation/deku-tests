import hashlib
import tempfile
import unittest
from pathlib import Path

from tools.boot_smoke import sha256_file, _SHA256


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


if __name__ == "__main__":
    unittest.main()
