"""Real-source regressions; these assertions are retrieval labels, not safety advice."""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from app.retrieval import command_search

ROOT = Path(__file__).resolve().parents[1]


class RealCorpusRelevanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location('evaluate_search', ROOT / 'scripts/evaluate-search.py')
        assert spec is not None and spec.loader is not None
        cls.benchmark = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.benchmark)

    def test_benchmark_is_repeatable_and_checks_every_source_preview(self):
        fixture = json.loads((ROOT / 'tests/fixtures/search-relevance.json').read_text())
        self.assertGreaterEqual(len(fixture['cases']), 10)
        self.assertEqual(len(fixture['documents']), 7)
        reports = []
        with tempfile.TemporaryDirectory() as temporary:
            for i in range(2):
                output = Path(temporary) / f'report-{i}.json'
                process = subprocess.run([
                    sys.executable, str(ROOT / 'scripts/evaluate-search.py'),
                    '--output', str(output)], capture_output=True, text=True, timeout=30)
                self.assertEqual(process.returncode, 0, process.stderr)
                reports.append(json.loads(output.read_text()))
        self.assertEqual(reports[0], reports[1])
        report = reports[0]
        self.assertEqual(report['corpus'], 'original')
        self.assertEqual(report['document_ids'], [d['id'] for d in fixture['documents']])
        self.assertEqual([c['id'] for c in report['cases']], [c['id'] for c in fixture['cases']])
        self.assertTrue(all(c['model_status'] == 'invalid-url' for c in report['cases']))
        self.assertGreater(report['previews_checked'], 0)
        # Fixed original-seven acceptance floor, not an AI-quality claim.
        self.assertGreaterEqual(report['metrics']['hit_at_1'], 0.75)
        self.assertGreaterEqual(report['metrics']['mrr_at_10'], 0.85)
        self.assertEqual(report['metrics']['hit_at_3'], 1.0)
        ranks = [c['first_relevant_rank'] for c in report['cases']]
        self.assertAlmostEqual(report['metrics']['mrr_at_10'],
                               sum(1 / rank if rank else 0 for rank in ranks) / len(ranks))
        self.assertAlmostEqual(report['metrics']['hit_at_1'],
                               sum(rank == 1 for rank in ranks) / len(ranks))

    def test_benchmark_separates_expansion_and_rejects_original_byte_drift(self):
        benchmark = self.benchmark
        fixture = json.loads(benchmark.FIXTURE.read_text())
        manifest = json.loads((ROOT / 'content/manifest.json').read_text())
        by_id = {doc['id']: doc for doc in manifest['documents']}
        documents = [by_id[doc['id']] for doc in fixture['documents']]
        with tempfile.TemporaryDirectory() as temporary:
            content = Path(temporary)
            for doc in documents:
                for key in ('file', 'text_file'):
                    target = content / doc[key]
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(ROOT / 'content' / doc[key], target)
            # An additional catalog entry pointing at actual source bytes is a
            # test-only stand-in for later corpus admission, never a new source.
            documents.append(dict(documents[1], id='test-expanded-entry'))
            (content / 'manifest.json').write_text(json.dumps({'documents': documents, 'map': {}}))
            original = benchmark.evaluate(content)
            expanded = benchmark.evaluate(content, corpus='expanded')
            self.assertEqual(len(original['document_ids']), 7)
            self.assertEqual(original['extra_document_ids'], [])
            self.assertEqual(len(expanded['document_ids']), 8)
            self.assertEqual(expanded['extra_document_ids'], ['test-expanded-entry'])
            copyfile = shutil.copyfile

            def change_during_snapshot(source, target):
                result = copyfile(source, target)
                if Path(target).name == Path(documents[0]['text_file']).name:
                    with Path(target).open('ab') as stream:
                        stream.write(b'changed during snapshot')
                return result

            with patch.object(benchmark.shutil, 'copyfile', side_effect=change_during_snapshot):
                with self.assertRaisesRegex(ValueError, 'changed text_file bytes'):
                    benchmark.evaluate(content)
            altered = content / documents[0]['text_file']
            altered.write_bytes(altered.read_bytes() + b'changed derivative')
            with self.assertRaisesRegex(ValueError, 'changed text_file bytes'):
                benchmark.evaluate(content)

    def test_safe_drinking_water_prefers_water_guidance_to_evacuation(self):
        fixture = json.loads(self.benchmark.FIXTURE.read_text())
        with self.benchmark.corpus_view(ROOT / 'content', fixture, 'original') as (view, documents):
            result = command_search(view, 'safe drinking water', model_url='http://example.invalid')
            first = result['results'][0]
            self.assertIn((first['id'], first['page']), {
                ('cdc-make-water-safe', 1), ('cdc-use-safe-water', 1),
                ('cdc-prevent-diarrhea-after-disaster', 1)})
            by_id = {doc['id']: doc for doc in documents}
            for hit in result['results']:
                page = (view / by_id[hit['id']]['text_file']).read_text().split('\f')[hit['page'] - 1]
                self.assertIn(hit['excerpt'], page)
                self.assertLessEqual(len(hit['excerpt']), 600)
            self.assertNotIn('answer', result)
