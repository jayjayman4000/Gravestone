# Practical source acquisition

## Historical engine-repair addition — current checkout

Batch `historical-engine-repair-2026-10-31` admits the complete U.S. War Department **TM 9-1803A**, *Ordnance Maintenance: Engine and Engine Accessories for 1/4-Ton 4x4 Truck (Willys-Overland MB and Ford GPW)*, dated **24 February 1944**. It adds **84 physical PDF pages / 8,888,550 original bytes**, bringing the checkout to **12 PDFs / 449 physical pages**. The eleven earlier originals and derivatives remain byte-identical. This is not a rebuilt ISO or an update to an already flashed USB.

- Original: `content/originals/war-department-tm9-1803a-1944.pdf`; SHA-256 `91a303b1defb65bdc7df003d307aa902b8cb5ff2afeaa2a15f19830fdc5ae669`.
- Official PDF: https://www.govinfo.gov/content/pkg/GOVPUB-W-450a1aabcc48d92a6585299c93126bb8/pdf/GOVPUB-W-450a1aabcc48d92a6585299c93126bb8.pdf
- GPO's work-specific MODS/Content Details explicitly declare this work not subject to copyright under 17 USC 105. Preserved raw MODS, PREMIS, Content Details and statute snapshots have their own recorded hashes/URLs/times. PDF size and SHA-256 match GPO's PREMIS PDF-object fixity record. This is not a hosting-only rights inference; no government/manufacturer endorsement or ownership of marks is asserted.
- Actual scope: historical engine removal, disassembly, inspection, repair, assembly, installation and clutch service (physical pages 10–73; printed 8–71). A full-size check of physical page 27 confirms illustrated water-pump disassembly material, not insurance text or diesel theory. Existing source warnings, figures, references, blanks and OCR defects remain unchanged.
- **Limits:** specific 1940s gasoline-engine models, not modern all-vehicle repair. Written for trained maintenance personnel; obsolete materials/practices and specialist-tool assumptions remain. Separate electrical, carburetor, hydraulic-brake, fuel-pump and chassis manuals are not bundled. No qualified mechanical safety review; never transfer dimensions/torques to another engine. GPO's 84 digital pages and 77 printed pages are distinct pagination concepts, not an asserted loss of pages.
- Search derivative: `content/search/war-department-tm9-1803a-1944.txt`, exact existing OCR extraction using pypdf 6.21.4/fonttools 4.68.0, all 84 physical-page segments retained including blank physical page 83. **UNVERIFIED**, not a checked transcription or new AI-authored procedure.

`content/rights/historical-engine-repair-2026-10-31.json` records admission; `content/coverage.json` marks vehicle repair only partially source-backed. Staging, all-page render inventory, selected full-size images, extraction regeneration and parent admission evidence are in `~/gravestone-test-evidence/practical-repair-followup/`. The USMC diesel-theory candidate remains staged; the GM/Terex-derived mechanic manual remains quarantined for unresolved rights.

## Earlier four-document expansion — 2026-10-31

Batch `practical-expansion-2026-10-31` adds **four complete publisher PDFs, 274 physical pages, 8,016,554 original-file bytes**. The seven pre-existing PDFs and their derivatives remain untouched. The catalog now has **11 PDFs / 365 physical pages**; map data and rights snapshots are not documents. These are checkout additions, not a rebuilt or shipped ISO.

| Source ID / original under `content/originals/` | Pages | Bytes | Edition |
| --- | ---: | ---: | --- |
| `fema-cert-2019.pdf` | 268 | 5,509,166 | FEMA *CERT Basic Training Participant Manual*, August 2019 / 2019 Update |
| `epa-emergency-disinfection.pdf` | 2 | 754,723 | EPA Office of Water, EPA 816-F-15-003, September 2017 |
| `epa-wells-after-flood.pdf` | 3 | 743,298 | EPA Office of Water, *What to Do After the Flood*, EPA 816-F-05-021, August 2005; updated October 2024 |
| `cdc-backcountry-treatment.pdf` | 1 | 1,009,367 | CDC *Drinking Water Treatment Methods for Backcountry and Travel Use*, February 20, 2009 |

Each has a same-basename `.txt` derivative in `content/search/`. `content/manifest.json` records exact request and final URLs, UTC retrieval times, publisher edition, byte size, page count, original and derivative SHA-256, source dependencies and document-specific rights basis. `content/rights/practical-expansion-2026-10-31.json` retains the admission/exclusion audit. No AI-written procedures, answers, OCR repairs or replacement pages were added.

### Agency authorship and work-specific rights checks

- **FEMA:** the actual introduction identifies the National CERT Program Office and the 2019 update; PDF Author is FEMA. The archived FEMA Reuse and Copyright policy permits copying/distribution but excludes restricted or licensed graphics. Complete extracted-text credit searches and selected cover, medical, sanitation and illustration renders found no third-party copyright/photo credits or contractor authorship notice. **Physical page 169 contains a sample manufacturer label with the UL registered certification mark**; it remains only in the intact reference, not extracted, used as branding, or relicensed. This is not a claim of ownership of marks or a blanket license for FEMA-site images. The historical LAFD program origin and references to outside training are preserved; no Red Cross manual is bundled.
- **EPA:** Office of Water authorship appears in both originals' printed publication identifiers and PDF metadata; the private-well publication also has an official publisher listing. The reuse basis is federal agency authorship under 17 USC 105, not `.gov` hosting alone. EPA's archived disclaimers explicitly warn that individual works/third-party content can differ; all five EPA pages, images and notices were reviewed, with no third-party copyright/photo credits or contractor attribution identified. No standalone image license is asserted.
- **CDC:** the work-specific CDC Stacks record explicitly labels this particular sheet **Public Domain**, identifies CDC as corporate author and supplies its date/download/checksum. The entire one-page original was reviewed for third-party exceptions; none identified. The MIOX registered product name remains contextual, not branding or endorsement. Attribution, free-availability, unchanged substantive content and non-endorsement notices apply as recorded in the manifest and `THIRD_PARTY_NOTICES.md`.

Six new raw HTTP response-body snapshots under `content/rights/` preserve FEMA, CDC, EPA and federal copyright policies plus the CDC work-specific provenance record and EPA well-publication listing. Each snapshot has request/final URL, UTC time, size and hash in the batch audit and relevant manifest records. These U.S. reuse determinations do not certify foreign rights or qualified legal review. Agency and third-party marks are not Gravestone branding, and no endorsement is implied.

### Transport and source defects retained honestly

- Ready.gov redirected the CERT request to `www.ready.gov`; both literal URLs are recorded. EPA PDFs downloaded directly with Python urllib.
- CDC Stacks and some policy endpoints returned **403 to urllib**. A real browser could retrieve the CDC sheet, its provenance page and FEMA/CDC policies. Browser Fetch response bodies were base64-transported without changing bytes; final response URLs, sizes and hashes are recorded. This is an actual PDF download, not reconstructed text or a browser printout. The source archive's SHA-512 was independently checked during verification.
- The CDC water sheet has **unrelated embedded National Health Statistics Reports/pulse-rate metadata**. Its visible title/footer, Stacks description and archive checksum identify the actual one-page work. The binary metadata is not repaired. Its existing OCR/text layer has spacing, symbols, table-order and numeric-recognition errors; the derivative preserves them exactly and is **UNVERIFIED**.
- EPA's September 2017 sheet contains an inconsistent altitude unit pairing on page 1. The publisher original and exact derivative are retained without numerical correction. Historical editions and differences between sources have not been reconciled or certified as current instructions.
- CERT is a course participant manual requiring training/practice and local protocols, not a standalone first-aid/CPR certification. Whole-manual context, nonmedical units, diagrams, exercises, warnings and empty physical pages remain intact.

### Coverage added, not certified complete

Actual-document associations only: `water-filtration` → CDC page 1; `finding-water` → EPA emergency page 2 and the post-flood well document pages 1–3; `drinkable-water` → both EPA originals and the CDC sheet; `sanitation` → CERT pages 134–135 (printed 4-11–4-12) alongside existing CDC sheets. New editorial topics `first-aid` and `shelter` associate CERT medical pages 99–117 / 124–136 (printed 3-1–3-19 / 4-1–4-13) and sheltering pages 32–33 / 35 (printed 1-19–1-20 / 1-22), respectively. These page associations are catalog metadata, not generated safety summaries. All pre-existing topic IDs and titles are preserved.

**Still missing:** equipment-specific power manuals, solar/PV/battery installation, comprehensive source testing and field-water locating, wilderness shelter construction, complete municipal sewage/waste management and a current comprehensive first-aid/clinical reference. The existing CPSC generator-hazards source remains the only admitted topic-specific power reference. No topic is complete.

**Excluded:** Honda EU22i manual requires written reproduction permission; none obtained. Prior NREL contractor/photo-rights exclusion remains unchanged. USGS Circular 1332 has indexed iStock photo credits; no document-wide reuse basis established. OSHA3286 browser PDF fetch returned 403 (consistent with prior blocked retrieval). CDC hurricane manual direct/alternate requests were blocked and not admitted. Red Cross/ACS copyrighted manuals remain excluded absent a suitable license. See `docs/SOURCE_CANDIDATES.md` and the batch audit.

### Reproduction and local evidence

Pinned ingestion environment verified: **pypdf 6.21.4, fonttools 4.68.0, pypdfium2 5.14.0**. Pillow 12.0.0 was added only to `/tmp/gravestone-ingest` for review-image creation; no app/build dependency changed. Every physical page is represented as `page.extract_text() or ''`, joined with U+000C form feed, UTF-8 encoded, without OCR, correction or normalization. Byte identity is not transcription accuracy.

Local scripts, successful download metadata, baseline hashes, selected-page PNGs and review/verification evidence are in `/home/jayjayman4000/gravestone-test-evidence/library-expansion/`. No private notebook data was read or copied. No app/test/build files, existing originals, release state or USB media were changed by this worker; no build, commit or push was performed.

Verification executed successfully:

- `python3 -B -m unittest discover -s tests -p 'test_content.py' -v` — **1 test, OK**.
- `python3 -B -m unittest discover -s tests -v` — **99 tests, OK (skipped=3)** against the live shared checkout. Installed-model artifact verification, real model inference and opt-in official Census downloading were skipped. This is not ISO/USB/physical-hardware acceptance; the test's temporary build staging is not an image build.
- `/tmp/gravestone-ingest/bin/python -B /home/jayjayman4000/gravestone-test-evidence/library-expansion/verify.py` — **PASS**: all 11 original/derivative manifest hashes, all 11 independent pypdf/PDFium page counts, all rights-evidence hashes, map/archive hashes, exact regeneration of all four new derivatives, all **274 new pages rendered**, six new snapshot hashes, and the CDC archive's published SHA-512. New derivatives total **400,988 bytes**. All **25 pre-existing content files**, seven original source records, map record and existing topic IDs/titles remain unchanged.
- Six real `app.retrieval.command_search` keyword-only smoke queries found the expected newly installed source and physical page, and every returned excerpt was checked as an exact substring of its derivative page. The model URL was deliberately rejected before connection; no shared inference service was used. This demonstrates discoverability, not safety or relevance certification.
- **Legacy delimiter caveat:** the untouched starter `fema-are-you-ready.txt` uses `\\n\\f\\n` between pages, not the new batch's exact `\\f` delimiter. It regenerates exactly using that legacy delimiter, retains all 36 physical pages and matches its existing manifest hash. This expansion did not normalize or rewrite it.

Durable local results: `verification.json`, `unittest-full.log`, `retrieval-smoke.json`, `review-evidence.json` and the reviewed PNGs in the evidence directory above. Only the owned content/provenance/doc files were edited by this worker; concurrent app/tests/scripts changes belong to other workers.

## Historical acquisition — 2026-10-30

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

## Water and antenna originals — 2026-11-05, current checkout admission

Recovered completed intake outside the checkout and independently checked original byte lengths, SHA-256, parsed physical pages, embedded rights, exact README/license bytes and GCARC Git blob identifiers. Admitted only the five candidates below; every other restricted or unresolved intake work remains outside the public checkout.

| Original / manifest ID | Physical pages | Scope and rights |
|---|---:|---|
| `cawst-biosand-2009` | 129 | September 2009 Version 10.0 concrete household biosand filter; explicit CC BY 3.0 grant on p3. SSWM mirror provenance retained, not current publisher-byte equivalence. |
| `kuphaldt-radio-antennas` | 131 | September 2026 ModEL edition; CC BY 4.0 on p1 and full Appendix D. Illustrated 902–928 MHz monopole case and antenna theory. |
| `meshtastic-915-yagi` | 4 | GCARC 915 MHz US Meshtastic assembly; CERN-OHL-P v2 project declaration. |
| `meshtastic-915-yagi-bom` | 1 | Same project purchasing BOM, not an independent complete build guide. |
| `meshtastic-915-yagi-elements` | 3 | Same project element preparation supplement; resolves kit-specific omission in basic instructions. |

New originals: **5 PDFs / 268 pages / 5,628,172 bytes**; FF-separated search derivatives: **413,264 bytes**. Current complete checkout: **18 PDFs / 719 pages / 30,869,919 original bytes**, excluding map and rights evidence. Every physical PDF page has a corresponding derivative segment, including empty text pages. Extraction uses existing `/tmp/gravestone-ingest` environment (pypdf 6.21.4, fonttools 4.68.0); no install or download was needed. Original bytes are never regenerated.

Rights applicability: GCARC README's express hardware-design declaration was checked against exact same-repository instruction/BOM/supplement blobs. They are design Source under §1.2, not merely a nearby third-party manual. Full README and CERN-OHL-P v2 bytes accompany them, retaining copyright, acknowledgments and disclaimer Notices. Original PDFs are unchanged (§3.1), separate extraction changes are dated/described (§3.3), original license retained (no MIT relicense), and no downstream restrictions added (§2.3). The permissive variant does not require conveying an entire CAD kit; this does **not** establish fabrication readiness. See `THIRD_PARTY_NOTICES.md` and the batch audit for conditions and limits. No qualified legal, RF, medical or safety certification is represented.

Coverage updates are limited to actual filter construction/operation/maintenance and 900/915 MHz antenna documents. New `water-filter-construction` is an explicitly editorial label responding to a later request, **not attributed to the old handwritten image**. CAWST disinfection/training/follow-up requirements remain dependencies. Its p111 checklist discrepancy (0.6 L/min maximum vs 0.4 L/min target and other pages) is preserved, not harmonized. GCARC models/graphs/software are absent; no claim of GMRS, VHF/UHF or broadcast-FM build coverage. No topic is complete.

Verification retained outside checkout at `/home/jayjayman4000/gravestone-test-evidence/expanded-admission/`: original/baseline hashes, per-page extraction, rights review logs/contact sheets, exact derivative regeneration, all **268 pages decoded/rendered by PDFium** at low resolution, independent PDF parser page counts, and `verification.json`. All previous document records, map and pre-existing source/rights/derivative bytes remained unchanged. HTTP `/api/library`, literal `/api/search` and keyword-only `/api/command` were exercised for every new source, checking original-page substring excerpts. Five original PDF HEAD/GET responses had correct MIME/length and byte-identical SHA-256 readback. Model URL was intentionally rejected before connection; no shared inference service changed. Content tests: **2 passed**; literal-page test: **1 passed**; command API test: **1 passed**. These are not semantic search-quality certification.

**Remaining gates:** actual Firefox open/read/page/return acceptance, qualified source/safety review, exact-ISO packaging/payload checks and physical USB persistence remain unperformed. HTTP readback and native PDFium rendering are **not Firefox rendering**. No ISO, build, commit, push, host or UI changes in this admission; existing image artifacts do not contain these additions.
