# Prepare a private pack on your normal computer

This source-side wizard uses only Python's standard library and your normal browser.
It does not need the kiosk app, a PDF parser, Linux-only modules or third-party Python
packages. Python 3.10+ is required (tested here on Python 3.11/Linux and Chromium).
Windows/macOS and their download dialogs have not been exercised here.

From an unpacked source checkout, open a terminal in the Gravestone folder:

```sh
# Linux/macOS with Python installed
python3 -m host_prepare
# Windows with the Python launcher installed
py -3 -m host_prepare
```

Open the exact `http://127.0.0.1:PORT/` address printed in the terminal, on the same
computer. Keep the terminal open; Ctrl+C stops it. Optional `--port 8767` fixes the
port; default port 0 asks the OS for a free port. No non-loopback bind option exists.
Do not expose/proxy this service to a network, including Tailscale. The process runs
one request at a time with a 15-second socket inactivity timeout; it is a local
preparation helper, not a multi-user upload service or a hostile-document sandbox.

1. Add equipment and record exact model, official manual link, local filename,
   consumables/spares, last checked and explicit unknowns. Leave details unknown
   rather than guessing. No private models or publisher catalog is preselected.
2. Acquire permitted original PDFs yourself through the publisher in your normal
   browser. The wizard records HTTPS links but never opens or downloads them.
3. Choose local PDFs; each title is editable. Review applicable terms and acknowledge
   authorized personal storage/use. This grants no rights or redistribution permission.
4. Create the private pack. Confirm the browser actually saved the ZIP in a private
   folder outside the checkout; use its save settings to choose the destination.
   Keep the distinct random download filename, never approve overwriting an old copy.
5. Extract into a **new empty folder** and read `TRANSFER.md`. Transfer permitted PDFs
   individually with the existing kiosk's Other PDF importer; do not upload the ZIP.
   Open the originals and test search. Verify persistence across two clean reboots.

No draft storage or resume/import-existing-pack feature: refreshing or closing loses
unsaved entries. No encryption, password storage, download manager, OCR, PDF parsing,
manual selection, flash writer, disk mount, persistence provisioning or bulk kiosk
import is included. Do not enter secrets. Other local users/processes with access to
your browser/storage may read content. PDFs may contain active/unsafe content; hashes
only establish byte identity, not safety, completeness, authorship or applicability.
Header/EOF checks reject obvious non-PDFs but are not parser validation. The kiosk
still applies its own parsing limits and can reject a file accepted by this helper.

## Limits and collision handling

- At most 100 inventory entries; each field is at most 4,000 characters.
- At most 16 PDFs; 32 MiB each and 64 MiB total; 92 MiB HTTP JSON request ceiling.
- JSON/base64 and ZIP copies are prepared in RAM. Allow several hundred MiB spare RAM
  near the size limits, or split into smaller packs. No temporary uploads are written.
- The HTTP helper never chooses/writes an output path. Download names contain 96 random
  bits to avoid ordinary collisions; browser/OS save dialogs remain responsible for
  destination permissions and final overwrite choices. Extraction is owner-managed.
- PDF SHA-256 names prevent filename traversal/collisions inside the ZIP. Identical PDF
  bytes selected twice reject the pack rather than replacing a member. Original filenames
  are metadata only; two different PDFs with the same filename remain separate.
- Host/Origin checks and a per-run token restrict cross-site requests; responses disable
  caching, framing and external resources. This is not isolation from malicious local code.

## Version 1 pack contract (not an app import API)

ZIP, uncompressed entries, UTF-8 JSON. The helper returns it as a browser download;
it does not install anything in `<data-dir>/personal/`.

- `manifest.json`: `format: "gravestone-personal-preparation"`, `version: 1`, and
  `documents`, each containing `path`, `sha256`, `bytes`, `original_filename`, `title`,
  `source_id: "other"`. No verified publisher identity is inferred.
- `pdfs/<sha256>.pdf`: exact original bytes, not rewritten/extracted/repaired.
- `inventory.json`: `version: 1`, `equipment` array. Each item contains `category` plus
  `exact_model`, `official_manual_link`, `local_filename`, `consumables_spares`,
  `last_checked`, `unknowns`. Original field strings remain unchanged in JSON.
- `MY_EQUIPMENT.md`: reading aid with user punctuation entity-escaped to avoid active
  Markdown/HTML. Use `inventory.json` when exact original field text matters.
- `TRANSFER.md`: private storage, individual PDF transfer and persistence cautions.

To check an extracted original, compare its SHA-256 to its manifest entry:

```sh
sha256sum /private/new-folder/pdfs/HASH.pdf  # Linux
shasum -a 256 /private/new-folder/pdfs/HASH.pdf  # macOS
```

```powershell
Get-FileHash -Algorithm SHA256 'C:\private\new-folder\pdfs\HASH.pdf'
```

A future importer must independently validate any ZIP before extraction; this writer's
contract is not permission to trust arbitrary archives. Current inventory stays an
ordinary private file, not a kiosk-indexed source. Maps remain separate supported map
packs; the inventory category does not add map content. Notebook/map backups exclude
personal PDFs. Keep the original pack/private downloads separately. Never format,
repartition or reflash an existing USB just to transfer content. USB reboot persistence
and physical hardware acceptance are separate from this host/browser test.

## Developer checks

```sh
python3 -m unittest discover -s tests -p 'test_host*.py' -v
```

Tests use disposable synthetic PDFs (not publisher manuals and not parser-validity
claims), assert byte/hash preservation, collision-free ZIP paths and download names,
reject malformed/oversized input and cross-site/rebinding attempts, and exercise the
actual module launcher. Browser download evidence is retained outside the checkout.
