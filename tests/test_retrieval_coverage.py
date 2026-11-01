"""Pinned installed-eleven regression, not repair guidance or model evaluation.

The extra four documents extend the original-seven frozen source set. New
catalog admissions are intentionally excluded, not judged irrelevant. All labels
refer to exact physical-page derivatives; they are not safety certification.
"""
import importlib.util
import json
from pathlib import Path
import re
import unittest

from app.retrieval import command_search

ROOT = Path(__file__).resolve().parents[1]
EXTRA_PINS = [
    {'id': 'fema-cert-2019', 'file': 'originals/fema-cert-2019.pdf',
     'text_file': 'search/fema-cert-2019.txt', 'pages': 268,
     'sha256': 'ca297bbc329c322ccbcb252fae7a1c89fd95f93dbf72b78b165b53cafa664026',
     'text_sha256': '16e163cf73b5104222b5f28cd8cde4facc827c6490a8f269592cb88257b14e88'},
    {'id': 'epa-emergency-disinfection', 'file': 'originals/epa-emergency-disinfection.pdf',
     'text_file': 'search/epa-emergency-disinfection.txt', 'pages': 2,
     'sha256': 'f404083d00decedc267bf4265eda776bb250ccfe18c1f7b19152aa006ff727c5',
     'text_sha256': '47edfa928c35d8f01c314bd88a28458903419edb2603b7f6e3c2e604c753caaf'},
    {'id': 'epa-wells-after-flood', 'file': 'originals/epa-wells-after-flood.pdf',
     'text_file': 'search/epa-wells-after-flood.txt', 'pages': 3,
     'sha256': 'ebf9465e7a23d1a546217bcfc33eaf034895b4836bb36965338ac1c05dff3fcc',
     'text_sha256': '38d4b2b6573947a03e3fca1cb83b7cdffc6c40339e0d7e08242dbf0b80c56da8'},
    {'id': 'cdc-backcountry-treatment', 'file': 'originals/cdc-backcountry-treatment.pdf',
     'text_file': 'search/cdc-backcountry-treatment.txt', 'pages': 1,
     'sha256': '9dab801f23f42be770e5c8599c499b53866cc855f6eb8330377ffe5328b8ebaa',
     'text_sha256': 'fe3cf6bc45a39c9afa2b6f281b983d65597b34b1156a0b5a4985b2dd8987d376'},
]


class InstalledElevenCoverageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location('coverage_benchmark', ROOT / 'scripts/evaluate-search.py')
        assert spec is not None and spec.loader is not None
        benchmark = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(benchmark)
        fixture = json.loads(benchmark.FIXTURE.read_text())
        cls.cases = fixture['cases']
        fixture['documents'] += EXTRA_PINS
        cls.snapshot = benchmark.corpus_view(ROOT / 'content', fixture, 'original')
        cls.view, documents = cls.snapshot.__enter__()
        cls.addClassCleanup(cls.snapshot.__exit__, None, None, None)
        cls.pages = {doc['id']: (cls.view / doc['text_file']).read_text().split('\f')
                     for doc in documents}
        assert len(cls.pages) == 11

    def search(self, query):
        result = command_search(self.view, query, model_url='http://example.invalid')
        self.assertEqual(result['mode'], 'keyword-only')
        self.assertEqual(result['model_status'], 'invalid-url')
        self.assertNotIn('answer', result)
        for bucket in ('results', 'related_results'):
            self.assertLessEqual(len(result[bucket]), 10)
            keys = [(hit['file'], hit['page']) for hit in result[bucket]]
            self.assertEqual(len(keys), len(set(keys)))
            for hit in result[bucket]:
                page = self.pages[hit['id']][hit['page'] - 1]
                self.assertTrue(hit['excerpt'])
                self.assertIn(hit['excerpt'], page)
                self.assertLessEqual(len(hit['excerpt']), 600)
                required = result['coverage']['required_terms']
                local = [term for term in required
                         if re.search(r'(?<!\w)' + re.escape(term) + r'(?!\w)', hit['excerpt'], re.I)]
                self.assertEqual(hit['local_matched_terms'], local)
                self.assertEqual(hit['missing_terms'], [term for term in required if term not in local])
                if bucket == 'results':
                    self.assertGreaterEqual(len(local), result['coverage']['minimum_local_terms'])
                else:
                    self.assertTrue(local)
                    self.assertLess(len(local), result['coverage']['minimum_local_terms'])
        return result

    def test_reported_repair_searches_expose_no_local_coverage(self):
        for query in ('engine repair', 'mechanical vehicle repair', 'vehicle repair'):
            with self.subTest(query=query):
                result = self.search(query)
                self.assertEqual(result['results'], [])
                self.assertEqual(result['coverage']['status'], 'no-local-coverage')
                self.assertIn('Library gap', result['message'])
                self.assertTrue(result['related_results'])
                self.assertIn(('fema-are-you-ready', 12),
                              {(hit['id'], hit['page']) for hit in result['related_results']})

    def test_question_framing_does_not_bypass_missing_repair_coverage(self):
        result = self.search('How can I repair an engine?')
        self.assertEqual(result['results'], [])
        self.assertEqual(result['coverage']['required_terms'], ['repair', 'engine'])

    def test_actual_water_food_sanitation_medical_sources_remain_findable(self):
        # Source-page labels checked against the pinned derivatives, not inferred
        # from a model response or the mere presence of matching words.
        cases = [
            ('safe drinking water', {('cdc-make-water-safe', 1), ('cdc-use-safe-water', 1),
                                     ('cdc-prevent-diarrhea-after-disaster', 1)}),
            ('Find safe drinking water guidance', {('cdc-make-water-safe', 1), ('cdc-use-safe-water', 1),
                                                   ('cdc-prevent-diarrhea-after-disaster', 1)}),
            ('safe minimum internal temperature chart', {('usda-kitchen-companion-2015', 21)}),
            ('wash hands soap', {('cdc-wash-hands', 1), ('cdc-prevent-diarrhea-after-disaster', 1)}),
            ('maintaining sanitation', {('fema-cert-2019', 134)}),
            ('treating burns', {('fema-cert-2019', 107)}),
            ('infant formula tap water', {('cdc-use-safe-water', 1)}),
        ]
        for query, relevant in cases:
            with self.subTest(query=query):
                result = self.search(query)
                self.assertEqual(result['coverage']['status'], 'local-query-match')
                self.assertTrue(relevant & {(h['id'], h['page']) for h in result['results'][:3]})

    def test_insurance_is_not_blacklisted_as_a_word_or_a_publisher(self):
        result = self.search('insurance repair')
        self.assertEqual(result['results'][0]['id'], 'fema-are-you-ready')
        self.assertEqual(result['results'][0]['page'], 12)

    def test_all_original_benchmark_cases_keep_labeled_evidence_in_top_three(self):
        for case in self.cases:
            with self.subTest(case=case['id']):
                result = self.search(case['query'])
                relevant = {(label['id'], label['page']) for label in case['relevant']}
                self.assertTrue(relevant & {(h['id'], h['page']) for h in result['results'][:3]})
                for label in case['relevant']:
                    self.assertIn(label['evidence'], self.pages[label['id']][label['page'] - 1])

    def test_absent_qualifier_is_explained_not_silently_discarded(self):
        # The established benchmark's infant-formula prompt contains 'unsafe',
        # absent from its labeled CDC page. Five original terms still anchor the
        # source, but the missing qualifier must not be silently claimed covered.
        query = 'How do I prepare infant formula when tap water is unsafe?'
        result = self.search(query)
        self.assertEqual(result['coverage']['status'], 'partial-query-match')
        relevant = next(hit for hit in result['results']
                        if (hit['id'], hit['page']) == ('cdc-use-safe-water', 1))
        self.assertEqual(relevant['missing_terms'], ['unsafe'])
        self.assertEqual(len(relevant['local_matched_terms']), 5)
        self.assertIn('Missing query words', result['message'])
        self.assertIn('When powdered infant formula is the only option', self.pages[relevant['id']][0])
