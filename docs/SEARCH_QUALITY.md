# Search quality: real-source ranking benchmark

This measures **keyword retrieval ranking**, not AI answer quality, safety accuracy,
transcription accuracy, source currency, or emergency readiness. Retrieval returns
source-only previews; it does not generate substantive advice.

## Fixed corpus and judgments

`tests/fixtures/search-relevance.json` pins the original seven publisher documents
from `02b8f00ef2fea78a0702169ff986282efc7cd4d2`: FEMA *Are You Ready?*, USDA
*Kitchen Companion*, CDC *Make Water Safe*, *Use Safe Water*, *Wash Your Hands*,
*Preventing Diarrhea*, and CPSC *Portable Generator Hazards*.

The fixture contains 16 stable question IDs, queries, editorial relevant-page
judgments, and exact evidence strings checked against inspected derivatives.
Page numbers are **physical PDF pages**, not printed page labels. Original and
text-derivative SHA-256 hashes are pinned independently. Labels identify pages
with substantive material for the query, not mere cross-references or indexes;
they are nonexhaustive, not qualified safety review. Questions are search prompts,
not instructions. No survival content was rewritten or added by this change.

The evaluator copies the selected corpus into a temporary snapshot, validates the
actual copied original/derivative bytes against the pins, and runs every query
against that frozen view. Changes during copying are rejected. Default `original`
mode ignores later admissions and preserves original manifest order. Pin or case
changes require explicit review; do not silently rebaseline them to improve scores.

## Repeat the evaluation

From the checkout:

```sh
python3 scripts/evaluate-search.py   --output /home/jayjayman4000/gravestone-test-evidence/search-quality/current-original.json
python3 scripts/evaluate-search.py --corpus expanded   --output /home/jayjayman4000/gravestone-test-evidence/search-quality/expanded-current.json
python3 -m unittest discover -s tests -p test_retrieval.py -v
python3 -m unittest discover -s tests -p test_search_relevance.py -v
python3 -m unittest discover -s tests -v
```

`--content-dir PATH` selects a separately captured corpus; `--fixture PATH` selects
an explicitly reviewed benchmark version. The evaluator always passes
`model_url='http://example.invalid'`: URL validation rejects it before any
connection. No inference server, environment model URL, network, or stochastic
completion affects this benchmark. Identical code/corpus/fixture produce identical
JSON, without timestamps or timings. Reports retain all ranked hits and exact
previews, case IDs, relevant ranks, source/derivative hashes, fixture hash, and
retrieval implementation hash.

Metrics are macro-averaged across questions. Hit@k means any judged relevant
physical page appears among the first k results. MRR@10 is the reciprocal rank
of the first judged relevant page (zero if absent from ten returned hits).
Precision@3 uses a fixed denominator of three. Judged-page recall@10 measures the
fraction of annotated pages returned per question. Unlabeled pages count as
nonrelevant for these calculations, which is a limitation, not a source verdict.

## Diagnosis and test-first fix

The one-command reproduction searched `safe drinking water` in the original
corpus. FEMA physical page 20 (largely evacuation and supplies) ranked first,
while CDC water guidance first appeared at rank 3. Each received score 300:
the old score counted distinct words anywhere on the entire physical page, then
left ties in manifest order. On FEMA page 20, first `safe`, `drinking`, and `water`
occurrences were at offsets 935, 1956, and 1221; they could not fit in one preview.
Preview candidates based only on each word's first occurrence also missed later,
more useful clusters.

A real-corpus regression was written and observed failing **before** ranking code
changed. The fix considers every original-term occurrence with a sliding window:

1. Maximize distinct original-query terms fitting within 600 physical characters.
2. Among equally covered clusters, prefer a shorter span. Collapse layout
   whitespace **only for scoring**, never in returned source text.
3. Score local original coverage first, then a bounded phrase/proximity bonus;
   whole-page original matches and up to four accepted model terms are small
   secondary signals. Extra model terms cannot admit an unanchored page.

No document IDs, titles, publisher preferences, or query-specific rules occur in
the ranker. The excerpt is an untouched substring of the corresponding physical
page, at most 600 characters, with enough leading context to retain the complete
selected cluster. Existing loopback-only URL validation, timeouts, result cap,
original-file checks, and source warnings remain intact.

A separate test-first change makes a successful model round-trip with no accepted
new keywords report `model_status: available`, `mode: keyword-only`, and an
explicit no-accepted-keywords message. `expansion_terms` exposes accepted additions
separately from combined `terms`; `ai-assisted` requires at least one addition.
Accepted terms or that mode still do **not** establish a ranking benefit.

## Local-model total deadline and keyword fallback

The local-model timeout is a **total monotonic budget**, clamped to the existing
0.01–20 second range, not a fresh inactivity allowance for each socket operation.
Numeric-loopback URL validation (including mapping `localhost` to `127.0.0.1`)
remains unchanged; remote hostnames are rejected before connection, not resolved.
Connect uses the bounded socket timeout; its elapsed time is deducted before a
per-request timer covers request transmission, response headers and response body.
The timer calls `shutdown(SHUT_RDWR)` on the captured connected socket to interrupt
blocked I/O. It does not depend on `connection.sock` remaining attached after
`getresponse()`; `Connection: close` can detach that attribute before body reading.
Monotonic checks also reject completions that finish after the deadline. Shutdown
EOF/parse errors after expiry report `model_status: timeout`, not bad JSON.

Every exit cancels and joins the timer, closes any response and connection, and
closes the captured socket. No process-wide alarm, socket default, background
inference worker or uncancelled timer is used. The 32 KiB JSON response bound is
unchanged. Timeout still returns keyword-only retrieval, no expansion terms and
only exact original-page excerpts; ranking and the zero-new-keywords contract
are untouched.

The regression was run **before production code changed** using real loopback HTTP
fixtures, explicitly **not actual inference**. Headers and bodies arrive in 10 ms
drips, each below the 120 ms inactivity allowance. All three cases (headers, body,
and body with `Connection: close`) incorrectly reported `available` after
0.724–0.836 seconds. They now require `timeout`, keyword fallback, no synthetic
answer or leaked completion, and search elapsed time below a generous 0.6 seconds.
Additional checks cover valid responses inside budget, success/error/timeout
socket and timer cleanup, fixture shutdown, and isolated concurrent deadlines.

Evidence: `/home/jayjayman4000/gravestone-test-evidence/next-hardening/search-deadline-fix/`
contains `red-drips.txt`, `green-retrieval.txt`, and `full-unittest.txt`.
These timing tests establish transport fallback, not installed-model inference or
retrieval quality. Timer delivery depends on OS/Python scheduling, so this is not
a hard real-time guarantee. The budget bounds the model exchange, not subsequent
local-library scanning, and disconnecting does not guarantee cancellation of work
inside an independently running inference server. Installed-runtime acceptance
must still be rerun separately.

## Measured before/after: unchanged original seven, same 16 questions

| Metric | Before | After |
| --- | ---: | ---: |
| Hit@1 | 0.562500 | 0.750000 |
| Hit@3 | 0.937500 | 1.000000 |
| Hit@10 | 1.000000 | 1.000000 |
| MRR@10 | 0.739583 | 0.864583 |
| Precision@3 | 0.395833 | 0.458333 |
| Judged-page recall@10 | 0.979167 | 1.000000 |

Top-1 judged hits increased from **9/16 to 12/16**. Five first-relevant ranks
improved and none worsened: safe drinking water 3→1; hands/soap 6→3; sanitizer
2→1; food/power outage 2→1; evacuation/shelter plan 3→2. All **158 previews** in
each run were checked for exact physical-page substring membership and the
600-character cap. The safe-drinking-water result now starts with CDC guidance,
not FEMA's evacuation passage.

Evidence is outside the checkout at
`/home/jayjayman4000/gravestone-test-evidence/search-quality/`:

- `original-corpus/`: unchanged seven-document snapshot including original PDFs.
- `before.json`, `after.json`, `comparison.json`: baseline, improved, and deltas.
- `retrieval-before.py`, `red-real-corpus.txt`: captured baseline code and initial
  failing real-corpus test, before production changes.
- `verify-baseline.py`, `baseline-regressions.txt`: current focused regression
  assertions exercised against the captured baseline (four expected failures).
- `current-original.json`, `expanded-current.json`: distinct current evaluations.
- `full-unittest.txt`: full-suite execution log (optional installed-model,
  real-inference, and official Census-download checks are skipped by default).

## Limitations and expanding corpus

This is a small, development-visible regression set, **not a held-out benchmark**.
Labels were based on actual machine-extracted pages, not invented expected pages;
extraction defects and incomplete judgments remain. No actual model inference
quality or semantic retrieval gain is claimed.

Cross-references and contents pages can still outrank substantive pages. The
internal-temperature chart remains rank 2 behind a reference to it; the family
communication page remains rank 2 behind the contents. The hands/soap question
still first reaches a labeled page at rank 3. The metric floor in tests protects
this demonstrated result, not universal relevance.

`--corpus expanded` retains the same original judgments but searches every current
manifest document and records extra IDs/hashes. Newly relevant pages are not yet
judged and can displace original hits, so expanded-corpus metrics must **not** be
compared with the original-seven baseline as evidence of a regression or benefit.
During development, a newly admitted EPA water page actually became the top hit;
the real-source regression was therefore isolated to the pinned seven, rather
than falsely declaring that new page irrelevant or inventing an annotation.
Review and version expanded relevance labels separately before making claims
about added coverage or model-assisted ranking.
