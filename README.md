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

- Command-first Python standard-library interface, original PDF library with a visible return control, model-assisted keywords, fallback literal search through an explicitly unverified extraction index, and local notebook.
- FEMA's *Are You Ready?* and CDC's *Make Water Safe During an Emergency*, retained as original PDF bytes with SHA-256 records.
- Natural Earth worldwide country outlines at 1:110 million scale: **not a detailed road map or navigation system**.
- Debian Live build recipe and automated build/boot checks; see workflow results for actual verification, not merely this feature list.
- Source-built CPU-only llama.cpp and the pinned Qwen3-0.6B model are included by the 0.2.0 image recipe; the Git checkout alone contains neither binary nor weights. Build and real-inference evidence are required before release.
- **No detailed U.S. roads, comprehensive survival library, or imported personal accounts yet.** Requested handwritten topics are an acquisition backlog, not installed instructions.

## Run on an existing computer

Requires Python 3.9+ and a modern browser; no Python packages or internet access needed for the app.

```sh
python3 -m app --data-dir ~/.local/share/gravestone --host 127.0.0.1 --port 8766
```

Open `http://127.0.0.1:8766/`. This runs the application; copying a repository does **not** make a USB bootable.

```sh
python3 -m unittest discover -s tests -v
```

## Bootable edition

Read [boot/build and flashing notes](docs/BOOT.md), [application details](docs/APP.md), [source policy](docs/SOURCE_POLICY.md), and [requirements](docs/REQUIREMENTS.md).

Use only release images with published checksums. Flashing destroys the selected drive's existing contents. Physical hardware compatibility, firmware restrictions, USB persistence, and image verification require separate testing. No promise of booting every computer or surviving EMP, damaged storage, or power loss.

## Attribution and licensing

Source: FEMA and CDC. CDC material is available without charge from the agency website. Gravestone is independent and is not endorsed by FEMA, CDC, ATSDR, HHS, or the United States Government. Made with Natural Earth.

The software license does not relicense source documents, map data, Debian packages, or personal contributions. See [third-party notices](THIRD_PARTY_NOTICES.md). Do not publish private notebooks or personal accounts by default.
