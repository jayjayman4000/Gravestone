# Practical source acquisition — 2026-10-30

This is an **editorial/provenance record**, not safety guidance. No survival instructions or safety summaries were authored, paraphrased, or completed with AI. Open the complete publisher PDFs; machine-extracted text is an **unverified search aid**.

## Actually installed

Batch ID: `practical-coverage-2026-10-30`.

**Five new complete PDFs, 54 physical PDF pages, 3,132,867 original-file bytes.** Together with the two untouched starter PDFs, the installed document count is **seven** (map data and policy snapshots excluded). These are original externally authored documents, not five generated topic notes.

| Source ID | Original installed under `content/` | Physical pages | Publisher edition / identification |
| --- | --- | ---: | --- |
| `usda-kitchen-companion-2015` | `originals/usda-kitchen-companion-2015.pdf` | 50 | USDA FSIS, *Kitchen Companion: Your Safe Food Handbook*; February 2008, slightly revised March 2015 |
| `cdc-use-safe-water` | `originals/cdc-use-safe-water.pdf` | 1 | CDC, *Use Safe Water During an Emergency*; CS334749-B; PDF subject metadata dated 11/9/2022; no separate printed edition date |
| `cdc-wash-hands` | `originals/cdc-wash-hands.pdf` | 1 | CDC, *Wash Your Hands*; CS283831-A; no printed edition date; 2017-09-27 PDF creation metadata is not an edition date |
| `cdc-prevent-diarrhea-after-disaster` | `originals/cdc-prevent-diarrhea-after-disaster.pdf` | 1 | CDC, *Preventing Diarrhea After A Disaster*; CS286698-I, November 27, 2018; visible title differs from stale embedded Hurricanes title |
| `cpsc-portable-generator-hazards` | `originals/cpsc-portable-generator-hazards.pdf` | 1 | CPSC, *CPSC Safety Alert: Portable Generator Hazards*; Publication 5123/102021; later PDF modification metadata is not treated as a new edition |

Each has an identically named `.txt` file under `content/search/`. Exact request URLs, final HTTP retrieval URLs, UTC retrieval timestamps, publisher URLs, byte sizes, page counts, original SHA-256 values, derivative SHA-256 values, edition caveats and source dependencies are recorded in `content/manifest.json`. `content/rights/practical-coverage-2026-10-30.json` records admission evidence and excluded candidates. Dates in URL paths, HTTP Last-Modified and PDF metadata are not silently substituted for publisher edition statements.

## Download sources and exceptions

- USDA publisher URL: https://www.fsis.usda.gov/sites/default/files/media_file/2020-12/Kitchen-Companion.pdf
- **Actual USDA download:** https://www.govinfo.gov/content/pkg/GOVPUB-A110-PURL-gpo234150/pdf/GOVPUB-A110-PURL-gpo234150.pdf
- GPO provenance: https://www.govinfo.gov/metadata/pkg/GOVPUB-A110-PURL-gpo234150/mods.xml
- CDC water: https://www.cdc.gov/water-emergency/media/pdfs/334749-B_UseSafeWater-OnePager-508.pdf?download=1
- CDC handwashing: https://www.cdc.gov/water-emergency/media/pdfs/factsheet-wash-your-hands.pdf?download=1
- CDC disaster hygiene: https://www.cdc.gov/water-emergency/media/pdfs/preventing-diarrheal-illness-after-disaster-english-H.pdf?download=1
- CPSC generator hazards: https://www.cpsc.gov/s3fs-public/5123_SafetyAlert_PortableGenerators_102021.pdf?VersionId=3D.6KZkXcpeiyriLmSswrdnVQI4JERoN

Direct FSIS retrieval returned HTTP 403, so the USDA PDF is the official **GPO-preserved agency rendition**, not an anonymous mirror or an AI reconstruction. GPO's archived MODS identifies USDA FSIS as author, gives the exact originating FSIS PDF URL, identifies 50 digital-object pages, and says it harvested the content from the authoring/hosting agency. GPO warns archived publications may not reflect current policy. Byte identity with today's inaccessible FSIS endpoint is **not** established; the archived rendition's PDF metadata modification date is 2026-06-26. No pages were removed, replaced, cropped or re-rendered into the installed PDF.

Some agency endpoints rejected initial requests. CDC's published download URLs with the explicit `download=1` query were retrievable with ordinary Python urllib; the exact successful URLs are recorded rather than normalized away. CPSC's literal download query is preserved; the resulting bytes, not the filename or requested query alone, define this archived copy.

## Rights evidence and admission basis

`.gov` hosting alone was **not** the reuse decision. Agency authorship, the intact work's credits/notices, and publisher reuse terms were checked. All source and agency notices remain within the PDFs, and additional attribution/non-endorsement/free-availability notices are in `THIRD_PARTY_NOTICES.md` and document manifest records. Government marks are not extracted as application branding. These are U.S. reuse determinations, not a certification of foreign rights or qualified legal advice.

| Publisher | Reuse basis and work-specific check | Archived evidence under `content/rights/` |
| --- | --- | --- |
| USDA FSIS | Government authorship confirmed in the work and GPO record. USDA Digital Rights and Copyright policy permits copying public-domain information, requests attribution, and distinguishes protected third-party/personal-use-only exceptions. Full extracted text and the complete page sequence were reviewed for credits/notices; no separate copyright/stock-photo credits or reuse restriction were identified. Photographs remain in context in the whole handbook; this is not a separate license for extracting images. | `usda-policies-2026-10-30-extracted.json`; `usda-kitchen-companion-gpo-2026-10-30.xml` |
| CDC | Agency-authored one-page fact sheets, with agency identification and no third-party copyright/image credits identified. CDC's public-domain content policy requires agency attribution, unchanged substantive content, a non-endorsement disclaimer and notice that originals are available free from CDC. Contractor/licensed-image and logo exceptions remain applicable; no blanket license for CDC images is asserted. | `cdc-agency-materials-2026-10-30.html` |
| CPSC | CPSC's copyright notice permits copying brochures with credit and no implied endorsement. Its guide-reuse FAQ explicitly identifies CPSC safety guides as public domain and allows use in their entirety. Complete-page inspection found a warning-label diagram but no photographs or third-party credits. | `cpsc-copyright-2026-10-30.html`; `cpsc-guides-reuse-2026-10-30.html` |

All evidence files have their own exact URLs, UTC retrieval dates, response-body sizes and SHA-256 values in the batch record and/or the documents' `rights_evidence` arrays. Existing rights snapshots were not overwritten.

**USDA policy transport limitation:** Direct policy HTML/browser access was denied. `usda-policies-2026-10-30-extracted.json` preserves the successful `web_extract` publisher-page text response and its retrieval timestamp. It is explicitly **not raw HTML**; the service did not expose a verified final HTTP URL, so that field is null rather than fabricated. The full extracted policy, including its exceptions and trademark notice, is retained.

## Preservation and search derivatives

- Each installed PDF is a byte-for-byte copy of its successful source download. Figures, tables, warning text, agency notices and surrounding pages are retained.
- Extraction used the existing `/tmp/gravestone-ingest` environment: **pypdf 6.21.4**, with **fonttools 4.68.0** available. Text is exactly `page.extract_text() or ''`, joined with U+000C form feeds and encoded as UTF-8. Empty text pages remain represented, preserving physical PDF page numbers used by search. There is no AI rewrite, OCR pass, number/unit repair, text normalization or manually repaired table.
- The CPSC PDF carries an existing OCR layer with errors. Its derivative reproduces that layer mechanically, including missing letters and reading-order defects. **Matching hashes prove bytes, not transcription accuracy.**
- Every new manifest record explicitly labels extraction **UNVERIFIED**. Source-page review for provenance/rights/completeness does not certify the search transcription or the safety/medical/electrical substance.
- A lightweight **pypdfium2 5.14.0** renderer was added only to the temporary ingestion environment for independent PDF/page/render checks; it is not an app/build dependency. Review images and acquisition staging remain outside the repository. No shared service was started, stopped or modified.

## Limited source-backed coverage, not completion

Only these four topic records moved to `partial-source-backed`:

- `food-storage`: USDA food-storage chapter, physical PDF pages 13–16 / printed pages 11–14, including the complete shelf-stable-food page and associated warnings. This does not fulfill a complete food-stockpile, home-preservation, nutrition or dietary-needs reference.
- `drinkable-water`: the new limited CDC water/disaster fact sheets plus the existing CDC emergency-water original. Field-source identification, chemical testing and complete treatment-system selection remain gaps.
- `sanitation`: CDC handwashing, safe-water use and disaster-hygiene fact sheets. Comprehensive toilets, sewage and waste-management material remain gaps.
- `solar-generators`: **generator hazards only**, CPSC page 1. Solar setup and PV/battery design remain unfilled.

All other requested topics and uncertain wording remain intact. No topic is marked complete, and no weapons/combat/intrusion material was acquired. No private notebooks, original topic photograph, or conversation excerpts were copied.

## Not admitted / unresolved

- **Solar:** DOE/NREL's complete 16-page *Own Your Power! A Consumer Guide to Solar Electricity for the Home* was downloaded for review from https://www1.eere.energy.gov/solar/pdfs/43844.pdf but **not installed**. Its January 2009 edition identifies preparation by NREL, operated by Alliance for Sustainable Energy, LLC, and contains photographs. DOE's policy distinguishes government information from private/contractor material. A document-wide redistribution basis covering the contractor work and images was not established; historical prices/incentives also require care. The policy response is archived as `doe-web-policies-2026-10-30.html`, and the candidate's actual downloaded hash/page count is recorded in the batch audit. No candidate PDF or candidate derivative is distributed in `content/`.
- **OSHA:** The direct *Using Portable Generators Safely* PDF returned HTTP 403 in normal and browser retrieval; the official legacy `obis` endpoint timed out. No partial/error response was admitted. CPSC's complete direct-publisher generator sheet supplies bounded hazard coverage instead.
- **Equipment-specific power information:** generator manufacturer manuals, electrical standards, transfer equipment, battery-system safety, PV wiring and sizing are not supplied by this batch. A source-backed hazard sheet is not an installation procedure.
- **Dependencies and currency:** linked publications, websites, standards and equipment manuals are not automatically installed. Each new manifest entry records those limits. The USDA 2015, CDC 2018/2022 and CPSC 2021 editions are preserved as dated sources, not represented as newly reviewed or universally current guidance. No qualified medical/electrical/safety review was performed.

## Verification

Content work does not change the application, tests, build files, existing publisher bytes, release state, or a user's USB. No new ISO was built; an already-flashed image is not updated by these repository files. Other concurrently modified application/test files belong to the parent task and were not edited by this acquisition worker.

Executed checks:

- `python3 -B -m unittest discover -s tests -p 'test_content.py' -v` — **1 test, OK**, including original-document and map integrity.
- `python3 -B -m unittest discover -s tests -v` — **49 tests, OK (skipped=2)**. The installed-AI-package and real-inference tests require explicit environment variables and were skipped; this is not inference, ISO, boot, or physical-hardware verification.
- `/tmp/gravestone-ingest/bin/python -B /tmp/gravestone-verify-practical-batch.py` — **passed**: all seven installed PDF and derivative hashes, map and original-map archive hashes, all six new rights/provenance evidence hashes, PDF headers/EOF markers, independent pypdf/PDFium page counts, all **54 new pages rendered**, and exact regeneration of all five new derivatives in the pinned ingestion environment. The local harness/result are retained in `/tmp/gravestone-practical-batch/` for this session; manifest hashes and the durable batch audit remain the repository provenance record.
- Five production keyword-retrieval smoke queries located the expected new sources at actual physical PDF pages: `botulism` → USDA page 16 (also its index at page 47); `local water advisory` → CDC safe-water page 1; `lather` → CDC handwashing page 1; `diarrhea` → CDC disaster-hygiene page 1; `backfeeding` → CPSC page 1. The model endpoint was intentionally rejected before connection, exercising keyword-only retrieval without using or changing a shared inference service. These are discoverability checks, not search-quality or safety certification.
- All pre-existing originals, derivatives, map bytes and rights snapshots match a pre-acquisition hash baseline. The two existing document records and map record remain equal to the original manifest. All topic IDs/titles and out-of-batch pending topic records remain unchanged; no topic is complete.

Verification caveats: a publisher PDF produces pypdf's non-zero-indexed-xref warning; PDFs were not repaired or rewritten, and independent PDFium page loading/rendering succeeded. An initial derivative-regeneration probe used the host's pypdf **6.19.0** without fonttools and failed byte comparison. Running the check in the actual ingestion environment (**pypdf 6.21.4 + fonttools 4.68.0**) regenerated every new derivative exactly. Reproduce with the recorded environment, not an assumed host toolchain. The initial retrieval smoke assertion also exposed an incorrect editorial claim about container sanitation in the safe-water sheet; that claim and the test query were corrected from the actual original/extracted text, without modifying any publisher bytes or inventing missing guidance.
