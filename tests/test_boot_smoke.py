import hashlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.boot_smoke import _SHA256, build_qemu_command, infer_firmware_vars, sha256_file

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
        self.assertIn("--firmware-vars", result.stdout)

    def test_ovmf_vars_inference_requires_matching_code_filename(self):
        self.assertEqual(infer_firmware_vars(Path("OVMF_CODE_4M.fd")), Path("OVMF_VARS_4M.fd"))
        self.assertEqual(infer_firmware_vars(Path("OVMF_CODE.fd")), Path("OVMF_VARS.fd"))
        self.assertIsNone(infer_firmware_vars(Path("custom-firmware.fd")))

    def test_qemu_uses_uefi_pflash_code_and_vars(self):
        command = build_qemu_command(
            "qemu-system-x86_64",
            Path("preview.iso"),
            Path("OVMF_CODE_4M.fd"),
            Path("serial.log"),
            Path("OVMF_VARS_copy.fd"),
        )
        self.assertIn(
            "if=pflash,format=raw,readonly=on,file=OVMF_CODE_4M.fd",
            command,
        )
        self.assertIn(
            "if=pflash,format=raw,file=OVMF_VARS_copy.fd",
            command,
        )
        self.assertNotIn("-bios", command)

    def test_guest_failure_marker_is_recognized(self):
        import re

        match = re.search(r"(?m)^DEKU_BOOT_FAIL:([A-Za-z0-9_.:-]{1,128})$", "DEKU_BOOT_FAIL:selinux-not-enforcing\n")
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), "selinux-not-enforcing")
        self.assertIsNone(re.search(r"(?m)^DEKU_BOOT_FAIL:([A-Za-z0-9_.:-]{1,128})$", "DEKU_BOOT_FAIL:bad value\n"))

    def test_result_evidence_is_valid_json(self):
        from tools.boot_smoke import save_result

        with tempfile.TemporaryDirectory() as temp_dir:
            save_result(Path(temp_dir), {"status": "failed", "schema_version": 1})
            result = Path(temp_dir, "boot-result.json").read_text(encoding="utf-8")
            self.assertIn('"status": "failed"', result)
            self.assertIn('"schema_version": 1', result)


if __name__ == "__main__":
    unittest.main()
