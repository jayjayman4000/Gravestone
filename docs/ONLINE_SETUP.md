# Optional online preparation and personal PDFs

Gravestone's **Online setup** button is optional and can be reopened. Bundled guides, local maps and notes remain usable without completing setup. Opening setup performs only a local catalog request: it does not download manuals, contact publishers or enable networking.

## Prepare on an internet-connected computer

The live image remains offline by default: this feature does **not** configure Wi-Fi, enable DHCP or add a general-purpose browser inside the kiosk. The simplest preparation route is to run Gravestone on your connected Linux computer and use your ordinary browser alongside it:

```sh
# From the source checkout; Debian/Ubuntu parser dependency:
sudo apt-get install python3-pypdf2
python3 -m app --data-dir "$HOME/.local/share/gravestone" --host 127.0.0.1 --port 8766
```

Open `http://127.0.0.1:8766`, choose **Online setup**, then:

1. Choose a listed radio manual and copy its official publisher-page address to your normal browser. The catalog includes Baofeng UV-5R and Icom IC-2300H and IC-718 basic/advanced manuals. Read and accept applicable terms yourself. Download the actual PDF through the publisher's normal process. No credentials, consent bypass or automatic restricted-source downloader is included.
2. In setup, choose the downloaded PDF, enter its title and select its source (or Other PDF). Acknowledge that you are permitted to store and use it personally under applicable terms. This acknowledgment does not grant permission or change the license.
3. Choose **Import personal PDF**. Wait for the confirmation that the imported record was read back from the library. If import is not confirmed, inspect Source Documents before retrying; a duplicate is rejected without replacing the first copy.
4. Open **Source Documents**. Personal imports are labeled separately and their original PDF bytes are preserved. The controlled reader and literal/command search use local copies. Search is mechanical extraction, not an AI-written guide; compare original pages. Scanned image-only pages are not OCR'd and will not be searchable.
5. Use the map-preparation button to open the existing map tools. Review available provider/area/zoom/storage choices and start the specific download deliberately. This does not add arbitrary map formats, unlimited coverage, or new rights to map data. See [Maps](MAPS.md).

A manual not listed in the catalog can still be imported with **Other PDF** if you are permitted to acquire/store/use it. Gravestone does not independently verify that the selected source describes your uploaded file.

## Limits and storage

- PDFs only: up to 32 MiB and 1,000 pages. Encrypted, malformed, over-budget or slow-to-parse files are rejected. Parsing is CPU/memory/time bounded in a separate process; this is not a complete hostile-document sandbox.
- Extraction has a conservative 2 MiB UTF-8 text budget and bounded JSON output. No OCR or automatic translation/summarization is provided.
- Imports go to `<data-dir>/personal/<sha256>/`, not the checkout, public manifest, Git or distributed ISO. Each import retains `original.pdf`, `search.txt` and `metadata.json`. Do not copy private files into `content/` to prepare a public build.
- Normal startup requires no parser for bundled sources. Import requires `pypdf` or `PyPDF2`; the live-image recipe installs Debian's `python3-pypdf2`.
- Experimental AI overviews remain public-collection-only; private PDFs participate in document/command search, not that experimental overview path.
- No encryption is provided. Other users with filesystem access can read these files. Kiosk/autologin is not an access-control boundary.
- Existing notebook/map backup **does not include imported PDFs**. Retain the original downloads and make a separate private copy of the `personal/` directory with the app stopped. Review permissions before sharing any populated USB, data directory or backup.

An application restart retains files in an ordinary persistent data directory. On a live USB without a provisioned and verified persistence volume, personal imports and maps are RAM-only and disappear at shutdown. The setup feature does not provision persistence, flash disks, or migrate your connected computer's private library to a USB. Use the existing [boot/persistence instructions](BOOT.md) and verify the target storage before relying on offline copies. To transfer a personal directory you are permitted to transfer, stop Gravestone on both systems and privately copy `personal/` into the target's configured data directory; transfer is owner-managed, not an automatic setup feature.

## Copyright boundary

The public project distributes code, reviewed reusable bundled sources, and official links—not the restricted radio manuals. Each owner uses the publisher's acquisition process themselves. This avoids **our** redistribution but is not a blanket copyright workaround. Copyright, publisher terms, geography, access restrictions and permissions still apply to downloads, extraction, storage, backups and transfers. No DRM/access-control circumvention is provided. See [source policy](SOURCE_POLICY.md).

## Verification boundary

Local tests exercise import, read-back, source-preserving search/reader paths, corruption/path protections and application restart. Chromium testing is not Firefox ESR/live-image/physical USB acceptance. A source test pass alone does not mean a new ISO exists or that personal imports survive a USB reboot.
