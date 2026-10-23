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

## Initial milestone

A reusable smoke-test harness that boots an explicitly supplied ISO in a disposable x86_64 UEFI VM and fails if the declared userspace target is not reached. It must not fabricate success when no ISO exists.
