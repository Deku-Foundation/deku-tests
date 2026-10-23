#!/usr/bin/env python3
"""Verify an ISO digest and boot a supplied ISO in disposable QEMU UEFI.

The harness does not create images or write host disks. It boots only the ISO
explicitly provided by the caller and requires a serial-console marker emitted
after the target userspace is ready. When --evidence-dir is supplied, logs and a
JSON result are retained there on both success and failure.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def save_result(directory: Path, result: dict[str, object]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "boot-result.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def build_qemu_command(
    qemu: str,
    iso: Path,
    firmware: Path,
    serial_log: Path,
    writable_vars: Path,
) -> list[str]:
    """Build a QEMU command using the UEFI pflash code/variable-store pair."""
    return [
        qemu,
        "-machine", "q35",
        "-accel", "tcg",
        "-m", "2048",
        "-smp", "2",
        "-drive", f"if=pflash,format=raw,readonly=on,file={firmware}",
        "-drive", f"if=pflash,format=raw,file={writable_vars}",
        "-cdrom", str(iso),
        "-boot", "d",
        "-display", "none",
        "-monitor", "none",
        "-serial", f"file:{serial_log}",
        "-no-reboot",
        "-no-shutdown",
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iso", required=True, type=Path, help="existing ISO to boot")
    parser.add_argument("--sha256", required=True, help="expected lowercase SHA-256 of the ISO")
    parser.add_argument("--firmware", required=True, type=Path, help="UEFI firmware code file")
    parser.add_argument("--firmware-vars", required=True, type=Path, help="matching writable UEFI variable-store template")
    parser.add_argument("--marker", required=True, help="serial marker emitted after userspace is ready")
    parser.add_argument("--timeout", type=int, default=180, help="boot timeout in seconds (default: 180)")
    parser.add_argument("--qemu", default="qemu-system-x86_64", help="QEMU executable")
    parser.add_argument("--evidence-dir", type=Path, help="directory to retain serial log, QEMU stderr and result JSON")
    args = parser.parse_args()

    evidence_dir = args.evidence_dir.resolve() if args.evidence_dir else None
    if evidence_dir:
        evidence_dir.mkdir(parents=True, exist_ok=True)

    def fail(message: str, result: dict[str, object] | None = None) -> int:
        print(f"FAIL: {message}", file=sys.stderr)
        if evidence_dir and result is not None:
            save_result(evidence_dir, result)
        return 2

    if not _SHA256.fullmatch(args.sha256):
        return fail("--sha256 must be 64 lowercase hexadecimal characters")
    if not args.iso.is_file() or args.iso.stat().st_size == 0:
        return fail("--iso must name an existing non-empty file")
    if not args.firmware.is_file():
        return fail("--firmware must name an existing UEFI firmware code file")
    if not args.firmware_vars.is_file():
        return fail("--firmware-vars must name an existing UEFI variable-store template")
    if not args.marker or len(args.marker) > 256 or any(ord(c) < 32 for c in args.marker):
        return fail("--marker must contain 1 to 256 printable characters")
    if not 10 <= args.timeout <= 900:
        return fail("--timeout must be between 10 and 900 seconds")
    if shutil.which(args.qemu) is None:
        return fail(f"QEMU executable not found: {args.qemu}")

    iso = args.iso.resolve()
    firmware = args.firmware.resolve()
    firmware_vars = args.firmware_vars.resolve()
    actual_digest = sha256_file(iso)
    base_result: dict[str, object] = {
        "schema_version": 1,
        "status": "failed",
        "iso": iso.name,
        "iso_size_bytes": iso.stat().st_size,
        "expected_sha256": args.sha256,
        "actual_sha256": actual_digest,
        "marker": args.marker,
        "firmware": str(firmware),
        "firmware_vars_template": str(firmware_vars),
        "timeout_seconds": args.timeout,
    }
    if actual_digest != args.sha256:
        base_result["failure"] = "ISO SHA-256 mismatch"
        return fail(f"ISO SHA-256 mismatch: expected {args.sha256}, got {actual_digest}", base_result)

    with tempfile.TemporaryDirectory(prefix="deku-boot-smoke-") as temp_name:
        temp_dir = Path(temp_name)
        serial_log = temp_dir / "serial.log"
        qemu_stderr = temp_dir / "qemu.stderr.log"
        writable_vars = temp_dir / "OVMF_VARS.fd"
        shutil.copyfile(firmware_vars, writable_vars)
        command = build_qemu_command(
            args.qemu, iso, firmware, serial_log, writable_vars
        )
        start = time.monotonic()
        marker_found = False
        exit_code: int | None = None
        qemu_error = ""

        with qemu_stderr.open("wb") as err_stream:
            process = subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=err_stream,
                close_fds=True,
            )
            try:
                while time.monotonic() - start < args.timeout:
                    current_log = serial_log.read_text(encoding="utf-8", errors="replace") if serial_log.exists() else ""
                    if args.marker in current_log:
                        marker_found = True
                        break
                    exit_code = process.poll()
                    if exit_code is not None:
                        break
                    time.sleep(1)
            except KeyboardInterrupt:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                raise
            finally:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
                if exit_code is None:
                    exit_code = process.returncode

        elapsed = round(time.monotonic() - start, 2)
        serial_text = serial_log.read_text(encoding="utf-8", errors="replace") if serial_log.exists() else ""
        qemu_error = qemu_stderr.read_text(encoding="utf-8", errors="replace")
        if evidence_dir:
            evidence_dir.mkdir(parents=True, exist_ok=True)
            (evidence_dir / "serial.log").write_text(serial_text, encoding="utf-8")
            (evidence_dir / "qemu.stderr.log").write_text(qemu_error, encoding="utf-8")
        base_result.update({
            "elapsed_seconds": elapsed,
            "marker_found": marker_found,
            "qemu_exit_code": exit_code,
            "serial_bytes": len(serial_text.encode("utf-8")),
        })

        if not marker_found:
            base_result["failure"] = "userspace marker not observed"
            if evidence_dir:
                save_result(evidence_dir, base_result)
            print("FAIL: expected userspace marker was not observed in serial output", file=sys.stderr)
            print(serial_text[-8000:], file=sys.stderr)
            if qemu_error:
                print(qemu_error[-3000:], file=sys.stderr)
            return 1

        base_result["status"] = "passed"
        if evidence_dir:
            save_result(evidence_dir, base_result)
        print(f"PASS: observed userspace marker in UEFI boot; iso_sha256={actual_digest}")
        print(f"evidence: {evidence_dir if evidence_dir else 'temporary logs only'}; elapsed_seconds={elapsed}")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
