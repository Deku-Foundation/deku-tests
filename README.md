# Deku Integration Tests

Cross-repository integration and system acceptance tests for Deku Linux.

## Status

Bootstrap stage. No bootable ISO or supported system exists yet; tests must report this honestly and fail when required artifacts are absent.

## Responsibilities

- Validate integration contracts between recipes, build plans, package metadata, system manifests and release manifests.
- Run disposable QEMU/KVM UEFI boot tests for generated images.
- Capture serial console logs, exit status, builder versions, commit IDs and artifact digests.
- Add package install/upgrade/rollback and installer tests only after those operations exist.

## Safety

Never run disk-writing acceptance tests against a developer's real disk. Use disposable virtual disks and VMs. Tests must not receive signing secrets or production credentials.

## Boot smoke-test harness

`tools/boot_smoke.py` accepts an existing ISO, its expected SHA-256, a UEFI firmware file, and a serial-console marker. It runs QEMU with software emulation and a bounded timeout; it does not write host disks or build an ISO.

Example after downloading a workflow artifact:

```sh
python3 tools/boot_smoke.py \\
  --iso ./deku-linux-technology-preview-x86_64.iso \\
  --sha256 <64-character-lowercase-sha256> \\
  --firmware /usr/share/OVMF/OVMF_CODE.fd \\
  --marker DEKU_BOOT_OK:minimal-x86_64 \\
  --timeout 180 \\
  --evidence-dir ./boot-evidence
```

The ISO digest is checked before QEMU starts. The test passes only if the exact marker appears in serial output and QEMU remains alive until the bounded timeout. The evidence directory preserves `serial.log`; without it, temporary logs are deleted after the run.

No Deku ISO has passed this harness yet. A unit-test pass validates the harness logic only, not system bootability.

## Initial milestone

A reusable smoke-test harness that boots an explicitly supplied ISO in a disposable x86_64 UEFI VM and fails if the declared userspace target is not reached. It must not fabricate success when no ISO exists.
