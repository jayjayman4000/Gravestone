# Gravestone civilian offline archive

## Current interface

The working checkout is a search-first civilian kiosk, not the earlier map-centered command console. Home contains:

- A prominent **Search Archive** input.
- Six touch-friendly topic tiles. Their coverage labels distinguish installed references from missing trauma/repair/radio/defense/foraging manuals; a category is not itself a supplied manual.
- Clean source cards with title, publisher, physical PDF page and a short exact extracted-text preview. The card opens the original at that page.
- **Emergency guide / Start here**, which explains navigation and lists installed originals. It does not invent emergency treatment instructions or connect to live assistance.
- On-demand Source Documents, Notebook, Maps and Display views, with obvious Close/Home controls.
- Actual battery/sysfs and configured-data-volume storage readings, or Unavailable when unsupported. Storage does not automatically mean the boot USB or verified persistence.

The four selectable palettes are Amber `#FFB000`, Red `#FF1A1A`, Green `#00FF66` on black `#000000`, and black on white `#FFFFFF`. Amber is the initial default. Palette preference alone is saved to browser localStorage when available; searches and notebook text are not. Themes apply to interface/map geometry, not original publisher PDF colors or hardware screen brightness. No guaranteed night-vision or sunlight-performance claim is made.

The footer is a single unobtrusive offline-archive statement. Repetitive developer/prototype/AI-authorship and extraction-warning boxes were removed from home/result cards; edition, source, extraction and rights context remain available in source information. The UI does not call the collection clinically/safely verified or emergency-ready.

## Source-only search

The user explicitly retained the original rule: **no AI-written survival procedures or synthesized action summaries**.

- Main question search uses bounded original query words and optional loopback local-model keyword suggestions. Suggestions never become an answer. Unavailable/invalid/slow model responses fall back to literal keywords without fabricated assistant text.
- Source Documents offers exact word/phrase matching.
- Both search paths return contiguous mechanically extracted source text, with physical PDF-page locations. Extraction can misread layout, words, tables, numbers or units; exact substring matching is not transcription verification. The complete original, including figures/cautions/context, remains authoritative.
- No matching source is reported as a collection/search gap, not proof that guidance does not exist. An original without usable extracted text can still be opened from the library.
- Main search is capped at 10 results; literal search at 50; input is at most 200 characters. Manifest reads are capped at 2 MiB, and an individual extracted-text file at 16 MiB.

The current document catalog is read from `content/manifest.json`, with no fixed document count in the interface. Source additions in the checkout are not silently added to a previously released/flashed ISO. See `SOURCE_ACQUISITION.md` and `SOURCE_CANDIDATES.md` for actual admissions, pending sources and redistribution/audience limits.

## Original-PDF reader

All local originals use a same-page controlled reader, not a new browser tab or native PDF iframe. Locally pinned PDF.js renders one physical PDF page to an app-owned canvas. Large Back, Previous, Next, Zoom In/Out, Copy page text and complete-original Export controls operate on that single page. Actual PDF page count supplies bounds; Copy requires agreement with the manifest/extraction count and a completed displayed render. A missing count, mismatch or render failure disables Copy rather than guessing.

Nested Library/Start-here readers return to their prior view. Query/results, map state and unsaved notebook drafts remain intact. Closing removes the canvas, cancels render/loading work and restores focus. A visible Back control remains available even if native PDF rendering fails.

Copy fetches the recorded unverified extraction derivative and copies only the app-selected physical page with an explicit source/page/extraction label. It does not substitute a generated answer or preview. Missing/mismatched text retains original Export. Clipboard failure offers selectable text rather than falsely confirming success. Native PDF navigation is not embedded. Scrolling pans only the displayed page; app page/zoom/Copy state cannot drift from a separate browser toolbar. See `READER.md` for validation, safety and native-browser test details.

Local PDF URLs are validated and HEAD-checked. Only same-origin PDF bytes are framed; remote pages/HTML are never embedded. Source rights, attribution and CDC free-availability/non-endorsement notices remain available without modifying publisher bytes.

## Offline maps and preparation

The Maps view is fullscreen, not a tiny home decoration. County packs provide real Census 2025 roads/highways/names and optional linear-water geometry. A bundled offline selector covers 3,222 U.S. county/equivalent entries across 52 state/territory codes. Each user selects the regions they need during online preparation, or imports original compatible county ZIPs offline. There are no automatic downloads.

Installed map data is served locally from the configured external writable data directory. It retains original ZIPs and source/digest/edition metadata, with bounded atomic conversion. Network availability/configuration is separate from a Download button; the live image still defaults to offline operation. Detailed global maps, computed routes, live passability, elevation and water drinkability are not supplied. Missing topography is shown disabled, not faked. See `MAPS.md` for import/download steps, limits and actual execution evidence.

## Run on an existing computer

Requires Linux and Python 3.11+. The app uses the standard library plus the bundled, licensed pure-Python shapefile reader; no pip installation or online browser assets are needed. JavaScript and canvas must be enabled.

```sh
python3 -m app --data-dir "$HOME/.local/share/gravestone" --host 127.0.0.1 --port 8766
```

Open `http://127.0.0.1:8766/`. Other network bind addresses are rejected. Port 0 selects an ephemeral loopback port for tests. If a port is in use, choose another; do not stop unrelated services. Copying/running this checkout does not create bootable media.

`--data-dir` must be outside the repository and content tree. Symlinked paths/ancestors are rejected; newly created private directories use mode 0700. Notes and downloaded maps are stored here, not in the public Git tree. The intended deployment is one unprivileged local backend, not a public network server or authentication boundary.

### Persistence and privacy

Notebook Save is explicit. It writes a same-directory temporary file, flushes it, atomically replaces the target and flushes the directory. The UI reads the exact notebook back before confirming success. Notes are capped at 256 KiB of UTF-8 text and are not encrypted. Other windows/processes can overwrite them; the last completed save wins.

A successful Save or application restart test does not prove USB-reboot or power-loss durability. Live data can be RAM-only; maps are then temporary too. Deliberately provision and verify the removable writable volume over two clean reboots before relying on it. The application does not autoformat storage or mount internal disks. Anyone with local system/filesystem access may read notes; there is no password.

## HTTP and file boundaries

- `GET /`, `/static/*`, `/content/*`: local shell/assets/unchanged originals; no directory listings.
- `HEAD /content/*`: reader MIME/status preflight, without a response body.
- `GET /api/library`: manifest documents and overview map metadata.
- `GET /api/search?q=...`: literal source results including `id,title,publisher,file,page,excerpt` plus machine-extraction warning metadata.
- `GET /api/command?q=...`: source results/query/terms/model mode/status; no generated answer.
- `GET /api/status`: backend readiness and unverified-persistence note, not a safety certification.
- `GET /api/system`: actual configured-volume storage and supported sysfs battery readings.
- `GET/POST /api/notes`: local plain-text notebook, JSON `{text}` on mutations.
- `/api/maps/*`: see `MAPS.md` for opt-in download, local data/import/removal and job routes.

Host validation applies to reads/writes. Mutations require an exactly matching loopback Origin and accepted same-origin Fetch metadata. Transfer encoding and duplicate/missing/oversized Content-Length are rejected as applicable; no permissive CORS is added. Notebook transport permits bounded JSON-escaping overhead. Errors retain appropriate statuses instead of inventing content or accepting partial input.

File access is directory-relative/no-follow; traversal, symlinks and nonregular targets are rejected. CSP permits only local assets and same-origin PDF frames. The dashboard/HTML/errors remain unframeable; only actual PDF MIME with `%PDF-` bytes is frameable by the same origin. A fake `.pdf` is served as opaque bytes, not trusted HTML. Do not expose this Python HTTP service through a network proxy.

## Verification boundaries

```sh
python3 -B -m unittest discover -s tests -v
node --check app/static/app.js
node --check app/static/console.js
node --check app/static/maps.js
```

The integrated suite currently runs **76 tests: 74 pass and two installed-model/inference checks are skipped without their explicit artifact environment**. Those skips do not establish current packaged AI functionality. New main/literal source-page, controlled reader, palette persistence, telemetry, county catalog/import/download protections and map-renderer tests execute production code with isolated test-only fixtures. An existing urllib chunked-request test race was replaced by a single-write raw HTTP test request; production rejection behavior was not weakened.

Real integrated Chromium preview checked all four exact computed palettes, no desktop horizontal overflow, actual telemetry, selected county download, local named-road/water rendering and map zoom. Arlington's 2,524 road and 32 water features were fetched by the real browser preparation flow and independently matched against original ZIP hashes/local API counts. DC pack hashes and 4,335/83 feature counts were checked too. Screenshots/assertions are held outside the public checkout under `gravestone-test-evidence/civilian-kiosk-integrated/`.

Earlier Debian Firefox ESR QA exercised the former native-iframe reader but did not detect independent native-page drift, so it does not validate the replacement. Current controlled-canvas Chromium QA verified distinct nonblank FEMA pages 7/8, matching displayed-page Copy through actual 125% rendering, rapid-navigation cancellation, 300% display sizing, unchanged original hashes, CDC rendering and nested draft/focus return. New Firefox acceptance is separate and remains pending until its recorded check completes; see READER.md. A screenshot/DOM adapter alone is not browser-rendering acceptance.

This is working-checkout/browser evidence, **not a new ISO, physical USB acceptance, persistence certification or completed survival library**. A user-approved layout preview, independent review and normal build/boot gates remain required before another flashable release.
