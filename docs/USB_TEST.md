# Gravestone 0.1.0 — first physical USB test

Engineering prototype: limited starter content, worldwide country outlines, no AI model. This is a UI/boot test, not an emergency-readiness certification.

## What has actually passed

- Local application/configuration/content integrity suite: 19 tests.
- GitHub build: https://github.com/jayjayman4000/Gravestone/actions/runs/41023338966
- Real Debian bookworm amd64 hybrid ISO construction.
- QEMU direct-kernel live-root, whole-ISO BIOS, and whole-ISO UEFI backend boot checks, with network disabled and no internal disk attached.
- Image SHA-256 checked after downloading the build artifact.

Those checks do not prove graphical kiosk behavior, physical USB compatibility, or persistence across power cycles. This first test is intended to exercise those boundaries.

## Download and verify

Download `gravestone-0.1.0-amd64.iso` and its `.sha256` file from the matching GitHub prerelease, not the GitHub Source code ZIP. Expected ISO size is **535822336 bytes**.

Expected SHA-256:

```text
a0f0195126ddceb5df2401ff39f7e8855f65af53d2fed924d4ec145241e40f15
```

In Windows PowerShell, in the download directory:

```powershell
Get-FileHash .\gravestone-0.1.0-amd64.iso -Algorithm SHA256
```

Compare the full hash, case-insensitively. Do not flash a mismatching file.

## Flash from Windows

1. Back up anything on the selected 16 GB USB: **the entire selected drive will be erased**. Unplug unrelated removable drives. Identify the intended device by model and capacity.
2. Get Rufus from its official site, https://rufus.ie/ . Do not use an advertising look-alike download site.
3. In Rufus select the intended USB under **Device**. Select the downloaded Gravestone ISO under **Boot selection**. Keep persistence disabled for this initial disposable boot/UI test.
4. Click **Start**. If asked to choose between ISO Image mode and DD Image mode, choose **DD Image mode** so the tested hybrid layout is written directly. Read the destructive-device warning before accepting.
5. Wait until writing is complete and Rufus reports ready. Close it and eject the USB safely. If Windows asks to format an unrecognized partition afterward, **cancel**; do not reformat the Linux media.

No remote automation from Gravestone should select, format, or write a physical device on your behalf.

## Boot the physical computer

1. Save work and shut down the target computer. Connect the USB.
2. Use that computer's one-time firmware boot menu and choose the USB's x86-64 UEFI entry. The menu key depends on the manufacturer; do not guess firmware changes based on a different PC.
3. This prototype does **not** support Secure Boot. If firmware rejects the image, stop and identify the exact error. Before changing Secure Boot settings on a BitLocker/device-encrypted Windows PC, ensure its recovery key is available to you offline; firmware changes can trigger recovery. Never post that key in chat. Do not clear the TPM or change internal disk/storage-controller settings.
4. The Gravestone live entry should start automatically. The intended result is the full-screen dashboard, without installing Linux on the internal disk.
5. Start with keyboard/mouse and a display. Networking is intentionally not configured. Touch, unusual graphics hardware, firmware-locked machines, ARM/Apple Silicon and fixed-advertising USB SSDs are outside this first test's support claim.

## Test checklist

- [ ] Boot menu recognizes the stick and the live entry starts.
- [ ] Full-screen Gravestone dashboard appears without a login or terminal command.
- [ ] Text, mouse, keyboard and screen resolution are usable.
- [ ] Library opens the original FEMA PDF and returns to the dashboard. Browser Back or Alt+Left may be used if needed.
- [ ] CDC PDF opens separately and remains readable offline.
- [ ] Search for `water` finds source documents with the unverified-extraction warning.
- [ ] Atlas shows country outlines and responds to zoom/pan/coordinate controls. It is not a road-navigation map.
- [ ] Notebook saves and reloads during the same session.
- [ ] Repeat essential browsing with Ethernet disconnected and no Wi-Fi configuration.
- [ ] Shut down cleanly; if the interface offers no power control, try a brief press of the computer's physical power button and wait for normal shutdown. Do not hold the button to cut power during a save.
- [ ] Removing the USB returns the computer to its original installed OS.

**Expected limitation:** without deliberately provisioning persistent storage, notebook edits and browser changes are in RAM and disappear when this live system shuts down. That is not a successful durability test. Provision and test persistence separately using `docs/BOOT.md`; first confirm the kiosk works on the target hardware.

Report the computer model, BIOS/UEFI choice, whether Secure Boot was enabled, the last visible screen/error, and the failed checklist item. Screenshots/photos are useful; exclude recovery keys, private notes and other secrets.
