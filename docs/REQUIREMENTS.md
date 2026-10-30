# Product requirements — Gravestone

This is engineering documentation, not survival guidance.

## Confirmed scope

The owner named the project **Gravestone**. Its purpose is to make reliable information available after an owner dies or is otherwise absent; it is for all Gravestone users, not a simulated personality of one individual.

1. Primarily United States preparedness content, covering both everyday disasters and major disruptions. Completeness must be assessed by documented coverage, not file count.
2. Original survival information must come directly from identified external sources, copied without substantive AI rewriting. Preserve original bytes, figures, warnings, and context.
3. Keep ordinary files and an Obsidian-compatible library structure available underneath the UI. No mandatory proprietary plugin, login, license activation, or cloud account.
4. Custom survival-focused dashboard with a map-centric visual direction inspired by God's Eye View, but no dependency on that application's hosted services.
5. Bootable Linux USB, copyable through a documented image-writing process. Initial target amd64 PCs; not universal hardware compatibility.
6. Advertised 16 GB USB is the primary capacity constraint. Initial release image gate: 14,000,000,000 bytes maximum. Writable capacity and packaged content need separate accounting.
7. Worldwide reference map with selective higher-detail U.S. regions later. Worldwide detailed roads/buildings/satellite imagery are not promised on the base drive.
8. Local AI is optional and deferred until core retrieval works. Failure to run AI must not prevent library or map use.
9. Durable notebook. A live-session save must not be described as restart-persistent unless a persistent storage partition is actually provisioned and tested.
10. Personal perspectives are first-person human source material, visibly distinct from external safety guidance. Preserve exact originals and require owner approval for edited attributed versions. Do not invent what an owner would think.
11. No default access to internal disks, mandatory networking, or hidden copying of host data. Protect notebooks from accidental public commits.

## Prototype acceptance

- App tests and content integrity checks pass.
- Original PDFs open offline; extraction previews clearly indicate they are unverified.
- Country-outline map renders entirely from packaged source-derived geography.
- Notebook survives application restart using the same writable directory.
- Real Linux image builds and its live root filesystem boots in a VM to the application backend.
- Distinguish direct-kernel live-system tests from BIOS/UEFI bootloader tests and graphical UI tests.
- Release publication follows actual build/test results; no generated or placeholder ISO.

## Deferred verification

Physical USB boot, hardware/driver matrix, Secure Boot, persistent USB provisioning and power-loss behavior, detailed regional maps, model selection and hardware performance, original-extraction visual verification, comprehensive medical/survival coverage, and independent safety review.
