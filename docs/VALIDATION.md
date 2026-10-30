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
- The replacement build, packaged inference and ISO boot results must be recorded separately when available.
