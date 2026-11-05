# Add your own reference documents

Gravestone has two content tracks:

- **Public bundled library:** original documents whose public redistribution basis has been checked, then integrated and tested. A topic label is not an installed guide.
- **Owner-installed library:** obtain documents yourself from legitimate publishers when their terms permit your intended download, storage and transfer. Free access is not permission to redistribute. Do not upload restricted PDFs, private inventories or populated content packs to GitHub or Discord. Unclear terms stay unresolved; personal use is not an automatic exemption.

Browse the public [owner-install reference catalog](OWNER_INSTALL_REFERENCES.md) for titles, editions, publisher links, separate download/redistribution status and format limits—without the protected originals. **CHECK TERMS** means permission is unresolved, not approved private installation. Radio-model entries are optional examples, not anyone's inventory or a preselected appliance catalog. PDF candidates still need individual acceptance checks; FDA HTML and the illustrated bow-book HTML ZIP are not currently importer-supported. Source acquisition and format compatibility are not safety approval.

## Shareable setup instructions

1. On your ordinary internet-connected computer, download the Gravestone source checkout from https://github.com/jayjayman4000/Gravestone . The preparation tool is in the source folder, not an application to run inside the flashed kiosk.
2. Install Python 3.10 or later if needed. Open a terminal in the source folder. Run `python3 -m host_prepare` on Linux/macOS, or `py -3 -m host_prepare` on Windows. Open the exact local address printed in that terminal. Keep it local; do not expose the server to the network.
3. In your normal browser, visit legitimate publisher pages. Check exact model, edition, language and terms. Download permitted original PDFs yourself. No account credentials belong in Gravestone's inventory. The wizard neither fetches manuals nor accepts publisher terms for you.
4. Enter private equipment details and select the downloaded PDFs in the wizard. Generate and save the private ZIP outside the source checkout. Keep a separate backup. Do not share a populated pack.
5. Extract into a new empty folder. Read its `TRANSFER.md`. The ZIP is transport, **not a boot image or a bulk-import installer**. Transfer permitted PDF files on a separate medium accessible to the live session; internal host disks are not automatically mounted. Follow applicable transfer restrictions as well as download terms.
6. In the offline Gravestone appliance, open **Import personal content**. Fill **Your document title**, use **Choose a local PDF (maximum 32 MiB)** for one extracted PDF, acknowledge authorized personal storage/use, and press **Import personal PDF**. Wait for confirmation before repeating; do not upload the ZIP. Current setup has no model/source selector. If the generated `TRANSFER.md` says **Other PDF** (legacy wording still present in the preparation helper), use this current form instead. No reflashing is required merely to import documents.
7. Open each original in **Source Documents**, check the relevant pages/figures and try a distinctive search phrase. Machine-extracted search text is not verified transcription; image-only scans have no OCR. Successful host pack creation does not establish kiosk PDF compatibility.
8. With persistent USB storage correctly configured, test that documents remain after two clean reboots. Do not rely on an application restart as proof. Preserve separate originals regardless: notebook/map backup excludes personal PDFs.

## Important limits

The host wizard uses Python's standard library. Windows/macOS commands are documented but have not been exercised on those operating systems. Detailed instructions and pack limits: [HOST_PREPARATION.md](HOST_PREPARATION.md).

Kiosk PDF imports require a supported parser (included in the live recipe), accept at most 32 MiB and 1,000 pages, and impose bounded extraction/time limits. Some PDFs will be rejected; no OCR, encrypted-document unlocking or arbitrary-format conversion is supplied. The public reader currently does not admit an illustrated HTML/EPUB archive merely because it was successfully downloaded.

Private storage is not encrypted. Do not add passwords, identity documents or other sensitive material without separate protection. Flashing/repartitioning can erase existing content; never reflash just to add PDFs. Nothing in this process provisions USB persistence or grants copyright permission.

## Short Discord message

> Gravestone supports your own authorized PDFs without sharing them publicly. On your normal computer, download the source and run `python3 -m host_prepare` (Windows: `py -3 -m host_prepare`). Open the local address printed in the terminal. Obtain originals yourself from the publisher and check download, storage and transfer terms; **CHECK TERMS** is not permission. Make a private pack, extract it into a new folder, and transfer the PDFs on a separate medium. In Gravestone, use **Import personal content** → **Import personal PDF**, one PDF at a time—not the ZIP. Open/search each document and verify it survives two clean reboots with persistence configured. Keep originals separately; don't share restricted PDFs or private packs. PDF acceptance isn't safety approval; HTML/EPUB aren't supported imports.
>
> Setup: https://github.com/jayjayman4000/Gravestone/blob/main/docs/CUSTOM_INSTALL.md
>
> Reference links and terms: https://github.com/jayjayman4000/Gravestone/blob/main/docs/OWNER_INSTALL_REFERENCES.md
