# Gravestone

A portable, offline survival-reference computer: knowledge that remains usable when its original keeper is absent.

**Early engineering prototype. Not a complete or validated emergency resource.** The app and documentation may be AI-assisted; survival-source documents are publisher originals, not AI-authored instructions.

## Intended product

- Bootable USB for compatible 64-bit Intel/AMD PCs, targeting an advertised 16 GB drive.
- Starts in an offline dashboard; core browsing and search never require an AI model or network.
- U.S.-focused source library, worldwide reference geography, and eventually selected detailed regional maps.
- Local AI keyword assistance for retrieval; never an authority replacing the originals.
- Portable field notes and optional owner-authored perspectives, kept separate from published guidance.
- Usable by another person without the original owner's account, passwords, or presence.

## This prototype

- Search-first civilian kiosk with six topic tiles and four palette presets; original PDF library, model-assisted keywords, fallback literal search through an explicitly unverified extraction index, and local notebook.
- Eleven original FEMA/CDC/USDA/CPSC/EPA publisher PDFs in the checkout, retained intact with SHA-256 records. The app-owned single-page PDF.js reader keeps physical-page navigation, zoom and extracted-text Copy consistent. Search text remains an unverified derivative; training requirements and edition limitations remain with each source.
- Natural Earth worldwide country outlines at 1:110 million scale, plus opt-in U.S. county road/water pack preparation: **no detailed regional packs preinstalled, route calculation, or potable-water claim**.
- Debian Live build recipe and automated build/boot checks; see workflow results for actual verification, not merely this feature list.
- Source-built CPU-only llama.cpp and the pinned Qwen3-0.6B model are included by the 0.4.0 image recipe; the Git checkout alone contains neither binary nor weights. Build and real-inference evidence are required before release.
- **No comprehensive survival library or imported personal accounts.** Requested handwritten topics are an acquisition backlog, not installed instructions.
- [Notebook/map backup and recovery](docs/BACKUP_RECOVERY.md) is a preparation CLI, not a bootable clone or browser-profile backup. Archives are unencrypted; restore refuses existing targets. [VM reboot acceptance](docs/PERSISTENCE_TEST.md) and the [physical-device checklist](docs/DEVICE_ACCEPTANCE.md) keep software evidence distinct from physical-stick reliability.

## Run on an existing computer

Requires Python 3.9+ and a modern browser; core bundled-source browsing needs no Python packages or internet access. Optional personal-PDF import requires `pypdf` or Debian's `python3-pypdf2`.

[Online setup](docs/ONLINE_SETUP.md) provides official manual-page addresses, authorized personal-PDF import for offline reading/search, and access to map preparation. Restricted owner-acquired files stay outside Git and distributed images; publisher terms still apply. Setup does not configure networking in the offline-by-default live image.

```sh
python3 -m app --data-dir ~/.local/share/gravestone --host 127.0.0.1 --port 8766
```

Open `http://127.0.0.1:8766/`. This runs the application; copying a repository does **not** make a USB bootable.

```sh
python3 -m unittest discover -s tests -v
```

## Bootable edition

Read [boot/build and flashing notes](docs/BOOT.md), [application details](docs/APP.md), [source policy](docs/SOURCE_POLICY.md), and [requirements](docs/REQUIREMENTS.md).

Published engineering test images: [releases](https://github.com/jayjayman4000/Gravestone/releases). Read the chosen image's exact checksum, completed checks, and remaining limits before flashing. Follow the [candidate-specific USB test checklist](docs/USB_TEST.md): 0.4.1 adds a corrected extracted-loader path and constructed GPT/UEFI same-USB root-persistence acceptance. A nonzero Rufus persistence slider bypasses the DD prompt; keep that path separate from the zero-slider DD alternative. Physical stick acceptance is still required.

Use only release images with published checksums. Flashing destroys the selected drive's existing contents. Physical hardware compatibility, firmware restrictions, USB persistence, and image verification require separate testing. No promise of booting every computer or surviving EMP, damaged storage, or power loss.

## Attribution and licensing

Source: FEMA and CDC. CDC material is available without charge from the agency website. Gravestone is independent and is not endorsed by FEMA, CDC, ATSDR, HHS, or the United States Government. Made with Natural Earth.

The software license does not relicense source documents, map data, Debian packages, or personal contributions. See [third-party notices](THIRD_PARTY_NOTICES.md). Do not publish private notebooks or personal accounts by default.
