# First ISO Acceptance Contract

Status: test plan; no bootable ISO is currently implied.

## Required inputs
- ISO path supplied by the workflow, never an invented or silently skipped artifact.
- Expected SHA-256 digest and image manifest.
- Pinned QEMU and UEFI firmware versions.
- Declared target: x86_64 UEFI console boot.

## Checks
1. Fail if the ISO or manifest is missing.
2. Verify the digest before boot.
3. Confirm image file is non-empty and its format is as expected.
4. Boot the ISO in a disposable VM with UEFI firmware and bounded CPU, memory and time.
5. Capture serial console output and QEMU exit state.
6. Require evidence of kernel start, userspace/init startup and a profile-specific success marker.
7. Fail on kernel panic, init failure, missing root, timeout or missing marker.
8. Upload logs and test metadata even on failure.
9. Never run installer disk writes against host disks; installer tests must use disposable virtual disks.

## Result semantics
A successful boot smoke test proves only that the tested image reached its declared userspace target in the tested VM configuration. It does not prove hardware compatibility, secure boot, update safety, reproducible builds or production readiness.
