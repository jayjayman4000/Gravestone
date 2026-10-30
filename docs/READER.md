# Controlled original-PDF reader

## One authoritative physical page

The reader renders **one physical PDF page to an app-owned canvas** using locally vendored Mozilla PDF.js. It never creates a PDF iframe, object, embed, browser-native toolbar, annotation navigation, or independently scrollable sequence of PDF pages. Scrolling pans only the current page. Previous / Next and Zoom drive the canvas itself; Copy refers only to the last successfully displayed physical page.

During opening, navigation, or zoom, the indicator says **Requested physical PDF page N — not yet displayed**, the previous canvas is removed, prior copied text is cleared, and Copy is disabled. The indicator becomes “Physical PDF page N of M” only after PDF.js's render promise completes and that canvas is installed. A cancelled or late render cannot replace its successor. Closing destroys the loading task/worker and cancels painting. Each opening owns a separate mount, so late import/cleanup cannot clear a newer document.

PDF.js's actual `numPages`, not a manifest estimate, supplies navigation bounds. Invalid/noninteger entry pages default to 1; positive out-of-range entry pages clamp to the actual final page after loading. Library opens default to page 1. Missing/mismatched manifest page counts disable derivative-text copying with an explanation, while actual-page reading, Back and original export remain available. No printed page label is guessed from an excerpt.

## UI integration contract

`app.js` preserves global `localLink(doc, label)` and `openReader(doc, opener)`. `reader.js`, loaded after app.js, installs the local dynamic-import factory and external controlled-viewer stylesheet, then calls idempotent `readerInit()`. The renderer is `app/static/pdfjs/controlled-viewer.mjs`; there is no second/native reader implementation.

The shell retains `#reader` (dialog), `#reader-header`, `#reader-title`, `#reader-back`, `#reader-source`, `#reader-status`, `#reader-download` and `#reader-body`. Initialization creates:

- `#reader-controls.reader-controls`, role group
- `#reader-prev`, `#reader-next`, `#reader-page`
- `#reader-zoom-out`, `#reader-zoom-in`, `#reader-zoom`
- `#reader-copy`
- `#reader-copy-panel.reader-copy-panel` with readonly `#reader-copy-text` and `#reader-copy-close`

Controls stay outside the scrolling page, with an obvious Back to library / results. Source rights/provenance/CDC notices remain in collapsed details. Zoom ranges from 50 to 300 percent in 25-point steps; the external stylesheet prevents responsive fit-to-width rules from silently overriding the requested scale. Canvas has an accessible physical-page label; this minimal viewer does not provide a PDF text/annotation layer. The readonly extracted-text panel remains selectable.

Search-card integration preserves **hit.page** when merging manifest metadata: `localLink({...hit, ...documentsByFile.get(hit.file), page: hit.page}, label)`.

## Source-only behavior and failure handling

Originals are HEAD-checked for successful PDF MIME type before loading or enabling export. Encoded escapes, fragments, query strings, absolute paths, URL schemes, traversal, backslashes, and control characters in source paths are rejected. PDF.js loads the same local unchanged original at `/content/originals/<file>.pdf`; no remote viewer, image, font, CDN, publisher HTML, or generated replacement is requested.

Copy is lazy: it fetches only a manifest-listed `search/*.txt` with path validation, same-origin credentials, redirects rejected, and plain-text MIME required. Form-feed-delimited physical-page count must match both the manifest and actual PDF, retaining empty-page positions. The exact displayed derivative page follows an explicit source/physical-page/**unverified machine extraction** label. Missing/empty/mismatched extraction never substitutes a search excerpt or generated text. Page/zoom change, reopen, and close invalidate pending copy responses and clear visible old text. Clipboard success is reported only after `writeText` succeeds; unavailable/denied clipboard opens a readonly focused, selected fallback panel. A clipboard write already handed to the operating system cannot be revoked; late completion cannot update the changed/closed reader.

Load/render failure leaves Back and, after successful original preflight, **Export original — complete PDF** available. It never silently falls back to a native PDF viewer with an unobservable page state. Export downloads the complete **unchanged publisher PDF**, not only the selected page, and does not save notebook changes. The modal preserves nested library state, queries/results, notebook draft and dirty guard, and restores focus to the actual opener.

## Local runtime and CSP

Pinned runtime: official `pdfjs-dist` **5.4.624**, with minified modern ES modules/worker, standard fonts, packed CMaps, and the non-WASM OpenJPEG fallback plus their licenses. See [vendor provenance](vendor/PDFJS.md) and the machine-readable per-file SHA-256 inventory. No package manager or external connection is needed at runtime.

Required additions to the existing self-only application policy:

```text
worker-src 'self'; font-src 'self' blob: data:
```

`script-src 'self'`, `style-src 'self'`, `connect-src 'self'`, and the existing content/download policies stay intact. The reader sets `isEvalSupported: false`, `useWasm: false`, and `enableXfa: false`: neither `unsafe-eval` nor `wasm-unsafe-eval` is needed. Styles use a same-origin external stylesheet, never inline CSS. The official worker is a same-origin module worker. Python serves `.mjs` as JavaScript. Restart an old backend process to exercise updated CSP headers; changing a Python file does not update already-running servers.

## Verification

```sh
python3 -m unittest discover -s tests -p 'test_reader*.py' -v
python3 -m unittest discover -s tests -p 'test_pdf_viewer.py' -v
python3 -m unittest discover -s tests -v
```

Node-backed tests execute the production app and controlled renderer. PDF.js's asynchronous boundary is injected for deterministic cancellation/race tests, not replaced for browser acceptance. Coverage includes requested-page canvas rendering, single-page ownership, page/zoom/Copy agreement, stale render rejection, close cancellation, late import cleanup, actual-vs-manifest bounds, loading/failure copy guards, exact selectable copy fallback, unsafe paths, provenance, export, nested return/focus and unsaved drafts. Vendor tests verify every shipped upstream byte against the recorded hashes.

Real Chromium **151.0.0.0** acceptance used a fresh isolated backend on loopback port 8880 with the actual CSP. FEMA original physical pages **7 and 8** produced distinct nonblank canvas pixel hashes, one canvas and zero iframes. Page 8 Copy matched exactly its derivative page before and after actual 125% rendering (765×990); 300% displayed width equaled canvas width (1836), not a CSS-clamped fit. Rapid Next/Next/Previous/Zoom settled on the same page-8/125% pixel hash, with Copy disabled during pending work. CDC's original single page also rendered with its collapsed provenance and nonendorsement notices retained. Original HTTP bytes matched the manifest SHA-256. Back, complete-original export, clipboard fallback, nested Library/focus, and unsaved draft survived. Recorded page resources were same-origin. Evidence: `/home/jayjayman4000/gravestone-test-evidence/reader-controlled-canvas/` (JSON plus PNGs), outside the public checkout.

Earlier native-Firefox reader evidence does **not** validate this implementation or solve native page drift. This controlled-viewer acceptance is Chromium, not a new Firefox/live-image, whole-ISO, physical boot, reboot-persistence, or transcription-accuracy claim.
