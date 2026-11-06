# Optional networking, downloads and personal import

Gravestone remains offline by default. Prepare material on an ordinary computer, or explicitly connect the live appliance when needed. The generic archive has no creator-specific equipment catalog and never accepts publisher terms or downloads personal documents automatically.

## Connect on the live appliance (optional)

1. On Home choose **Network & downloads** (also available through **Import personal content**).
2. Choose **Enable network / Wi-Fi & wired setup**. This starts NetworkManager for this boot and enables networking/Wi-Fi. A normal wired DHCP connection may connect immediately. The separate native `nmtui` screen opens in xterm; use Tab/arrow keys/Enter, **Activate a connection** for Wi-Fi or wired, and **Edit a connection** if a wired profile needs manual configuration. Enter passwords only there. This is keyboard-driven, not a touch-only network manager.
3. Choose **Back / Quit** or close xterm to return. **Refresh network status** reads NetworkManager's local state; connected does not prove internet or publisher availability. Missing hardware/firmware, unsupported Wi-Fi, captive portals, enterprise authentication and restricted networks may require administrator help. Only Debian main drivers are packaged; no proprietary firmware is added.
4. Choose **Open download browser**. A normal Firefox window opens at a blank page, with an address bar, separate from the kiosk. Navigate to legitimate publishers, check exact equipment/edition and applicable terms, and download an authorized **original PDF**, not a printed HTML page. If Firefox displays a PDF, use its Download button. No publisher-specific bookmarks or permissions are implied.
5. Downloads default to **`/home/user/Downloads`**. Close the normal browser (× or Alt+F4; close all of its windows if more opened) to reveal the unchanged archive. Alt+Tab switches windows. The kiosk has its own profile and remains open; neither native window replaces its page or loses notebook drafts.
6. In the import form, choose a local PDF. In Firefox's native chooser select **Home → Downloads**, or press **Ctrl+L**, enter `/home/user/Downloads`, then select the PDF. Enter its title, acknowledge authorized personal storage and choose **Import personal PDF**. Wait for the library read-back confirmation, then open **Source Documents** to read/search it.
7. Choose **Go offline** when finished. NetworkManager networking/Wi-Fi are disabled and its service is stopped. This does not close browser windows, erase downloads/passwords, disable Bluetooth, or impose a hardware radio kill switch. Local PDF import, reading, search, notebook and installed maps keep working.

The live recipe resets networking to disabled **every boot**, even if a root-union persistent overlay remembers NetworkManager settings. Reconnection requires the explicit enable action again. Saved connection profiles/passwords can persist under `/etc` with root-union persistence; downloads and both Firefox profiles live under `/home/user`. None is encrypted. Without verified persistence, downloads/imports may disappear at shutdown. Keep separate permitted backups; the notebook/maps backup excludes personal PDFs and download-browser state.

When running a source checkout without the live desktop session, native launch actions report unavailable; local file import still works. The web app never accepts commands, arbitrary executable paths, URLs or Wi-Fi secrets. It only sends fixed same-origin actions to a private same-user Unix socket in the X session. That session invokes fixed shell-free command arrays. The bridge uses sudoers entries for only two exact helper arguments; it never passes arbitrary privileged arguments. The HTTP backend retains `NoNewPrivileges` and its original filesystem sandbox. Neither service is a public-network endpoint.

### Maintainer contract / verification

- Fixed root helper: `/usr/local/sbin/gravestone-network online` or `offline`; live account: `sudo -n /usr/local/sbin/gravestone-network online` to enable, or `sudo -n /usr/local/sbin/gravestone-network offline` to disable. It does not open nmtui; graphical launch is separate.
- `gravestone-network-default.service` writes disabled NetworkManager state before NM can start. The NM drop-in requires this reset and a transient `/run/gravestone-network-enabled` marker. NM is installed but disabled, not permanently masked; competing DHCP/network services remain masked. The helper never changes boot enablement.
- `python3 -B -m app.desktop` runs only in the live X session, inheriting its display/DBus environment. Its socket is `/home/user/.local/share/gravestone-desktop/control.sock`, mode 0600, same-UID peers only, single session lock. HTTP has no generic proxy or download endpoint.
- `POST /api/desktop/network-online`, `network-settings`, `network-offline`, `browser`: exact `{}` JSON body only; exact loopback Host/Origin and same-origin Fetch metadata required; malformed/duplicate framing rejected and connection closed. `GET /api/desktop/status` is read-only and does not enable networking. A successful launch acknowledges process creation, not confirmed display/internet/download.
- Unit/HTTP/Node tests use disposable directories and mocks only at native command boundaries. They do **not** change host networking or prove native NetworkManager/Firefox behavior on a booted image. Verify real Wi-Fi/wired, browser download → chooser → import/read/search → offline and reboot-default-off on the exact next image; physical Wi-Fi remains a separate gate.

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
