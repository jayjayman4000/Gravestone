#!/usr/bin/env python3
"""Deterministic real-source ranking evaluation. Never calls a model/network."""
import argparse
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.retrieval import command_search  # noqa: E402

FIXTURE = ROOT / 'tests/fixtures/search-relevance.json'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@contextmanager
def corpus_view(content_dir, fixture, corpus):
    """Freeze selected manifest entries and their bytes before running any query."""
    manifest = json.loads((content_dir / 'manifest.json').read_text())
    by_id = {doc['id']: doc for doc in manifest['documents']}
    pinned = fixture['documents']
    for expected in pinned:
        actual = by_id[expected['id']]
        for key in ('file', 'text_file', 'pages'):
            if actual[key] != expected[key]:
                raise ValueError(f"Pinned {expected['id']} changed {key}")
    documents = ([by_id[doc['id']] for doc in pinned] if corpus == 'original'
                 else manifest['documents'])
    with tempfile.TemporaryDirectory(prefix='gravestone-search-eval-') as temporary:
        view = Path(temporary)
        for doc in documents:
            for key in ('file', 'text_file'):
                # Benchmark only uses ordinary local corpus paths, never traversal.
                relative = Path(doc[key])
                if relative.is_absolute() or '..' in relative.parts:
                    raise ValueError('Unsafe corpus path')
                target = view / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(content_dir / relative, target)
        # Validate the bytes actually searched, not a raceable pre-copy check.
        for expected in pinned:
            for key, hash_key in (('file', 'sha256'), ('text_file', 'text_sha256')):
                if digest(view / expected[key]) != expected[hash_key]:
                    raise ValueError(f"Pinned {expected['id']} changed {key} bytes")
        (view / 'manifest.json').write_text(json.dumps({'documents': documents, 'map': {}}))
        yield view, documents


def evaluate(content_dir, fixture_path=FIXTURE, corpus='original'):
    fixture = json.loads(fixture_path.read_text())
    cases = fixture['cases']
    if len(cases) < 10 or len({case['id'] for case in cases}) != len(cases):
        raise ValueError('Need at least ten uniquely identified cases')
    records = []
    checked = 0
    with corpus_view(content_dir, fixture, corpus) as (view, documents):
        pages = {doc['id']: (view / doc['text_file']).read_text().split('\f')
                 for doc in documents}
        for case in cases:
            relevant = {(item['id'], item['page']) for item in case['relevant']}
            for item in case['relevant']:
                if item['evidence'] not in pages[item['id']][item['page'] - 1]:
                    raise ValueError(f"Missing annotation evidence for {case['id']}")
            result = command_search(view, case['query'], model_url='http://example.invalid')
            if result['mode'] != 'keyword-only' or result['model_status'] != 'invalid-url':
                raise ValueError('Benchmark must be deterministic keyword-only, without network')
            if 'answer' in result:
                raise ValueError('Generated answer in retrieval response')
            for hit in result['results']:
                if (not hit['excerpt'] or len(hit['excerpt']) > 600 or
                        hit['excerpt'] not in pages[hit['id']][hit['page'] - 1]):
                    raise ValueError(f"Non-source preview for {case['id']}")
                checked += 1
            ranks = [i for i, hit in enumerate(result['results'], 1)
                     if (hit['id'], hit['page']) in relevant]
            records.append({'id': case['id'], 'query': case['query'],
                            'model_status': result['model_status'],
                            'first_relevant_rank': min(ranks) if ranks else None,
                            'relevant_at_3': sum(i <= 3 for i in ranks),
                            'relevant_at_10': len(ranks),
                            'judged_relevant_pages': len(relevant),
                            'results': result['results']})
        corpus_hashes = [{key: doc[key] for key in ('id', 'file', 'text_file')} |
                         {'sha256': digest(view / doc['file']),
                          'text_sha256': digest(view / doc['text_file'])}
                         for doc in documents]
    n = len(records)
    metrics = {'mrr_at_10': sum(1 / c['first_relevant_rank'] if c['first_relevant_rank'] else 0
                              for c in records) / n,
               'precision_at_3': sum(c['relevant_at_3'] / 3 for c in records) / n,
               'page_recall_at_10': sum(c['relevant_at_10'] / c['judged_relevant_pages']
                                        for c in records) / n}
    for k in (1, 3, 10):
        metrics[f'hit_at_{k}'] = sum(c['first_relevant_rank'] is not None and
                                     c['first_relevant_rank'] <= k for c in records) / n
    return {'schema_version': 1, 'corpus_id': fixture['corpus_id'], 'corpus': corpus,
            'fixture_sha256': digest(fixture_path),
            'retrieval_sha256': digest(ROOT / 'app/retrieval.py'),
            'source_commit': fixture['source_commit'],
            'document_ids': [doc['id'] for doc in documents], 'corpus_hashes': corpus_hashes,
            'extra_document_ids': [doc['id'] for doc in documents
                                   if doc['id'] not in {d['id'] for d in fixture['documents']}],
            'case_count': n, 'previews_checked': checked, 'metrics': metrics, 'cases': records}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--content-dir', type=Path, default=ROOT / 'content')
    parser.add_argument('--fixture', type=Path, default=FIXTURE)
    parser.add_argument('--corpus', choices=('original', 'expanded'), default='original')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = evaluate(args.content_dir, args.fixture, args.corpus)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'corpus': report['corpus'], 'case_count': report['case_count'],
                      'metrics': report['metrics'], 'output': str(args.output)}, sort_keys=True))


if __name__ == '__main__':
    main()
