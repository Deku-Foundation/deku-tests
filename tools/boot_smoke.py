#!/usr/bin/env python3
"""Boot an explicitly supplied ISO in disposable QEMU and require a serial marker.

This tool does not create images or write host disks. It only boots the supplied
ISO, captures serial output in a temporary directory, and reports a pass when
the expected marker appears. A timeout is expected for a live system that keeps
running after reaching the target.
"""
from __future__ import annotations

import argparse
import hashlib
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iso", required=True, type=Path, help="existing ISO to boot")
    parser.add_argument("--sha256", required=True, help="expected lowercase SHA-256 of the ISO")
    parser.add_argument("--firmware", required=True, type=Path, help="UEFI firmware code file, e.g. OVMF_CODE.fd")
    parser.add_argument("--marker", required=True, help="exact ASCII marker emitted after the target userspace is ready")
    parser.add_argument("--timeout", type=int, default=180, help="boot timeout in seconds (default: 180)")
    parser.add_argument("--qemu", default="qemu-system-x86_64", help="QEMU executable")
    args = parser.parse_args()

    if not _SHA256.fullmatch(args.sha256):
        parser.error("--sha256 must be 64 lowercase hexadecimal characters")
    if not args.iso.is_file() or args.iso.stat().st_size == 0:
        parser.error("--iso must name an existing non-empty file")
    if not args.firmware.is_file():
        parser.error("--firmware must name an existing UEFI firmware file")
    if not args.marker or len(args.marker) > 256 or any(ord(c) < 32 for c in args.marker):
        parser.error("--marker must be 1..256 printable characters")
    if not 10 <= args.timeout <= 900:
        parser.error("--timeout must be between 10 and 900 seconds")
    if shutil.which(args.qemu) is None:
        parser.error(f"QEMU executable not found: {args.qemu}")

    actual = sha256_file(args.iso)
    if actual != args.sha256:
        print(f"FAIL: ISO SHA-256 mismatch: expected {args.sha256}, got {actual}", file=sys.stderr)
        return 2

    with tempfile.TemporaryDirectory(prefix="deku-boot-smoke-") as temp_dir:
        serial_log = Path(temp_dir) / "serial.log"
        command = [
            args.qemu,
            "-machine", "q35",
            "-accel", "tcg",
            "-m", "2048",
            "-smp", "2",
            "-bios", str(args.firmware.resolve()),
            "-cdrom", str(args.iso.resolve()),
            "-boot", "d",
            "-display", "none",
            "-monitor", "none",
            "-serial", f"file:{serial_log}",
            "-no-reboot",
            "-no-shutdown",
        ]
        timed_out = False
        try:
            completed = subprocess.run(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                timeout=args.timeout,
                check=False,
                text=True,
            )
            if completed.returncode != 0:
                print(f"QEMU exited with status {completed.returncode}: {completed.stderr[-2000:]}", file=sys.stderr)
        except subprocess.TimeoutExpired:
            timed_out = True

        log = serial_log.read_text(encoding="utf-8", errors="replace") if serial_log.exists() else ""
        if args.marker not in log:
            print("FAIL: expected userspace marker was not observed in serial output", file=sys.stderr)
            print(log[-8000:], file=sys.stderr)
            return 1
        if not timed_out:
            print("FAIL: QEMU exited before the bounded boot window completed", file=sys.stderr)
            return 1

        print(f"PASS: observed userspace marker in UEFI boot; iso_sha256={actual}")
        print(f"evidence: serial_bytes={len(log.encode('utf-8'))}, timeout_seconds={args.timeout}")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
