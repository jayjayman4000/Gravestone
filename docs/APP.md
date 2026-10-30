# Gravestone dashboard

A local-only prototype field desk: publisher-original reference files, literal search over optional machine-extracted text, a country-outline reference atlas, and one plain-text notebook. The interface/navigation is AI-authored software; it is not survival guidance. No generated survival advice, local AI, personal accounts, or user-authored perspectives are bundled by the app.

## Launch

Requires Linux and Python 3.11+ (standard library only). No package installation, build step, CDN, fonts, tiles, telemetry, or internet connection is needed at runtime. JavaScript and canvas must be enabled in the browser.

From the repository root:

```sh
python3 -m app --data-dir "$HOME/.local/share/gravestone" --host 127.0.0.1 --port 8766
```

Open **http://127.0.0.1:8766/**. The host defaults to `127.0.0.1`; `localhost` is accepted and binds IPv4 loopback. Other hosts are rejected. The port defaults to `8766`; port `0` selects an ephemeral port for tests. The startup line reports the actual URL. Stop this foreground process with Ctrl+C. If the requested port is already in use, choose another port; do not stop an unrelated service.

`--data-dir` is required and must be outside both the repository and the content tree. Newly created directories use mode 0700; new note files use mode 0600. Existing directory permissions are not changed. Directory/file symlinks, including ancestor symlinks, are not supported. Use actual paths rather than symlink aliases. The intended deployment is one backend process under an unprivileged local user with a private data directory.

### Storage is not automatically persistent

The notebook is `notes.txt` in the configured data directory, **not** in the public repository and not in browser localStorage. Save is explicit, not automatic. Writes use a same-directory temporary file, file `fsync`, atomic replacement, and directory `fsync`. The UI reads the notebook back before confirming a save.

A successful save or backend restart test does **not** prove persistence across reboot, power loss, removal of the USB, or a failed flash device. A live system may put the directory in RAM. Verify the actual writable persistent mount, permissions, and a reboot/read-back on the target USB before relying on it. `/api/status` intentionally says persistence is not verified; it does not infer mount durability. Notes are not encrypted and there is no login. Anyone with filesystem access, or another local process, can read them. Back up important notes separately.

Only one notebook is supported. Multiple windows/processes can overwrite one another; the last completed save wins. The UI warns about unsaved edits on navigation where the browser permits it. It is not an emergency communication or incident-management system.

## Content integration

The app reads repository `content/manifest.json`; it never downloads or generates documents. Expected shape:

```text
{
  "documents": [
    {
      "id": "stable-document-id",
      "title": "Publisher's original title",
      "publisher": "Publisher",
      "url": "Original source URL",
      "file": "originals/document.pdf",
      "sha256": "Original file SHA-256",
      "rights": "Source rights/attribution",
      "retrieved_at": "Retrieval timestamp",
      "text_file": "search/document.txt",
      "extraction_status": "Machine-extracted; not visually verified"
    }
  ],
  "map": {
    "file": "maps/world.geojson",
    "publisher": "Map data publisher",
    "url": "Source URL",
    "rights": "Map rights/attribution",
    "sha256": "Map file SHA-256"
  }
}
```

All file paths are relative to `content/`. `text_file` is optional. Additional metadata is preserved. The library opens local PDF originals in a same-page reader overlay and shows manifest provenance. Non-PDF originals are not embedded; access them as ordinary files outside the kiosk. Publisher source links are explicitly labeled as requiring a network and are never fetched automatically. Displaying a manifest hash is **not** runtime hash verification. Collection integrity, source authenticity, licenses, attribution, version currency, and content review remain the collection/build pipeline's responsibility. Missing or malformed manifests produce an explicit library error, not invented documents.

### Original-document reader

Library **Open original** and search **Read original in full** use the same app-owned modal reader; neither opens a new tab nor replaces the dashboard. A large **Back to library** button stays above the PDF, including when scrolling long provenance on a narrow screen. Closing removes the frame and restores focus to the opening library/search button. The underlying notebook, unsaved edits, search results, and dashboard are kept intact. Opening an original does not save notes. Escape may also close the dialog where the browser handles it, but is not the only exit and may be intercepted by the native PDF viewer.

The reader identifies the original title, publisher, rights, and source URL. CDC originals additionally display CDC attribution, free availability, and non-endorsement notices. These are interface/provenance labels, not modifications to publisher files. Publisher-source links in library provenance deliberately remain **new-tab, network-required** links; remote publisher sites and HTML are never embedded by the reader.

Before embedding, a local HEAD request checks availability and `application/pdf`. Invalid/unsafe paths, non-PDF originals, missing files, and service errors do not create a frame. Errors retain the visible return button. The reader always explains the blank/unsupported-viewer fallback and offers a download of the unchanged local PDF after successful validation, without opening a new tab. Browser PDF rendering failures are not reliably detectable from iframe load events; the app does not claim a rendered page merely because the frame loaded. In kiosk use, return to the library if the viewer fails; downloading may require an external PDF-capable viewer.

### Search safety boundary

Search is case-insensitive literal substring matching, with up to 50 previews and a query limit of 200 characters. Each excerpt is a contiguous substring of the installed UTF-8 `text_file`, including its original whitespace; no language model or answer generation is used. An original PDF without extracted text is still in the library but cannot be searched. Missing, unreadable, invalid-UTF-8, or oversized extraction files are skipped. Manifest reads are capped at 2 MiB; individual extracted text reads at 16 MiB.

**Literal extraction is not verification.** PDF extraction may change reading order, table structure, numbers, units, or line breaks. Every visible result is labeled:

> Machine-extracted search preview — not verified; open the original document and read full context.

Previews may begin/end mid-word or omit necessary context. They must not be treated as verified safety quotes or instructions. No match does not mean a topic is absent. Always open the original file and read the full context, including tables and cautions. Search is not semantic search, OCR, a complete index, or a substitute for reading originals.

### Reference atlas

The map requires a local GeoJSON `FeatureCollection` containing `Polygon` and/or `MultiPolygon` features in longitude/latitude degrees. Optional `properties.name` / `properties.iso_a3` provide labels and an accessible country index. Coordinates are projected equirectangularly, with deliberately simple antimeridian handling. Pan by dragging or arrow keys while focused; zoom by wheel, buttons, or +/−; Home or Reset returns to the world overview. Zoom is bounded to 1×–16×. Optional manually entered latitude/longitude centers a reference marker; it does not detect GPS and is not stored. Labels are approximate and may be omitted to avoid overlaps.

**Reference only: not a navigation or street map.** There are no routes, detailed US/regional maps, terrain/elevation, shelters, real-time conditions, live location, or emergency-service data. Simplified country outlines and publisher boundary conventions are not appropriate for travel or safety decisions. Canvas has keyboard controls and a textual country index, but is not a full nonvisual geographic interface.

## HTTP contract

All JSON responses are UTF-8 and sent with `Cache-Control: no-store`. Host validation applies to reads and writes; normal URLs include the actual port.

| Request | Result |
| --- | --- |
| `GET /` | Dashboard |
| `GET /static/*` | Local UI files only |
| `GET /content/*` | Content files, unchanged bytes; no directory listings |
| `HEAD /content/*` | Same status, MIME, security headers, and length, without a body; reader preflight |
| `GET /api/library` | Manifest object including `documents` and `map` |
| `GET /api/search?q=phrase` | `{results: [{id, title, file, excerpt}], warning}` |
| `GET /api/status` | Prototype status and explicit unverified-persistence note |
| `GET /api/notes` | `{text: "..."}`; empty string only for a missing notebook in an available data directory |
| `POST /api/notes` | JSON `{text: "..."}`; returns stored text on success |

Note text is capped at **256 KiB (262,144 UTF-8 bytes)**, not 262,144 Unicode characters. The transport limit permits JSON escaping overhead. POST requires `Content-Type: application/json`, a valid single loopback `Host` with the server port, and an exactly matching HTTP `Origin`. Cross-site fetch metadata is rejected. Non-browser clients must set Origin explicitly; CORS is not enabled. Transfer-encoded bodies and duplicate Content-Length values are rejected.

Failures include 400 (invalid path/query/body/framing), 403 (Host/origin), 404 (unknown route or unavailable content), 411 (missing Content-Length), 413 (size limit), 415 (media type), and 503 (manifest/notebook storage unavailable). Files are opened with directory-relative, no-follow traversal; symlinks, nonregular files, and path traversal cannot expose files outside their serving roots. The dashboard CSP allows only same-origin frames (`frame-src 'self'`) and remains unframeable itself. Only successfully served content with PDF MIME and a `%PDF-` signature receives `X-Frame-Options: SAMEORIGIN` and `frame-ancestors 'self'`; PDF responses do not receive the HTML sandbox that would obstruct native PDF viewers. A `.pdf` file without the signature is served as `application/octet-stream`, not as a frameable PDF. All other responses retain `X-Frame-Options: DENY`; publisher HTML and content errors retain the restrictive sandbox CSP, without scripts, frames, or external resources. Some original HTML features may therefore be unavailable. This is a small loopback-only prototype using Python's HTTP server, not a hardened public network server; do not expose it through a proxy or bind it to a network interface.

## Tests and verification

```sh
python3 -m unittest discover -s tests -v
python3 -m compileall -q app
```

Tests use temporary fixture collections and external temporary note directories; the fixtures are test data, not survival documents. They start actual threaded HTTP servers on ephemeral loopback ports, exercise the module CLI, original-byte serving, manifest/search behavior, error statuses, notebook restart persistence, UTF-8 size limits, invalid JSON, same-origin enforcement, traversal/symlink rejection, nonregular storage, XSS-safe text rendering conventions, and accessible shell/map controls. If Node.js is present, an additional dependency-free test exercises JavaScript projection, pan/zoom bounds, coordinate validation, polygon extraction, and label collision checks. Dependency-free Node reader regression also executes the production JavaScript and actual library/search/click handlers through a minimal DOM adapter: same-page modal behavior, visible return markup, original title and CDC notices, publisher-link policy, focus restoration, unsaved edits and unload guard, missing/wrong-MIME/offline failures, unsafe paths, and a late preflight response after closing. Node-dependent tests are skipped without Node; Node is not a runtime dependency. HTTP tests check exact PDF/HTML framing policies, HEAD behavior, and unchanged original bytes; collection tests check installed original hashes.

Implementation followed incremental RED → GREEN cycles; failing behavior was exercised before implementation. Browser smoke testing used the installed parent-supplied FEMA/CDC collection and local world polygons: library display, machine-extraction warnings, search, note save/read-back with literal HTML-like text, coordinate centering, map controls, desktop layout, and a 390-pixel viewport. Initial application resource requests were all same-origin; no remote assets were fetched. Resolved findings included unavailable/nonregular notebook targets being misreported as empty, deeply nested invalid JSON disconnecting instead of returning 400, and overlapping country labels at narrow widths.

Reader-specific browser verification used Chromium on an isolated loopback server: FEMA and CDC PDF pages visibly rendered below the return header, library/search opening and closing retained an unsaved notebook draft and restored focus, and a 390 × 700 viewport confirmed the 52-pixel-high return button stayed visible after scrolling long CDC provenance. Browser QA caught and fixed a narrow-screen case where provenance scrolling originally hid the button. This is not Firefox ESR kiosk verification.

Not verified here: a complete Debian live-USB boot, Firefox ESR kiosk-specific PDF behavior, real persistent-mount reboot durability, power-loss resilience on the target flash device, or formal accessibility/security certification. The browser smoke check is not a substitute for those deployment checks.
