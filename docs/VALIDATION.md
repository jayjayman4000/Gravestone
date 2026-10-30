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
