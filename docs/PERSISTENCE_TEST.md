# Disposable-VM two-clean-reboot acceptance

This test uses the **unchanged released 0.3.0 ISO**, SHA-256
`63be2439540ce02b5821791ea93e4cda5669f2b8adcd7a7d3d96fe921accc001`.
It extracts that ISO's kernel/initrd and boots its live filesystem three times
sequentially. This is a persistence test, **not a firmware, physical USB,
graphical kiosk, browser palette, power-loss, or hardware compatibility test**.

## Safety boundary

- No disk-device argument, host formatting, host loop mount, privileged container,
  device passthrough, host network or Docker socket is required or supported.
- The only writable disk attached to QEMU is a newly created, exclusively opened
  256 MiB regular scratch file inside the disposable container. Existing files,
  symlinks and `/dev` input are rejected. No physical drive is selected.
- `mkfs.ext4 -d` seeds `persistence.conf` containing `/home union`; no filesystem
  is mounted on the host/container. Only the guest mounts its virtual USB volume.
- The ISO is bind-mounted read-only and QEMU attaches it read-only. The writable
  scratch file is attached as **removable USB mass storage**, retaining the
  production `persistence-media=removable-usb persistence-storage=filesystem` filter.
- QEMU has one vCPU, 2048 MiB RAM, TCG, no NIC and a 300-second bound per boot.
  The Docker container is bounded to 2500 MiB, one CPU and 256 MiB shared memory.
- `systemd.debug_shell=ttyS0` and masking the serial getty are **external VM-only
  kernel arguments**. They do not change the ISO or production boot configuration.
  Never enable a root debug shell in a distributed image.

## Protocol and evidence

1. Boot 1: GET `/api/notes` must be empty; POST a unique multiline UTF-8/literal
   marker through the actual running release API, then GET exact equality.
2. Request guest `systemctl poweroff`. Require kernel `Power down`, QEMU exit 0,
   and a successful read-only `e2fsck -fn` after exit.
3. Boot 2 with the same scratch file: GET must equal boot 1's exact marker; POST
   an updated marker and GET exact equality. Repeat clean shutdown/check.
4. Boot 3 with that file: GET must equal boot 2's updated marker. Repeat clean
   shutdown/check. Require three distinct kernel boot IDs.

These are two full clean shutdown/cold-start cycles, not backend restarts.
Each pass retains its command JSON, serial log, QEMU stderr, filesystem check,
mount table and `lsblk` inventory. `result.json` is written even on failure;
`passed: true` requires all three passes and distinct boot IDs. API failure
still requests shutdown but cannot produce a successful assertion record.
No graphical screenshot is required or claimed by this serial/API test.
The live system may report its read-only optical medium/SquashFS loop still
busy during shutdown; retain those messages rather than hiding them. The
persistence acceptance also requires the writable ext4 scratch volume to pass
its post-poweroff filesystem check, independently of read-only media teardown.

## Reproduce safely

Run the unit guards first:

```sh
python3 -m unittest discover -s tests -p test_persistence.py -v
```

Use a new uniquely named disposable container; the command below mounts only
read-only inputs. Do not add privileges, devices or writable host paths.
Replace `ISO` with the canonical path to the matching released regular file.
The script deliberately pins the released digest and refuses reused `/evidence`.

```sh
ISO=/home/jayjayman4000/gravestone-test-evidence/release-0.3.0/artifacts/gravestone-0.3.0-amd64.iso
NAME=gravestone-persistence-acceptance
docker run -d --name "$NAME" --memory=2500m --cpus=1 --shm-size=256m \
  --mount type=bind,src="$ISO",dst=/input/release.iso,readonly \
  --mount type=bind,src=/home/jayjayman4000/Gravestone/scripts,dst=/harness,readonly \
  debian:bookworm sleep infinity
docker exec "$NAME" sh -c 'apt-get update && apt-get install -y --no-install-recommends qemu-system-x86 xorriso e2fsprogs python3'
docker exec "$NAME" python3 /harness/test-persistence.py
# Preserve evidence BEFORE removing this one owned container, also on failure.
docker cp "$NAME":/evidence /home/jayjayman4000/gravestone-test-evidence/persistence-reboots
docker rm -f "$NAME"
```

Package installation uses the container's normal network; the VM itself has no
network adapter. Retain the exact container ID/resource/mount inspection and
QEMU version with the evidence. Never stop shared services to run this test.

## Executed acceptance: released 0.3.0

The run completed on 2026-10-31 UTC with `passed: true`. Durable evidence is at
`/home/jayjayman4000/gravestone-test-evidence/persistence-reboots/`.

| Pass | Result | Kernel boot ID |
| --- | --- | --- |
| 1 | Empty notebook; exact API save/read; clean poweroff | `a91106a7-e5c2-4056-b13b-c129330ddabb` |
| 2 | Exact prior note; exact updated API save/read; clean poweroff | `5f3e59d7-eed2-416c-add9-f3e719f8b4dd` |
| 3 | Exact updated note; clean poweroff | `68e45454-bca8-4e64-acd2-092de5f2fe32` |

All three QEMU exits were 0 and all three post-poweroff `e2fsck -fn` checks
passed. The final filesystem header independently reports **state clean** and
**mount count 3**. Mountinfo shows `/home` overlay upper/work directories on
`/run/live/persistence/sda`; `lsblk` identifies that device as USB, removable,
ext4, label `persistence`. No internal disk was attached. The owned container
was removed afterward; shared listeners 8766/8879 and healthy `open-webui`
remained present. Optional browser palette/map persistence was not exercised.

The harness guard tests pass (3 tests). The final integrated checkout suite
ran 102 tests successfully with 3 explicit skips; this includes concurrent work
outside this test's three owned files, not additional code inside the ISO.
`full-suite.log`, `unit-tests.log`, `container-inspect.json`, the final filesystem
header, per-boot logs/commands, `result.json` and the scratch image are retained.
Read-only optical-medium teardown warnings are preserved in the serial logs;
the writable ext4 volume was clean afterward.

## Continuous acceptance for new images

The image-build workflow runs this same protocol against the freshly built ISO, not an older release. It verifies the checksum file, computes the exact ISO SHA-256 and passes that pin as `GRAVESTONE_TEST_ISO_SHA256`. The harness accepts only a 64-character lowercase hexadecimal expected digest; when unset it retains the published 0.3.0 pin for the standalone reproduction above. This override changes no input paths and permits no device arguments.

The CI container has the same memory/CPU bounds, read-only source/ISO mounts and no privileges/device passthrough. After dependency installation its bridge network is disconnected before any boot. A trap copies only result JSON and per-boot commands/serial/fsck logs, then removes that owned container. The scratch disk and extracted kernel/initrd are not uploaded. A failed protocol fails the build; uploading logs on failure is not a passing persistence result.

## Verification boundary

A successful VM run proves notebook API data survives these two clean guest
reboots using Debian live `/home` union persistence on emulated removable USB.
It does not prove physical USB media durability, USB-controller behavior,
firmware boot, arbitrary hardware support, graphical saving, browser localStorage
or unexpected power-loss recovery. Physical two-clean-reboot acceptance remains
required before trusting important notebooks on a real provisioned device.
