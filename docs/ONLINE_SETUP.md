# Personal preparation and offline import

Prepare personal material on your normal internet-connected computer **before flashing**. The generic Gravestone appliance does not ship a creator-specific radio/vehicle catalog or configure networking.

## Prepare on your normal computer

Follow [Host preparation](HOST_PREPARATION.md): run `python3 -m host_prepare` from the checkout (Windows: `py -3 -m host_prepare`) and open its printed loopback URL. No third-party Python packages are required for that preparation tool.

Use the blank [equipment template](../MY_EQUIPMENT.md) or wizard to record exact models, legitimate publisher pages, filenames, consumables/spares, last-checked dates and unknowns. Visit publishers in your ordinary browser and acquire only material you are permitted to use. The wizard does not fetch documents or accept publisher terms for you.

The downloaded preparation ZIP contains a private inventory and byte-preserved PDF originals with hashes. It is **not a one-click Gravestone installer or a bootable image**. Keep it outside Git and public build inputs. Downloading the pack does not provision persistent storage or flash a USB. Keep a separate copy before reflashing: writing an image can erase existing data.

## Import while offline

1. Extract your preparation ZIP on the connected computer. Transfer permitted original PDFs using a separate medium accessible to the live session. Gravestone does not automatically mount the computer's internal disks.
2. In Gravestone, choose **Import personal content**. Select a local PDF and enter its title. Acknowledge applicable personal-use permissions; this does not grant permission or change its license.
3. Choose **Import personal PDF** and wait for read-back confirmation. Duplicates are rejected without replacement; check Source Documents before retrying an uncertain import.
4. Open **Source Documents** to read the unchanged original. Literal and command searches use machine-extracted page text, not generated instructions. Scanned image-only pages are not OCR'd.
5. Keep inventory Markdown/JSON as ordinary private reference files. The appliance does not bulk-import the preparation ZIP or index its inventory. Maps use their separate existing import/preparation tools; see [Maps](MAPS.md).

## Display colors

Home's **Display colors** button opens four persistent choices: amber on black (default), red on black, green on black and black on white. Palette persistence depends on browser storage and, across live-USB reboots, a correctly configured persistent environment.

## Limits and storage

- PDF import: maximum 32 MiB and 1,000 pages; conservative 2 MiB UTF-8 extraction budget. Encrypted, malformed, slow or over-budget files are rejected. A bounded parser process is not a complete hostile-document sandbox.
- Imported originals, extraction and metadata live under `<data-dir>/personal/<sha256>/`, outside the public manifest and checkout.
- Bundled-source reading needs no PDF parser package. Personal import needs `pypdf` or `PyPDF2`; the live recipe installs Debian's `python3-pypdf2`.
- Private PDFs participate in source/command search, not experimental public-collection AI overviews.
- Storage is **not encrypted**. Kiosk/autologin is not access control. Keep passwords, recovery codes, identity documents and sensitive medical information separately protected.
- Notebook/map backup **excludes imported PDFs**. Retain originals and separate private backups. Do not share populated media without reviewing its contents.

Application-restart durability is not USB-reboot persistence. Without verified persistent storage, a live session's imports and maps can disappear at shutdown. See [boot/persistence instructions](BOOT.md). No preparation tool here provisions persistence, flashes disks or automatically migrates a host library to USB.

## Rights and verification boundaries

Links to legitimate publisher pages do not grant PDF redistribution rights. Personal download, extraction, storage, transfer and backup remain subject to applicable rights and publisher terms. No access-control circumvention is provided. See [source policy](SOURCE_POLICY.md).

Local tests and desktop Firefox checks cover palette selection/reload, PDF import/read/search and application restart. These do not establish physical USB or new-image reboot acceptance. A passing application suite is not evidence that a new ISO has been built.
