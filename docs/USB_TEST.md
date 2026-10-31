# Gravestone 0.4.1 — extracted USB boot and persistence test

Engineering prototype: limited original FEMA/CDC/USDA/CPSC/EPA content, worldwide country outlines, an opt-in U.S. county map-pack manager, and a CPU-only local model for keyword assistance. This is an interaction/boot test, not emergency-readiness certification. The model never authors the survival guidance shown in results.

## Release verification

Only use the matching **published prerelease** after its build and boot checks pass. A GitHub Actions artifact can exist even when a test fails; artifact existence alone is not approval to flash it. Read the release's exact build run, source commit, checksum, measured image size, and remaining test limits.

The 0.4.1 build requires:

- Application/configuration/source-integrity tests.
- Pinned model, runtime-source, license and installed-binary integrity checks.
- Actual source-built bookworm llama.cpp inference and production retrieval, not an HTTP mock. Evidence: `real-inference.json` and `AI_BUILD_PROVENANCE.json`.
- Real Debian bookworm amd64 hybrid ISO construction, with the 14,000,000,000-byte ceiling enforced.
- Offline QEMU direct-kernel, BIOS optical, UEFI optical, BIOS USB-as-disk and UEFI USB-as-disk backend boot checks, with no internal disk attached.
- Exact notebook API checks over two clean VM reboots with a disposable regular-file persistence disk.
- Patched-helper and actual shipped-loader UEFI discovery on GPT/FAT32 and MBR/FAT32.
- Three OVMF firmware boots of an extracted GPT/FAT32 USB with a 4 GiB ext4 root-union persistence partition on the same emulated removable disk: exact saved UTF-8 text, unique boot IDs, clean poweroff and read-only filesystem checks. This is a constructed Rufus-like layout, not execution of Rufus or qualification of a physical USB.

These checks are distinct from the physical machine test below. They do not prove universal hardware compatibility or notebook persistence across shutdown.

## Download and verify

Download `gravestone-0.4.1-amd64.iso` and `gravestone-0.4.1-amd64.iso.sha256` from the matching release, not the GitHub Source code ZIP. Compare the checksum with the independently published full checksum in that release.

In Windows PowerShell, in the download directory:

```powershell
$expected = ((Get-Content .\gravestone-0.4.1-amd64.iso.sha256 -Raw).Trim() -split '\s+')[0]
if ($expected -notmatch '^[0-9a-fA-F]{64}$') { throw 'Invalid checksum file' }
$actual = (Get-FileHash .\gravestone-0.4.1-amd64.iso -Algorithm SHA256).Hash
if ($actual -ne $expected) { throw 'CHECKSUM MISMATCH: do not flash' }
"Checksum matches: $actual"
```

A matching hash checks bytes, not publisher guidance accuracy or software safety.

The exact 0.4.1 ISO passed [build run 41207842357](https://github.com/jayjayman4000/Gravestone/actions/runs/41207842357), including both persistence protocols. Source commit: `f02eddaca433b840189d88867eec1f40ab40643d`. ISO: **1,206,779,904 bytes**, SHA-256 `e405bb00ff1cea3f0a1f56818f42332d1994dd2629b24a99adad146cc292b18f`. Downloaded bytes matched; the embedded payload passed 299 checks. Separate Firefox source tests are not graphical testing inside this exact ISO. Physical USB/AI interaction and physical two-reboot persistence remain unverified.

## Flash from Windows

1. Back up anything on the selected 16 GB USB: **the entire selected drive will be erased**, including any previously provisioned persistence. Unplug unrelated removable drives. Identify the intended device by model and capacity.
2. Get Rufus from its official site, https://rufus.ie/ . Do not use an advertising look-alike download site.
3. Select the intended USB under **Device** and **`gravestone-0.4.1-amd64.iso`** under **Boot selection**. For the persistence workflow under test, select **GPT / UEFI (non-CSM)**, FAT32, and set the persistence slider to **4 GB**. The constructed firmware/persistence acceptance used a 4 GiB ext4 partition; actual Rufus version/settings still require physical confirmation. Do not select the old 0.4.0 ISO.
4. Click **Start** after reviewing the destructive-device warning. With persistence enabled, the inspected Rufus source bypasses the ISO/DD prompt: **do not wait for a DD choice**. The extracted-layout loader failure is corrected in 0.4.1. BIOS and MBR root-persistence are not established by the GPT/UEFI persistence test.
5. Wait for writing to complete, then safely eject the USB. If Windows asks to format an unrecognized partition, **cancel**; do not reformat the Linux media.

**Alternative raw-image test:** set the slider to zero, choose DD Image mode when offered, and provision persistence separately as described in `BOOT.md`. Raw/DD firmware gates remain passing. Do not combine those directions with the nonzero-slider workflow above. See [the diagnosis and exact acceptance boundary](RUFUS_PERSISTENCE.md). Never reflash merely because an old instruction describes a different writer path.

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
- [ ] For a persistent USB, save a unique disposable note, shut down cleanly, boot again and verify it exactly. Update it, then repeat the clean shutdown/boot and verify the complete updated text. Until both checks pass on this USB, do not trust it with important notes.
- [ ] Repeat core interactions with Ethernet disconnected and no Wi-Fi configuration.
- [ ] Shut down cleanly. A brief press of the physical power button may request shutdown; do not hold it to cut power during a save.
- [ ] Removing the USB allows the computer to return to its original installed OS.

**Expected limitation:** without deliberately provisioning persistent storage, notes and browser changes are RAM-only and disappear at shutdown. A successful save is not a durability test. Follow `docs/BOOT.md` for explicit persistence provisioning and verify through two clean reboots before trusting important notes.

Report computer model, RAM, BIOS/UEFI choice, writer mode, last visible screen/error and failed checklist item. Exclude recovery keys, private notes and other secrets from photographs.
