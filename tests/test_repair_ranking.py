"""Publisher-structure labels are editorial metadata, not repair instructions.

The historical manual remains vehicle-specific, unverified OCR, and unsuitable
as a claim of current all-vehicle coverage. Never rewrite source excerpts.
"""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from app.retrieval import command_search

ROOT = Path(__file__).resolve().parents[1]
MANUAL = 'war-department-tm9-1803a-1944'
MANUAL_PIN = {
    'id': MANUAL, 'file': f'originals/{MANUAL}.pdf',
    'text_file': f'search/{MANUAL}.txt', 'pages': 84,
    'sha256': '91a303b1defb65bdc7df003d307aa902b8cb5ff2afeaa2a15f19830fdc5ae669',
    'text_sha256': '591dc4b25d12ac6a36454a47aef3945c6c0bac720b170e85fe243de1e4e46257',
}
# Physical PDF pages, independently inspected against the publisher contents,
# scope, procedure and reference/index/end leaves. No OCR keyword heuristics.
PAGE_ROLES = [
    {'start': 1, 'end': 9, 'role': 'frontmatter'},
    {'start': 10, 'end': 73, 'role': 'main'},
    {'start': 74, 'end': 79, 'role': 'reference'},
    {'start': 80, 'end': 84, 'role': 'endmatter'},
]
PAGE_ROLES_NOTE = (
    'Editorial physical-page structure annotation, not publisher text or safety review. '
    'Publisher contents physical 5 (printed 3), scope 6 (printed 4), procedural '
    'chapters 10–73 (printed 8–71), references/index 74–79 (printed 72–77), '
    'notes/blank/rear cover 80–84. Introductory scope includes audience and '
    'separate-manual dependencies; it remains required context. Never label '
    'warnings or emergency caveats as non-substantive front/end matter.'
)


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RepairRankingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        benchmark = load_module('repair_benchmark', ROOT / 'scripts/evaluate-search.py')
        earlier = load_module('earlier_pins', ROOT / 'tests/test_retrieval_coverage.py')
        fixture = json.loads(benchmark.FIXTURE.read_text())
        fixture['documents'] += earlier.EXTRA_PINS + [MANUAL_PIN]
        cls.snapshot = benchmark.corpus_view(ROOT / 'content', fixture, 'original')
        cls.view, cls.documents = cls.snapshot.__enter__()
        cls.addClassCleanup(cls.snapshot.__exit__, None, None, None)
        assert len(cls.documents) == 12
        cls.pages = {d['id']: (cls.view / d['text_file']).read_text().split('\f')
                     for d in cls.documents}
        manifest = json.loads((cls.view / 'manifest.json').read_text())
        doc = next(d for d in manifest['documents'] if d['id'] == MANUAL)
        doc['page_roles'] = PAGE_ROLES
        doc['page_roles_note'] = PAGE_ROLES_NOTE
        # Metadata overlay in an isolated copied corpus; NEVER the live manifest.
        (cls.view / 'manifest.json').write_text(json.dumps(manifest))

    def test_live_manifest_contains_reviewed_editorial_overlay(self):
        manifest = json.loads((ROOT / 'content/manifest.json').read_text())
        doc = next(d for d in manifest['documents'] if d['id'] == MANUAL)
        self.assertEqual(doc.get('page_roles'), PAGE_ROLES)
        self.assertEqual(doc.get('page_roles_note'), PAGE_ROLES_NOTE)
        for field, expected in MANUAL_PIN.items():
            self.assertEqual(doc[field], expected)

    def test_engine_repair_prefers_actual_procedure_to_scope_and_references(self):
        result = command_search(self.view, 'engine repair', model_url='http://example.invalid')
        hits = result['results']
        # Physical 44 visibly has Flywheel Assembly / Inspection and Repair;
        # 29 has water-pump Inspection and Repair; 31 piston inspection/repair.
        self.assertEqual([h['page'] for h in hits[:3]], [44, 29, 31])
        self.assertTrue(all(h['id'] == MANUAL for h in hits))
        self.assertEqual(set(h['page'] for h in hits), {5, 6, 29, 31, 44, 75, 78, 79})
        for hit in hits:
            self.assertIn(hit['excerpt'], self.pages[hit['id']][hit['page'] - 1])
            self.assertLessEqual(len(hit['excerpt']), 600)
            self.assertEqual(set(hit['local_matched_terms']), {'engine', 'repair'})
            self.assertEqual(hit['missing_terms'], [])
        self.assertEqual(hits[0]['page_role'], 'main')
        self.assertIn('Editorial', hits[0]['page_role_note'])
        self.assertIn('Historical vehicle-specific', hits[0]['source_caveat'])
        self.assertIn('scope', result['message'].lower())
        self.assertIn('warnings', result['message'].lower())
        self.assertNotIn('answer', result)

    def test_subject_action_queries_prefer_inspected_procedure_pages(self):
        cases = [
            ('How can I repair an engine?', {44, 29, 31}, 'Inspection and Repair'),
            ('engine removal', {10}, 'REMOVAL'),
            ('engine disassembly', {16}, 'DISASSEMBLY'),
            ('water pump repair', {29}, 'Inspection and Repair'),
            ('piston rings', {31, 34}, 'Piston'),
        ]
        for query, judged_pages, evidence in cases:
            with self.subTest(query=query):
                result = command_search(self.view, query, model_url='http://example.invalid')
                first = result['results'][0]
                self.assertEqual(first['id'], MANUAL)
                self.assertIn(first['page'], judged_pages)
                self.assertIn(evidence.lower(), self.pages[MANUAL][first['page'] - 1].lower())
                self.assertEqual(first['page_role'], 'main')
                for hit in result['results'] + result['related_results']:
                    self.assertIn(hit['excerpt'], self.pages[hit['id']][hit['page'] - 1])
                    self.assertLessEqual(len(hit['excerpt']), 600)

    def test_source_admission_does_not_invent_missing_qualifier(self):
        result = command_search(self.view, 'mechanical vehicle repair',
                                model_url='http://example.invalid')
        self.assertEqual(result['results'], [])
        self.assertEqual(result['coverage']['status'], 'no-local-coverage')
        self.assertTrue(result['related_results'])
        self.assertIn('Library gap', result['message'])

    def test_role_annotations_do_not_blacklist_insurance_or_fema(self):
        result = command_search(self.view, 'insurance repair', model_url='http://example.invalid')
        self.assertEqual((result['results'][0]['id'], result['results'][0]['page']),
                         ('fema-are-you-ready', 12))
        self.assertNotIn('page_role', result['results'][0])


class PageRoleContractTests(unittest.TestCase):
    """Synthetic domain-neutral ranking fixtures, not installed guidance."""

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.view = Path(self.temporary.name)
        (self.view / 'fixture.pdf').write_bytes(b'Test-only file-existence fixture')

    def search(self, pages, roles=None, *, query='alpha beta', note: object = 'Editorial test-only roles',
               page_count=None):
        (self.view / 'fixture.txt').write_text('\f'.join(pages))
        doc = {'id': 'fixture', 'title': 'Test-only domain-neutral fixture',
               'file': 'fixture.pdf', 'text_file': 'fixture.txt',
               'pages': len(pages) if page_count is None else page_count}
        if roles is not None:
            doc.update(page_roles=roles, page_roles_note=note)
        (self.view / 'manifest.json').write_text(json.dumps({'documents': [doc], 'map': {}}))
        return command_search(self.view, query, model_url='http://example.invalid')

    def test_role_is_tiebreak_within_coverage_not_a_new_coverage_rule(self):
        pages = ['alpha beta gamma delta epsilon', 'alpha beta gamma delta']
        roles = [{'start': 1, 'end': 1, 'role': 'reference'},
                 {'start': 2, 'end': 2, 'role': 'main'}]
        result = self.search(pages, roles, query='alpha beta gamma delta epsilon')
        self.assertEqual([h['page'] for h in result['results']], [1, 2])
        self.assertEqual(result['results'][0]['missing_terms'], [])
        self.assertEqual(result['results'][1]['missing_terms'], ['epsilon'])

    def test_main_and_unannotated_pages_have_identical_priority(self):
        pages = ['alpha beta', 'alpha extra-layout beta']
        baseline = self.search(pages)
        annotated = self.search(pages, [{'start': 2, 'end': 2, 'role': 'main'}])
        self.assertEqual([h['page'] for h in baseline['results']], [1, 2])
        self.assertEqual([h['page'] for h in annotated['results']], [1, 2])
        self.assertNotIn('page_role', annotated['results'][0])

    def test_safety_pages_are_not_demoted_below_main_pages(self):
        # No content inspection, title/publisher/query blacklist, or guessed
        # "warning" regex: reviewed warning/caveat pages have neutral priority.
        pages = ['alpha beta emergency caveat test fixture', 'alpha test fixture beta']
        roles = [{'start': 1, 'end': 1, 'role': 'safety'},
                 {'start': 2, 'end': 2, 'role': 'main'}]
        result = self.search(pages, roles)
        self.assertEqual([h['page'] for h in result['results']], [1, 2])
        self.assertEqual(result['results'][0]['excerpt'], pages[0])
        self.assertEqual(result['results'][0]['page_role'], 'safety')

    def test_each_non_substantive_role_can_only_reorder_not_filter(self):
        pages = ['alpha beta', 'alpha extra-layout beta']
        for role in ('frontmatter', 'reference', 'endmatter'):
            with self.subTest(role=role):
                result = self.search(pages, [{'start': 1, 'end': 1, 'role': role}])
                self.assertEqual([h['page'] for h in result['results']], [2, 1])
                self.assertEqual(result['results'][1]['excerpt'], pages[0])
                self.assertNotIn('Editorial', result['results'][1]['excerpt'])

    def test_invalid_metadata_is_ignored_as_a_whole_without_losing_sources(self):
        pages = ['alpha beta', 'alpha extra-layout beta']
        baseline = self.search(pages)
        valid = {'start': 1, 'end': 1, 'role': 'reference'}
        bad_cases = [
            'reference', {}, [None], [dict(valid, start=True)], [dict(valid, end=1.0)],
            [dict(valid, start=0)], [dict(valid, end=3)], [dict(valid, start=2, end=1)],
            [dict(valid, role='guessed-procedure')], [dict(valid, role=[])],
            [valid, {'start': 1, 'end': 2, 'role': 'main'}],
            [{'start': 2, 'end': 2, 'role': 'main'}, valid],
            [valid, valid, valid],
        ]
        for roles in bad_cases:
            with self.subTest(roles=roles):
                self.assertEqual(self.search(pages, roles), baseline)
        for note in (None, [], '', ' ', 'x' * 4097):
            with self.subTest(note_type=type(note)):
                self.assertEqual(self.search(pages, [valid], note=note), baseline)
        for count in (True, '2', 3):
            with self.subTest(page_count=count):
                self.assertEqual(self.search(pages, [valid], page_count=count), baseline)
