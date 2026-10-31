# Gravestone 0.4.0 — persistence, retrieval and recovery USB test

Engineering prototype: limited original FEMA/CDC/USDA/CPSC/EPA content, worldwide country outlines, an opt-in U.S. county map-pack manager, and a CPU-only local model for keyword assistance. This is an interaction/boot test, not emergency-readiness certification. The model never authors the survival guidance shown in results.

## Release verification

Only use the matching **published prerelease** after its build and boot checks pass. A GitHub Actions artifact can exist even when a test fails; artifact existence alone is not approval to flash it. Read the release's exact build run, source commit, checksum, measured image size, and remaining test limits.

The 0.4.0 build requires:

- Application/configuration/source-integrity tests.
- Pinned model, runtime-source, license and installed-binary integrity checks.
- Actual source-built bookworm llama.cpp inference and production retrieval, not an HTTP mock. Evidence: `real-inference.json` and `AI_BUILD_PROVENANCE.json`.
- Real Debian bookworm amd64 hybrid ISO construction, with the 14,000,000,000-byte ceiling enforced.
- Offline QEMU direct-kernel, BIOS optical, UEFI optical, BIOS USB-as-disk and UEFI USB-as-disk backend boot checks, with no internal disk attached.
- Exact notebook API checks over two clean VM reboots with a disposable regular-file persistence disk. This does not qualify a physical USB.

These checks are distinct from the physical machine test below. They do not prove universal hardware compatibility or notebook persistence across shutdown.

## Download and verify

Download `gravestone-0.4.0-amd64.iso` and `gravestone-0.4.0-amd64.iso.sha256` from the matching release, not the GitHub Source code ZIP. Compare the checksum with the independently published full checksum in that release.

In Windows PowerShell, in the download directory:

```powershell
$expected = ((Get-Content .\gravestone-0.4.0-amd64.iso.sha256 -Raw).Trim() -split '\s+')[0]
if ($expected -notmatch '^[0-9a-fA-F]{64}$') { throw 'Invalid checksum file' }
$actual = (Get-FileHash .\gravestone-0.4.0-amd64.iso -Algorithm SHA256).Hash
if ($actual -ne $expected) { throw 'CHECKSUM MISMATCH: do not flash' }
"Checksum matches: $actual"
```

A matching hash checks bytes, not publisher guidance accuracy or software safety.

For this candidate, obtain the exact size, checksum, source commit and successful build link from its published release and `RELEASE_PROVENANCE.json`. Earlier image measurements in `docs/VALIDATION.md` do not validate a newer image. Separate controlled-reader Firefox ESR kiosk acceptance passed 24/24 assertions. The existing 0.3.0 image also passed exact notebook API checks over two clean VM reboots; newer images require their own workflow evidence. Physical USB/AI retesting and physical two-reboot persistence remain unverified until performed on the intended image/device.

## Flash from Windows

1. Back up anything on the selected 16 GB USB: **the entire selected drive will be erased**, including any previously provisioned persistence. Unplug unrelated removable drives. Identify the intended device by model and capacity.
2. Get Rufus from its official site, https://rufus.ie/ . Do not use an advertising look-alike download site.
3. Select the intended USB under **Device** and this release's ISO under **Boot selection**. Keep persistence disabled for this initial disposable test.
4. Click **Start**. Choose **DD Image mode**, not ISO Image mode. The original prototype's EFI loader failed on extracted partitioned-FAT layouts; changing GPT to MBR was not a fix. DD preserves the tested hybrid layout. Read the destructive-device warning before accepting.
5. Wait for writing to complete, then safely eject the USB. If Windows asks to format an unrecognized partition, **cancel**; do not reformat the Linux media.

**Rufus persistence-slider caveat:** the ISO/DD prompt is offered only when the slider is zero in the inspected upstream source. A nonzero slider takes a different, extracted-image path. The user reported the same GRUB failure with 0.4.0 and 4 GB persistence enabled; do not repeatedly erase the drive or ask them to choose a DD option that this path does not offer. See [the diagnosis and separate acceptance gates](RUFUS_PERSISTENCE.md). The existing VM persistence test does not validate Rufus's full-root persistence configuration.

No remote automation should select, format, or write a physical device on your behalf.

## Boot the physical computer

1. Save work and shut down the target computer. Connect the USB.
2. Use its one-time firmware boot menu and choose the USB's x86-64 UEFI entry. The correct menu key depends on the manufacturer.
3. Secure Boot remains unsupported. Before changing firmware settings on a BitLocker/device-encrypted Windows PC, ensure its recovery key is accessible to you offline. Never post that key in chat. Do not clear the TPM or change storage-controller settings.
4. The live entry should start automatically into **Gravestone**, with top-center search and six topic tiles as the main screen. No internal-disk installation is supplied.
5. Use a keyboard/mouse and display. Networking is intentionally not configured. ARM/Apple Silicon, firmware-locked computers, unusual graphics hardware, and fixed-advertising USB SSDs remain outside the support claim.

For the desktop plus AI, plan 4 GiB total RAM and 2 GiB available for AI. These are planning targets, not measured universal minima. Older CPUs may be slow; model failure must leave the library and keyword search usable.

## Interaction checklist

- [ ] Boot menu recognizes the USB and the live entry starts.
- [ ] Full-screen **Gravestone** appears without a login or terminal command.
- [ ] Text, mouse, keyboard, scrolling and screen resolution are usable.
- [ ] Type a question such as `Find safe drinking water guidance`; results show publisher, page and unverified-preview warning, not a generated answer.
- [ ] After model startup, distinguish an available model from accepted new keywords: keyword-only is correct when no additions survive validation. If unavailable/slow, verify the honest keyword fallback still returns source matches. Record which mode was actually observed.
- [ ] Open a result with **Read original in full**. Verify the actual PDF renders and the large **Back to library** button remains visible and clickable, without using a keyboard shortcut.
- [ ] Close the reader and verify the original question/results and scroll position remain usable.
- [ ] Enter a disposable **unsaved** notebook draft, open/close a PDF, and confirm the draft is preserved. Opening a document must not silently save or discard it.
- [ ] Open and return from both original FEMA and CDC PDFs from the library.
- [ ] Search for a topic outside the collection; it reports limited coverage/no matching sources rather than inventing guidance.
- [ ] Requested coverage is visibly labeled **not installed**.
- [ ] Atlas responds to zoom/pan/coordinates. Default geography is country outlines; road/water geometry requires user-installed county packs. There is no route calculation or potable-water claim.
- [ ] Four palettes are available: Amber, Red, Green and Contrast. Publisher PDF colors remain unchanged.
- [ ] PDF Next/Previous change the displayed physical page; Copy matches that page; zoom changes its visible size. A page still rendering must not enable Copy.
- [ ] Notebook saves and reads back during the current session.
- [ ] Repeat core interactions with Ethernet disconnected and no Wi-Fi configuration.
- [ ] Shut down cleanly. A brief press of the physical power button may request shutdown; do not hold it to cut power during a save.
- [ ] Removing the USB allows the computer to return to its original installed OS.

**Expected limitation:** without deliberately provisioning persistent storage, notes and browser changes are RAM-only and disappear at shutdown. A successful save is not a durability test. Follow `docs/BOOT.md` for explicit persistence provisioning and verify through two clean reboots before trusting important notes.

Report computer model, RAM, BIOS/UEFI choice, writer mode, last visible screen/error and failed checklist item. Exclude recovery keys, private notes and other secrets from photographs.
