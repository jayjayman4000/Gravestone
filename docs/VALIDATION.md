# Prototype validation record

This records engineering observations, not survival guidance or a claim of emergency readiness.

## Image under test

- Release: `v0.1.0-alpha.1`.
- Image source commit: `620a2384a37a08f414951d1345736a7a4449fdba`.
- SHA-256: `a0f0195126ddceb5df2401ff39f7e8855f65af53d2fed924d4ec145241e40f15`.
- Build/run evidence: https://github.com/jayjayman4000/Gravestone/actions/runs/41023338966

## Verified before physical test

- Application, configuration and content-integrity suite passed: 19 tests.
- Real ISO built; direct-kernel and unchanged whole-ISO BIOS/UEFI backend boot checks passed.
- Downloaded image checksum matched. These checks alone did not establish graphical or physical USB behavior.

## Physical test observations

- User initially reported Rufus ISO mode and showed the plain GRUB prompt; later photograph showed `error: no such device: /.disk/info.`.
- Investigation reproduced this error with the original EFI loader on partitioned GPT/FAT32 and MBR/FAT32 fixtures, despite the marker file being present. The raw hybrid image attached as USB storage reached the Linux kernel. These fixtures were not an actual Rufus execution.
- User was instructed to rewrite the same image in Rufus DD mode.
- User subsequently reported that the drive booted and supplied a photograph showing the full-screen Gravestone dashboard on a physical laptop. The dashboard shows its local-service indicator, `Prototype online`, both starter document cards and the persistence warning.
- **Physical USB boot reaching the graphical dashboard is confirmed by user report and photograph on this machine.** The computer model, firmware mode and final writer mode were not explicitly reported, so no broader compatibility claim is made.
- The user's photograph is not included in the public project; it contains their physical surroundings.

## Physical interaction defect: document navigation

The user opened the original FEMA PDF successfully, then could not find a visible way back. Their photograph shows the native Firefox PDF toolbar without the Gravestone navigation shell. Application code opens originals and search hits with `target="_blank"`; Firefox kiosk mode hides the browser's tab/navigation controls. This is a confirmed usability defect, not a document-content failure. `Ctrl+W` closes the new PDF tab as a temporary recovery path. Acceptance for the fix: an obvious, persistent, pointer-accessible return control that works while viewing originals, without requiring a keyboard shortcut and without losing unsaved notebook text. Physical retest remains pending.

## Still unverified on the physical machine

- Keyboard, mouse/trackpad, scrolling and all controls.
- Opening and returning from both original PDFs.
- Search result behavior and map interactions.
- Notebook saving and reading back in the current session.
- Offline use with network disconnected.
- Clean shutdown and return to the installed OS.
- Provisioned persistent USB storage and note survival across two clean reboots.

Do not infer successful interactions merely from the dashboard being visible. Treat notes as disposable until restart persistence is deliberately provisioned and demonstrated.

## 0.2.0 command-console verification (application, not image)

- Local Python/Node-backed regression suite after the packaging compatibility fix: 47 tests run, 45 passed and 2 installed-model/inference tests explicitly skipped pending build artifacts.
- Browser QA used Debian bookworm Firefox ESR 153.6.0esr, non-headless under Xvfb with `--kiosk`, against the running application. This is the recipe's browser family/distribution, not a booted ISO or physical test.
- Command search returned original-source previews with explicit keyword-only fallback while no model server was installed on the QA host. This is not evidence of working model inference.
- Both FEMA and CDC originals visibly rendered through Firefox PDF.js. The large Back to library button remained visible, one tab remained open, closing removed the PDF frame, and the exact unsaved notebook draft remained marked unsaved. Parent independently inspected both screenshots and the structured result record.
- The isolated browser container required a sandbox override; no browser-hardening claim is inferred. No notebook was saved and no private notes were published.
- Parent preserved the browser evidence with a SHA-256 manifest under `/home/jayjayman4000/gravestone-test-evidence/0.2.0-command-console/`, outside the public checkout. The original temporary copy remains under `/tmp/gravestone-firefox-qa/`. Neither local path is a public release asset.

## 0.2.0 initial build failure and targeted reproduction

- Build run https://github.com/jayjayman4000/Gravestone/actions/runs/41080556859 failed before runtime compilation or ISO construction.
- Exact cause: the builder's Debian Python 3.11.2 lacks the `TarFile.extractall(filter=...)` parameter. No ISO was produced.
- The replacement extractor prevalidates the complete archive and permits only regular files/directories below the pinned commit root. It rejects traversal, unexpected roots, links, devices and duplicate paths; it does not import special permissions.
- Regression tests and full-byte comparisons of all 3,976 original source files passed inside the actual `debian:bookworm` container on Python 3.11.2 with the filter API confirmed absent. This proves the failed extraction seam is fixed, not that the remaining compilation, inference or image boot steps pass.
## 0.2.0 replacement build and image verification

- Successful build: https://github.com/jayjayman4000/Gravestone/actions/runs/41081405816 ; exact image source commit `943ea081fe7e75d933205ccc73b5b0efe7041977`.
- ISO: `gravestone-0.2.0-amd64.iso`, 1,194,983,424 bytes; SHA-256 `918e31863262ea4a309b1f6deb343b590131f9b90def3f39af5c4dbdb175e16e`. Full checksum matched after artifact download.
- All six installed-package/inference tests passed in the actual bookworm builder without skips. The real Qwen model and source-built runtime produced JSON, and production `command_search` returned source excerpts in AI-assisted mode (3.802 seconds in that runner; not a hardware latency guarantee).
- Model inference is not a relevance guarantee: this probe yielded no additional accepted keywords beyond the user's terms. Keyword ranking remains basic and can return broad or unrelated previews. No generated answer is shown; open the full publisher document.
- Direct-kernel live-root/backend, whole-image BIOS optical, UEFI optical and UEFI USB mass-storage backend checks passed with no network adapter or internal disk. Serial logs contain their required readiness markers. BIOS USB-as-disk, visible kiosk inside this exact ISO, physical 0.2.0 hardware/AI use, and persistence are not implied by these checks.
- A read-only audit of the downloaded ISO independently matched the embedded Qwen weights, runtime executable, complete runtime source archive, all pinned AI license/model-card files, and both publisher-original PDFs against their recorded digests. It also confirmed the command/reader shell and enabled loopback-only AI service in the image.
- Release provenance, packaged runtime build provenance, actual inference evidence, Debian package manifest, checksum and build/boot logs accompany the test candidate. Source commit remains distinct from this later documentation update.
- Physical reflash testing should follow `docs/USB_TEST.md`, using Rufus DD mode. Notes remain disposable until deliberate persistence provisioning and two clean reboot checks.

## 0.3.0 approved civilian kiosk and controlled-reader source

- Application/source suite: 76 tests, 74 passed and two installed-model tests skipped locally. The image builder must run the actual installed model/runtime checks without those skips before release.
- Debian bookworm Firefox ESR 153.6.0esr, non-headless kiosk under Xvfb: 24/24 controlled-reader assertions passed at an actual 1280×800 content viewport. Dedicated backend and container were removed; shared services remained running.
- Confirmed one nonblank app-owned canvas and zero iframes; FEMA physical page 7/8 distinct pixels, exact displayed-page Copy, literal 125% zoom with 765px CSS/backing width, stable copy after scroll/rapid navigation, preserved unsaved draft/library focus, and CDC page 1 rendering. Original PDF hashes remained unchanged.
- Actual local PDF.js worker confirmed in Firefox's content process, with `worker-src 'self'` and `font-src 'self' blob: data:`. No application module/worker/CSP load failures observed. The container used `MOZ_DISABLE_CONTENT_SANDBOX=1`; this is not a production-sandbox or whole-image-boot claim.
- Browser evidence stays outside the public checkout at `/home/jayjayman4000/gravestone-test-evidence/reader-controlled-firefox/`. The upstream PDF.js resources and all seven publisher originals have byte-integrity tests; extraction text remains an unverified search aid.
- The release smoke runner now additionally tests BIOS USB-as-disk, separately from BIOS/UEFI optical and UEFI USB. Its argument-assembly regression was observed failing before implementation and passing afterward. These contract tests do not establish that the new ISO boots; actual workflow evidence and an embedded-payload audit are required.
- The new source includes seven publisher documents, not a comprehensive survival library. Road/water county packs remain opt-in preparation downloads/imports and are not bundled regional map coverage.

## 0.3.0 published image verification

- Published engineering test candidate: [v0.3.0-alpha.1](https://github.com/jayjayman4000/Gravestone/releases/tag/v0.3.0-alpha.1).
- Exact image source commit: `0770eef73986271985e46a4831dfe25b5dd8d8f8`; successful [build run 41141364319](https://github.com/jayjayman4000/Gravestone/actions/runs/41141364319). Later documentation commits do not change the image source/tag.
- ISO `gravestone-0.3.0-amd64.iso`: **1,199,702,016 bytes**; SHA-256 `63be2439540ce02b5821791ea93e4cda5669f2b8adcd7a7d3d96fe921accc001`. Downloaded ISO checksum matched.
- All six installed-package/inference tests passed without skips in the actual bookworm builder. Production retrieval completed in AI-assisted mode in 2.254 seconds on that runner; no target-CPU performance or ranking guarantee follows. No additional model-proposed terms were accepted in this probe.
- All five VM gates passed: direct-kernel live-root/backend, BIOS optical, UEFI optical, BIOS USB mass storage and UEFI USB mass storage. Both USB gates had no CD-ROM fallback; no VM had an internal disk or network adapter.
- Read-only payload audit passed **275 checks**, including all **247 committed app/content/AI files**, seven original PDFs and derivatives, model weights, runtime executable, corresponding source archive and original AI licenses/model card. Actual enabled backend/AI service links were checked.
- All nine release assets were read back with uploaded state, exact size and SHA-256 matching local bytes, before and after publication. Published tag resolves to the exact image source commit above. Runtime provenance, actual inference evidence, package inventory, payload audit, checksum, USB checklist and build/boot logs accompany the ISO.
- Remaining gates: visible kiosk interaction inside this exact booted ISO, physical USB graphical/AI retest, broader hardware/sandbox compatibility and two-clean-reboot notebook persistence. Separate Firefox acceptance and VM backend markers do not establish those gates. Use Rufus DD mode; writing erases the selected device and any prior persistence.

## Next hardening source — not yet a published image

- Current integrated source passed **108 tests with no skips** when explicitly enabling hash-verified installed runtime/model checks and real Census map recovery. Ordinary lightweight tests retain the three explicit opt-in skips; a skipped integration test is not passing integration evidence.
- The unmodified released 0.3.0 ISO passed actual notebook API persistence over two clean VM reboots: three unique boot IDs, exact multiline UTF-8 notes before/after, clean kernel poweroff/QEMU exit 0 and read-only ext4 checks after each session. This direct-kernel/no-NIC emulated-USB test does not establish physical stick durability, firmware or graphical interaction. New image builds also gate on this protocol for their exact ISO checksum.
- Four complete publisher PDFs added **274 physical pages / 8,016,554 original bytes**; checkout total **11 PDFs / 365 pages**. Existing seven originals/derivatives and manifest records remained unchanged. CERT coverage requires training and is not standalone medical certification. EPA/CDC historical editions, extraction defects and an original unit discrepancy remain explicitly documented, not repaired. Equipment-specific power and solar documents remain unadmitted due rights/retrieval gaps.
- The fixed original-seven corpus has 16 development-visible relevance cases. Top-1 judged hits improved 9/16 to 12/16; top-3 15/16 to 16/16; MRR@10 0.739583 to 0.864583. All 158 returned previews per run are exact physical-page substrings. This is neither held-out evaluation nor validation of the expanded corpus/AI usefulness. The parent reran the benchmark with identical metrics.
- An available model with zero accepted additional keywords now truthfully returns keyword-only mode and an explicit message. Actual runtime/model testing reproduced the old unconditional AI-assisted test assertion failure; the integration contract was corrected to require a real available response and the mode appropriate to the actual accepted additions. All six installed/inference tests then passed, followed by the full no-skip suite.
- New `python3 -m app.backup` provides bounded, unencrypted saved-note/map export and verified recovery to a nonexistent target only. Corrupt/unsafe archives, symlinks, overwrite attempts and filesystem replacement races are tested. It does not back up browser profiles or unsaved drafts; the CLI must be used while the app/map jobs are stopped.
- Real official Arlington roads/water data survived three separate scratch server processes and byte-exact backup/recovery: 2,524 road features, 32 water features and seven preserved file hashes. Python-level network guards were self-tested; kernel network namespaces were unavailable, so this is not a physical network-disconnection claim. Parent independently reran both map-recovery checks successfully.
- Durable evidence remains outside the public checkout under `gravestone-test-evidence/{persistence-reboots,library-expansion,search-quality,map-backup-recovery,next-hardening}/`. No private notebooks, physical devices or shared services were modified. Physical tests follow `docs/DEVICE_ACCEPTANCE.md`; current-image claims remain separate from these source additions.
