# Gravestone 0.4.2 candidate — USB test checklist

**Build/boot/artifact acceptance is pending when this source checklist is written.** A filename or a successful artifact upload alone is not approval to flash. Use only the matching verified engineering prerelease, its exact source commit, checksum and recorded completed checks. This is limited-source experimental software, not an emergency-ready reference.

## Candidate changes and limits

- Wider responsive homepage, refreshed real battery/storage readings, stricter source-only search and separate collapsed partial matches.
- Twelve archived publisher PDFs, including the historical War Department TM 9-1803A engine manual. Historical procedures are vehicle-specific, contain obsolete practices and unverified OCR, and have not received qualified mechanical safety review.
- The manual's editorial page-role metadata ranks equally covered procedural pages before introductory/reference leaves. Original text, figures and cautions are unchanged; read the entire applicable scope and warnings.
- AI overview is **withheld by default** because substantive model output failed usefulness and condition-preservation review. Exact evidence IDs are not semantic approval. Original PDF reading, keyword search and the notebook do not depend on overviews. `GRAVESTONE_EXPERIMENTAL_OVERVIEW=1` is an engineering-only opt-in, not enabled in the image.
- Compatible amd64 PCs only; Secure Boot unsupported. ARM/Apple Silicon, 32-bit UEFI and arbitrary hardware compatibility are not established.

## Before writing

1. Download `gravestone-0.4.2-amd64.iso` and `gravestone-0.4.2-amd64.iso.sha256` from the matching verified prerelease, not the Source code ZIP. Check that the release identifies successful firmware/raw-USB and persistence gates for this exact image.
2. Independently compare the full ISO SHA-256 with the release and checksum file. On PowerShell:

   ```powershell
   $expected = ((Get-Content .\gravestone-0.4.2-amd64.iso.sha256 -Raw).Trim() -split '\s+')[0]
   if ($expected -cnotmatch '^[0-9a-f]{64}$') { throw 'Malformed expected SHA-256' }
   $actual = (Get-FileHash .\gravestone-0.4.2-amd64.iso -Algorithm SHA256).Hash
   if ($actual -ine $expected) { throw 'ISO checksum mismatch — do not flash' }
   ```

3. Back up the entire intended USB, including existing notes. **Writing the image erases the selected device and its partitions.** Disconnect unrelated removable drives, identify the intended USB by model/capacity/serial and never select an internal disk. No automatic physical-device writer is supplied.

## Writer and boot path

- Use the official Rufus download at <https://rufus.ie/> and record its exact version/settings.
- For the extracted-persistence path, proceed only when this exact image passed the constructed GPT/UEFI same-USB root-union gate. Select GPT / UEFI (non-CSM), FAT32 and 4 GB persistence. The VM fixture uses a 4 GiB ext4 partition; it is a constructed equivalent, not actual Rufus execution or physical compatibility proof. A nonzero persistence slider bypasses Rufus's ISO/DD prompt. Do not wait for a DD choice or infer MBR/BIOS root persistence from GPT/UEFI success.
- Alternatively, a zero-slider raw/DD write uses the hybrid image layout. Manual removable `/home` persistence is a separate procedure in [BOOT.md](BOOT.md#optional-home-persistence); it is not provisioned automatically.
- Boot the intended USB from the firmware one-time menu with Secure Boot off. Do not clear the TPM or change internal storage mode. Keep any BitLocker recovery precautions on your own device; never share recovery keys in chat.
- Cancel Windows prompts to format Linux partitions. Safely eject after writing.

## Physical acceptance to record

1. Record ISO checksum, computer model, BIOS/UEFI mode, Rufus version and exact writing/persistence settings.
2. Confirm automatic visible kiosk startup, usable widescreen layout/palettes and honest battery/storage indicators.
3. Search `engine repair`; open an original historical-manual page, navigate/zoom/Copy and return using the visible Back control. Treat excerpts as unverified extraction, not repair advice.
4. Confirm the optional overview request explains that it is withheld. No generated advice should appear in the default image.
5. Save a unique non-sensitive notebook note. If persistence was deliberately provisioned, shut down cleanly and verify **the exact saved text after each of two clean reboots**. A save in one session or VM evidence is not physical-stick durability.
6. Check installed map access separately; no downloaded region or usable detailed map is implied by the dashboard. Preserve backups before any reflash.

Report failures against the exact image and transport. A bare GRUB prompt is not a reason to erase again without inspecting the writing mode and loader evidence.
