# Source replacement status — 2026-11-05

The five AI-written search files (`survival-bowmaking.txt`, `survival-skinning-butchering.txt`, `survival-firearm-repair.txt`, `survival-blackout-grid-down.txt`, `SURVIVAL_GUIDES_INDEX.txt`) were removed from the local checkout. They are not authentic retrieved sources and must not be restored or used as authoritative instructions.

## Admitted

- FEMA, *Be Prepared for a Power Outage*, May 2018, two complete original pages: `content/originals/fema-power-outage-2018.pdf`. Mirror provenance, edition caveat, reprint-policy evidence and hashes are in `content/manifest.json`. Search derivative is machine-extracted, not an authored guide. Content tests passed and keyword search returned both pages.

## Downloaded, not admitted

- Saxton T. Pope, *Hunting with the Bow & Arrow*: original illustrated Gutenberg HTML ZIP and embedded license, outside repository at `/home/jayjayman4000/gravestone-source-intake/field/`. Work-specific Gutenberg record identifies public domain in USA. ZIP integrity checked; bowmaking chapter found. Requires supported offline-reader integration and appropriate historical caveats before admission; do not call it installed/searchable or a PDF.
- Baofeng UV-5R manual (52 pages), Icom IC-2300H manual (66 pages), IC-718 basic (32 pages) and advanced (27 pages): publisher originals retained outside repository at `/home/jayjayman4000/gravestone-source-intake/radios/`. Exact provenance and rights evidence in `provenance.json`. Parent independently checked byte counts, SHA-256 and PDF page counts. Baofeng requires prior written distribution consent; Icom download terms prohibit public distribution/third-party transfers. No permission acquired. Do not bundle these in the public repository/ISO. Official download pages remain available to individual users.

## Remaining gaps

- Field dressing/skinning: no source admitted. UF/IFAS *Wild Game: Safety and Quality in the Field*, https://ask.ifas.ufl.edu/publication/FY1503, was located through web extraction; direct urllib retrieval loops on redirects. Source PDF acquisition and reuse/currency review remain unresolved.
- Firearm maintenance: no replacement source acquired/admitted. Use model-specific manufacturer safety/owner maintenance material, not AI-generated repair/fabrication procedures.
- No new ISO built, pushed, or claimed to include this batch. Existing GitHub artifacts predate these local changes.
