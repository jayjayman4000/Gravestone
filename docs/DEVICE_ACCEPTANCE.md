# Physical-device acceptance and persistence record

This records hardware observations, not safety-source guidance. Software, VM and filesystem tests do not establish physical USB reliability. Use disposable test notes until every relevant gate passes.

## Identify the exact test image and hardware

- Release/tag and downloaded ISO SHA-256:
- Computer model, CPU architecture and RAM (no serial number required):
- USB make/capacity (do not publish private identifiers):
- Firmware mode: x86-64 UEFI or BIOS; Secure Boot remains unsupported:
- Writer/version and **DD Image mode**, not ISO extraction:
- Display resolution and input devices:

Record existing results as observations, not assumptions. A successful earlier release boot does not test a newer image.

## Initial disposable offline session

1. Save other work. Boot through the firmware's one-time boot menu. Do not change internal-storage/controller settings or clear TPM state. If firmware changes are necessary on an encrypted Windows PC, keep its recovery information available privately; never post keys.
2. Leave Ethernet disconnected and do not configure Wi-Fi. Confirm Gravestone opens automatically without a login or terminal command.
3. Check Amber, Red, Green and Contrast; text, buttons, input focus and Back controls must remain usable at the actual resolution.
4. Search for a phrase copied from an installed source and a topic outside the collection. Record the result mode and pages. A no-result message must not invent guidance. Model startup/failure must not prevent ordinary library browsing or keyword-only fallback.
5. Open a FEMA document, change physical page, zoom and Copy. Compare the selectable extracted text with the displayed physical page. Copy is an unverified transcription aid, not a substitute for figures or warnings.
6. Close the reader, open a CDC document and return. Verify one unchanged kiosk workspace, visible Back, preserved question/results and a disposable unsaved draft.
7. Open Atlas and use pan/zoom. Preinstalled country outlines are not detailed local maps. If preparing a county pack, use the explicit preparation/import controls; return to an offline session before testing its installed geometry.
8. Save and read back a disposable notebook note in the current session. **This alone does not prove reboot persistence.**
9. Shut down cleanly. Removing the USB should leave the computer able to start its existing OS. No internal-disk installation or automatic physical writer is supplied.

## Two-clean-reboot persistence acceptance

Persistence is optional and deliberately restricted to removable USB storage. Without a provisioned volume, losing notes on shutdown is expected. See `BOOT.md` for the existing ext4 `persistence` label and `/home union` requirements.

Preparing/formatting a persistence partition destroys data in the selected target. Back up first; identify the USB by make/capacity in a trusted partition tool on the preparation computer. Do not select an internal disk, resize the running live medium, or accept a Windows format prompt for existing Linux partitions. No remote agent should select the physical device for you.

Use the same image and the same deliberately provisioned USB for all three sessions:

- **Session A:** save a unique non-sensitive note, e.g. `Persistence acceptance A — <your date>`. Record its exact text locally. If testing maps, record the installed county/layers and their source/data hashes. Select a palette. Shut down cleanly; wait for shutdown before removing power.
- **Session B (first clean reboot):** before editing, verify the entire note matches exactly. Verify the palette and installed pack list; open actual map geometry while networking remains disconnected. Append a second disposable marker, save and read it back, then shut down cleanly.
- **Session C (second clean reboot):** verify both note markers and installed geometry again before editing. Record pass/fail for each item, not merely “it booted.”

| Gate | Session A | First reboot / B | Second reboot / C |
| --- | --- | --- | --- |
| Exact saved note | | | |
| Selected palette | | | |
| Installed pack IDs and hashes | | | |
| Actual map renders offline | | | |
| Original PDFs/search usable | | | |
| Clean shutdown | | | |

A VM using a newly created persistence image tests the software path only; it does not qualify this physical stick, its power-loss behavior or flash lifetime. No finite test proves immunity to corruption. Back up important notes and packs separately.

## Backup and recovery acceptance

Use the [documented backup tool](BACKUP_RECOVERY.md) included in versions carrying `app.backup`; the already released 0.3.0 image does not contain this new module. Run `python3 -m app.backup --help` from the source application directory on the preparation machine or a future image that includes it. Archives may contain private, unencrypted notes; keep them off public repositories/releases and use trusted storage.

1. Back up only the explicitly selected Gravestone data directory, not an entire home directory or browser profile.
2. Restore into a **nonexistent scratch data-directory path whose parent exists** first. Never test recovery by overwriting the only live copy.
3. Verify exact saved-note bytes and each original/derived map hash. Start a separate backend on an automatically selected loopback port with that scratch directory; do not replace the running service for the test.
4. Repeat browsing with networking unavailable. A hash-verified backup is not proven usable until the restored application opens the data.
5. Keep the original archive and live data until the restored copy passes. Recovery from browser preferences is outside a notes/map archive unless explicitly documented.

## Report results without secrets

Return the release/hash, computer model/RAM, firmware mode, writer mode, last visible error/screen and failed checklist item. Do not include private notebook contents, authentication information, recovery keys, or a device's personal data in screenshots. Mark untested items **not tested**, not passed.
