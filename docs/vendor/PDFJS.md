# Mozilla PDF.js runtime provenance

Gravestone vendors the **official prebuilt minified modern distribution**, not an npm installation or a source checkout, under `app/static/pdfjs/`.

- Package/version: `pdfjs-dist@5.4.624` (immutable version, not `latest`).
- Publisher/upstream: Mozilla PDF.js, <https://github.com/mozilla/pdf.js>.
- Source package URL: <https://registry.npmjs.org/pdfjs-dist/-/pdfjs-dist-5.4.624.tgz>.
- Registry metadata: <https://registry.npmjs.org/pdfjs-dist/5.4.624>.
- Upstream commit recorded by the package: `384c6208b257e81fa7bcd4e59dc100e3c99d9528`.
- Tarball SHA-256: `5c387457cd03cc2e7b9c9b1ed642e8148d1ba44c3b8e5b5b771526feb24b61b9`.
- Registry SHA-512 integrity was independently computed and matched before extracting; recorded verbatim in [the JSON inventory](pdfjs-dist-5.4.624.json).
- License: Apache-2.0. The unmodified package `LICENSE` was byte-compared with <https://raw.githubusercontent.com/mozilla/pdf.js/384c6208b257e81fa7bcd4e59dc100e3c99d9528/LICENSE>.
- Main license SHA-256: `0d542e0c8804e39aa7f37eb00da5a762149dc682d7829451287e11b938e94594`.

## Exact selection

The JSON inventory records every shipped upstream path, original tar member, byte length and SHA-256. Package bytes are unmodified:

| Package member | Installed path |
| --- | --- |
| `build/pdf.min.mjs` | `pdf.min.mjs` |
| `build/pdf.worker.min.mjs` | `pdf.worker.min.mjs` |
| `LICENSE` | `LICENSE` |
| `cmaps/*` | `cmaps/*` (including `LICENSE`) |
| `standard_fonts/*` | `standard_fonts/*` (including `LICENSE_FOXIT`, `LICENSE_LIBERATION`) |
| `wasm/openjpeg_nowasm_fallback.js` | same relative path |
| `wasm/LICENSE_OPENJPEG`, `wasm/LICENSE_PDFJS_OPENJPEG` | same relative paths |

This is **191 upstream files / 3,916,148 bytes**. The app sets `useWasm: false`; only the JavaScript JPEG2000 fallback is shipped, not unused WASM binaries. No upstream tests, examples, source maps, viewer shell, legacy builds, npm dependencies, ICC/WASM accelerators or package-manager metadata are included. CMaps and fonts remain local to support embedded PDF font encodings without network access. Original survival-content PDF bytes are separate and are not changed by vendoring or rendering.

`controlled-viewer.mjs` and `controlled-viewer.css` are Gravestone integration code, **not upstream Mozilla assets** and not covered by the upstream file inventory. They implement the single-page rendering/cancellation contract documented in [READER.md](../READER.md).

## Reproducing/validating the selection

1. Fetch only the pinned metadata/tarball URLs above into a temporary directory.
2. Validate the tarball SHA-256 and registry SHA-512 integrity before reading its members.
3. Copy only the regular-file members listed in the JSON inventory; remove the `package/` prefix and additionally remove `build/` for the two minified modules. Do not unpack unlisted paths or normalize line endings.
4. Verify every copied member's size and SHA-256 against the JSON inventory. Verify the main license against the commit-pinned upstream URL above; retain all selected resource licenses verbatim.
5. Run `python3 -m unittest discover -s tests -p test_pdf_viewer.py -v` and exercise original-page rendering with the actual application CSP. Runtime URLs must be same-origin. No CDN fallback is permitted.

Updating versions requires repeating provenance/integrity/license checks and actual browser rendering/race verification; changing only a version string is not an update.
