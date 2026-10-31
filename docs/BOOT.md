# Booting and building Gravestone

## Scope and current verification boundary

The recipe targets **Debian 12 (bookworm), amd64/x86-64**, with an Xorg,
Openbox, LightDM and Firefox ESR kiosk. The root filesystem is XZ-compressed
SquashFS. BIOS uses ISOLINUX; 64-bit UEFI uses GRUB. Both boot menus start the
first live entry after three seconds. **Secure Boot is disabled/unsupported**;
disable it in firmware. ARM/aarch64, Apple Silicon, 32-bit UEFI, and machines
requiring proprietary graphics/Wi-Fi firmware are not supported by this recipe.
Only Debian `main` is enabled; no extra firmware is bundled.

Source/configuration tests do **not** establish that an ISO boots. A successful
remote build plus all five VM checks below is required before calling an
artifact boot-tested. Those checks validate kernel/live filesystem/backend boot,
not a visible Firefox session, physical hardware, USB boot, or persistence.
Manual graphical and physical-device persistence checks remain required. The workflow also exercises the actual notebook API across two clean disposable-VM reboots on newly built images; this is distinct from physical-stick durability. No workflow
publishes a release automatically. A failed-run artifact is diagnostic material,
not a release candidate.

## Build on GitHub Actions

The workflow is `.github/workflows/build-live.yml` (`workflow_dispatch` only).
It runs on an Ubuntu amd64 GitHub-hosted runner, installs build dependencies
inside a **privileged `debian:bookworm` Docker container**, and runs the real
`lb config` and `lb build`. Debian archive signatures remain enabled; the
Debian archive keyring authenticates the standard Debian and security mirrors.
No third-party APT repository or unsigned/trusted override is used. Container
privilege is needed for debootstrap/chroot/mount operations: run only trusted
source, not unreviewed contributions.

After the maintainer reviews and pushes the workflow to the default branch:

```sh
gh workflow run build-live.yml --ref main
gh run list --workflow build-live.yml --limit 5
# Replace RUN_ID with the id returned by the listing.
gh run watch RUN_ID --exit-status
gh run download RUN_ID --name gravestone-0.4.0-amd64 --dir dist
gh run download RUN_ID --name gravestone-build-logs --dir build-logs
(cd dist && sha256sum -c gravestone-0.4.0-amd64.iso.sha256)
```

Outputs:

- `dist/gravestone-0.4.0-amd64.iso`
- `dist/gravestone-0.4.0-amd64.iso.sha256`
- `dist/filesystem.packages` (installed Debian package/version manifest)
- Build, boot-catalog, extraction, serial VM and disk-space logs in the log
  artifact. ISO artifacts are retained seven days; logs fourteen days.

The builder first compiles the pinned baseline-CPU llama.cpp runtime and installs the verified Qwen model. It runs installed-artifact integrity and actual inference tests, including the production retrieval path within its 20-second timeout, before `lb build`. Evidence files `real-inference.json` and `AI_BUILD_PROVENANCE.json` accompany the image artifact. See [AI package details](../ai/README.md). A lightweight test run with the two artifact/inference tests skipped is not AI verification.

The ISO is rejected if it exceeds **14,000,000,000 bytes**. Artifacts and logs
are uploaded even after a later failure. Check the run conclusion and serial
logs, not just artifact existence. This is a rebuildable recipe, **not** a
claim of bit-for-bit reproducibility: Debian security packages and the Debian
container tag can change between builds. For release provenance retain the
commit, workflow run id, package manifest, checksum and logs.

A full local build is intentionally not part of lightweight validation. It
requires a disposable amd64 Linux builder with Docker, adequate free disk space
(plan at least 25 GiB), internet access, and root/privileged-container permission.
Use the dependency list and Docker invocation in the workflow. Do not run it on
a nearly-full shared server. `scripts/build-live.sh BUILD_DIR OUTPUT_DIR` runs
inside that container. The build directory must be empty and **outside** the
source repository; the script never deletes an existing build tree.

For configuration-only staging on a machine without root/live-build:

```sh
python3 -m unittest discover -s tests -p test_build_config.py -v
scripts/prepare-live.sh /tmp/gravestone-fresh-build
```

`prepare-live.sh` copies application, content and repository documentation to
`config/includes.chroot/opt/gravestone`; Git history, bytecode, virtualenvs,
build output, CI files and tests are excluded. The recipe itself is in `live/`.
`live/auto/config` is the single source of live-build options. Actual
configuration validation, when bookworm live-build is installed, is:

```sh
cd /tmp/gravestone-fresh-build
lb config
lb config noauto --validate
```

## VM acceptance checks

Install `qemu-system-x86`, `ovmf`, and `xorriso` on the test host, then run:

```sh
scripts/smoke-iso.sh dist/gravestone-0.4.0-amd64.iso logs
```

All VMs use TCG, two vCPUs, 2 GiB RAM, no network adapter and no user/internal
disk. Each boot is bounded by `timeout 240`.

1. **Direct-kernel live-system check:** xorriso extracts `/live/vmlinuz` and
   `/live/initrd.img`. QEMU boots them with the original ISO attached as a CD,
   `boot=live components console=ttyS0,115200 gravestone.smoke=1`, and
   `nopersistence`. live-boot finds `/live/filesystem.squashfs` on the CD.
   Only this opt-in kernel flag enables `gravestone-smoke.service`; its script
   independently checks the same flag, waits for a successful HTTP response
   from `http://127.0.0.1:8766/api/status`, writes `GRAVESTONE_BOOT_OK` to the
   serial port, and powers the guest off. Both a clean QEMU exit and marker
   are required. This check alone does **not** validate a firmware bootloader.
2. **Unmodified whole-ISO BIOS check:** QEMU's default SeaBIOS boots the actual
   ISO, including ISOLINUX, until `GRAVESTONE_SERVICE_READY` appears after the
   backend's successful readiness probe. The host then terminates that VM.
3. **Unmodified whole-ISO UEFI check:** OVMF boots that same ISO with a disposable
   copy of its variable store. The same backend-ready marker is required,
   then the host terminates the VM. No Secure Boot claim is made.

4. **Unmodified BIOS USB-as-disk check:** SeaBIOS boots the same ISO attached as removable USB mass storage, with no CD-ROM attached; the backend-ready marker is required.
5. **Unmodified UEFI USB-as-disk check:** OVMF boots the same ISO attached as removable USB mass storage, with no CD-ROM attached; the backend-ready marker is required. Both USB checks exercise the DD-image layout, not Rufus ISO-mode extraction. Use DD mode for physical flashing.

After these five gates, a separate unprivileged resource-bounded Docker container boots the exact built ISO with a newly created regular-file ext4 persistence disk. The container is disconnected from networking before execution, and the VM has no NIC. It saves notes through the API, powers off cleanly, verifies the exact previous text after two subsequent boots, and runs read-only filesystem checks. Only JSON/serial/fsck logs are uploaded, not the scratch disk. The test uses a VM-only debug shell; production boot arguments are unchanged. See [persistence acceptance](PERSISTENCE_TEST.md).

The backend-only VMs retain a 2 GiB allocation; they do not establish AI service functionality. Model inference is separately exercised on the packaged binary in the Debian builder; complete offline graphical/AI integration and hardware retesting remain required.

For graphical inspection, boot the original ISO in a desktop VM with a 2 GiB
or larger memory allocation and a graphical console. Verify the browser opens
the dashboard automatically, local source documents open, search works and
notes save. Backend markers alone do not prove Xorg/LightDM/Firefox succeeded.

## Runtime layout and offline behavior

- `live-config` creates the `user` account before LightDM and the app start.
- LightDM autologins into the `gravestone` X session. It starts Openbox, waits
  for backend health and opens Firefox ESR in kiosk mode at
  `http://127.0.0.1:8766`. Closing Firefox restarts it.
- `gravestone.service` runs as `User=user`, from `/opt/gravestone`, using:

  ```sh
  python3 -m app --data-dir /home/user/.local/share/gravestone --host 127.0.0.1 --port 8766
  ```

- The service cannot write the source system. Notes live under the user's
  home; the browser profile is also in home. No automatic cloud sync exists.
- External network auto-configuration services are masked; the provided
  interfaces file configures loopback only. The kernel uses `ip=frommedia`.
  There is no NetworkManager connection or DHCP autoconnect. Firefox telemetry,
  studies, first-run pages and captive-portal checking are disabled. This is
  **offline by default**, not a hardened network sandbox or hardware radio
  kill switch. A privileged user can change configuration.
- Swap discovery is disabled in kernel arguments and `swap.target` is masked.
  UDisks is masked, and no desktop file manager or installer is included.
  Ordinary internal volumes are not automatically mounted into the desktop
  or used as swap/persistence. Boot-medium discovery is itself restricted to
  removable storage with `live-media=removable`, rather than probing ordinary
  fixed internal disks. Some USB SSDs advertise themselves as fixed disks and
  will not boot with this filter. Device enumeration still occurs: this is not
  a forensic no-read guarantee.
- Kiosk mode/autologin are convenience features, **not** access control or a
  security boundary. Never use the default live account to protect secrets.

Useful diagnostic commands from a live console:

```sh
systemctl status gravestone.service lightdm.service --no-pager
journalctl -b -u gravestone.service -u lightdm.service --no-pager
curl --noproxy '*' --fail http://127.0.0.1:8766/api/status
cat /proc/cmdline
findmnt /home
swapon --show
```

## USB writing: destructive, deliberate, user-controlled

Verify the downloaded checksum first. A hybrid ISO can be written as a whole
image to a USB stick using a trusted image writer on your preparation machine.
**Writing an image erases the selected device and its existing partitions.**
Back up that device, confirm model/capacity/serial, unplug unrelated removable
drives, and select the complete intended USB device, not an internal disk.
Do not copy the `.iso` as an ordinary file onto a formatted USB stick.
The repository supplies **no automatic block-device writer or installer**.

Boot the USB through your firmware's one-time boot menu. Select its BIOS or
64-bit UEFI entry, with Secure Boot off. Without an explicitly provisioned
persistence volume, edits and notes are **RAM-only and lost at shutdown**.

## Optional `/home` persistence

Persistence is deliberately restricted to **removable USB storage** and
filesystem labels (`persistence-media=removable-usb persistence-storage=filesystem`).
Normal internal disks and files named `persistence` on arbitrary filesystems
are not used as persistence stores. Some external SSD/USB adapters advertise
non-removable media and will therefore not qualify. Do not relax this filter
without understanding that internal storage could then be eligible.

Provision only on a separately verified USB device, from your preparation
machine. This is a manual opt-in operation, not a boot-time formatter:

1. Back up the USB. In a trusted partition tool, identify the USB by model,
   capacity and serial. Use available space after the written ISO, if your
   image writer and partition tool support that layout, or use a second
   removable USB drive. Never resize or format an internal disk for this.
2. Create an **ext4** partition labeled exactly **`persistence`**. Creating or
   formatting that partition destroys any data previously in it. Review the
   pending device operations before applying them.
3. Mount that deliberately selected partition on the preparation machine.
   At its filesystem root create `persistence.conf` with exactly:

   ```text
   /home union
   ```

4. Flush/eject it safely. Boot Gravestone with that USB attached. The normal
   boot entry already includes `persistence`; **no volume is created or
   formatted automatically**. A label without `persistence.conf` is insufficient.
5. Confirm `/home` is using the intended persistence volume. Save a unique
   non-sensitive note, shut down cleanly, boot again, and verify the note.
   Repeat once more before trusting the device with important data.

The browser profile persists along with notes because all of `/home` persists.
This is unencrypted storage. Back it up; loss of power or USB failure can lose
notes. Persistence is not established merely because the kernel has the
`persistence` argument or the app's save button worked once. To troubleshoot,
remove the persistence drive or append `nopersistence` at the boot menu; this
starts a temporary session without using the stored home.

References: [Debian Live manual, runtime customization/persistence](https://live-team.pages.debian.net/live-manual/html/live-manual/customizing-run-time-behaviours.en.html),
[bookworm live-boot parameters](https://manpages.debian.org/bookworm/live-boot-doc/live-boot.7.en.html),
[bookworm live-build configuration](https://manpages.debian.org/bookworm/live-build/lb_config.1.en.html).
