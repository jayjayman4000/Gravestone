# Gravestone Retrieval API

## Overview

The `command_search` function provides keyword-based search over the Gravestone original-source library with optional local-model keyword suggestions. It never generates substantive survival answers; every result is a mechanically sliced excerpt from an original document page, and the UI must always display the unverified-context warning.

## Function Signature

```python
def command_search(
    content_dir: str | Path,
    query: str,
    *,
    model_url: str = 'http://127.0.0.1:8767',
    timeout: float = 20
) -> dict
```

## Return Value

JSON-safe dictionary with these keys:

| Key | Type | Description |
|-----|------|-------------|
| `query` | string | Echo of the input query (empty string if invalid). |
| `mode` | `'ai-assisted' \| 'keyword-only'` | `'ai-assisted'` only when a local model round-trip succeeds and returns valid terms; otherwise `'keyword-only'`. |
| `model_status` | string | One of: `'available'` (successful round-trip), `'unavailable'` (HTTP ≠ 200), `'timeout'`, `'invalid-response'` (malformed JSON, oversize body, recursion, missing `choices`), `'invalid-url'` (non-loopback, auth, path, query, fragment, wrong scheme, host override), `'not-called'` (query empty, >2048 chars, or no meaningful terms after stop-word removal). |
| `terms` | string[] | Combined de-duplicated search terms: original query terms first, then up to 4 model suggestions (single-word nouns, no phrases, no stop-words, ≤48 chars). |
| `results` | object[] | Up to 10 hits, each with: `id`, `title`, `publisher`, `file`, `page` (1-based), `excerpt` (≤600 bytes from original page), `score` (original-term matches weighted 100×; phrase match +200), `matched_terms` (all terms found on that page). |
| `warning` | string | `Machine-extracted search preview — not verified; open the original document and read full context.` |
| `message` | string | Human-readable status: model supplied keywords / keyword-only fallback / enter meaningful words / library gap. |

## Loopback Model Contract

- **Only** `http://127.0.0.1:*`, `http://localhost:*`, `http://[::1]:*` accepted. Any other host, `https`, auth, path, query, fragment, or port override is rejected before any connection (`'invalid-url'`).
- POST `/v1/chat/completions` with JSON body containing `messages`, `temperature=0`, `max_tokens=128`, `response_format={"type":"json_object"}`, `chat_template_kwargs.enable_thinking=false`.
- System prompt instructs model to emit **only** `{"terms":["keyword"]}` JSON; no advice, no corpus text, `/no_think` appended.
- Response body capped at 32 KiB; timeout capped at 20 s (parent default).
- Completion is parsed defensively: `think` blocks stripped, fenced JSON accepted, max 4 single-word nouns, no stop-words or generic preparedness words.
- Model failures fall back to **keyword-only** immediately; no retry, no remote fallback.

## Search Ranking

1. Only pages containing at least one **original** query term are admitted (AI terms refine ranking but never admit a page).
2. Exact multi-word phrase match of original terms → +200 score.
3. Each original term match → +100 score.
4. Each additional AI term match → +1 score (capped at +4).
5. Results sorted by score descending, capped at 10.
6. Excerpt window centred on phrase match or densest original-term cluster, clipped to 600 bytes.

## Safety Invariants

- **No generated answers.** `excerpt` is always a substring of the original page text (split on form-feed `\f`).
- **Original bytes only.** Uses `read_manifest` / `read_text` / `open_file` which enforce path containment, symlink rejection, 16 MiB text cap.
- **Library gap reported.** When no pages match, `message` explicitly states coverage gap; no advice.
- **No corpus leakage.** The model never sees document text; prompt is generic keyword task.

## Environment

- `GRAVESTONE_MODEL_URL` overrides the default `http://127.0.0.1:8767` when the caller passes the default.
- Tests may override via `model_url=` argument or `GRAVESTONE_MODEL_URL` env var.
- CI uses a fake HTTP fixture (`tests/test_retrieval.py::model_server`) — not a real model.

## Tests

Run with:

```bash
python3 -m unittest discover -s tests -p test_retrieval.py -v
```

All 11 tests must pass:
- Exact substring / page match
- AI-assisted round-trip only proposes terms
- Transport failures fall back plainly without raw completion
- Model terms bounded / sanitized
- Ranking prefers original phrase; AI cannot add unanchored pages
- Preview chooses query-relevant cluster without full phrase
- Unsafe/unavailable sources report library gap
- Duplicate manifest entries deduplicated; results capped at 10
- Queries without meaningful terms do not call model
- Default timeout 20 s and `GRAVESTONE_MODEL_URL` honoured
- Remote/ambiguous URLs rejected before connection

## Integration

Parent server mounts this as:

```python
from app.retrieval import command_search
# GET /api/command?q=...
result = command_search(content_dir, query)
```

Frontend displays `results[]` with `warning` and `message`; never treats excerpts as authoritative instructions.