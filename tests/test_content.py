"""Release data gates: originals must exist and match their recorded hashes."""
import hashlib
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1] / 'content'

class ContentTests(unittest.TestCase):
    def test_historical_repair_manual_has_exact_original_and_work_specific_rights(self):
        manifest = json.loads((ROOT / 'manifest.json').read_text())
        by_id = {doc['id']: doc for doc in manifest['documents']}
        source_id = 'war-department-tm9-1803a-1944'
        self.assertIn(source_id, by_id)
        doc = by_id[source_id]
        self.assertEqual(doc['sha256'], '91a303b1defb65bdc7df003d307aa902b8cb5ff2afeaa2a15f19830fdc5ae669')
        self.assertEqual(doc['pages'], 84)
        self.assertEqual(doc['bytes'], 8888550)
        self.assertIn('historical', doc['source_caveat'].lower())
        self.assertIn('not modern', doc['source_caveat'].lower())
        self.assertIn('UNVERIFIED', doc['extraction_status'])
        text = (ROOT / doc['text_file']).read_text()
        self.assertEqual(len(text.split('\f')), 84)
        self.assertEqual(text.split('\f')[82], '')
        self.assertEqual(hashlib.sha256((ROOT / doc['text_file']).read_bytes()).hexdigest(), doc['text_sha256'])
        mods = next(e for e in doc['rights_evidence'] if e['kind'] == 'work-specific-government-rights')
        raw = (ROOT / mods['file']).read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), mods['sha256'])
        self.assertIn('not subject to copyright pursuant to 17 USC 105', raw.decode())
        from app.retrieval import command_search
        result = command_search(ROOT, 'engine repair', model_url='http://example.invalid')
        self.assertTrue(result['results'])
        self.assertTrue(all(h['id'] == source_id for h in result['results']))
        for hit in result['results']:
            self.assertIn(hit['excerpt'], text.split('\f')[hit['page'] - 1])
            self.assertEqual(hit['missing_terms'], [])

    def test_originals_and_map_match_manifest(self):
        self.assertTrue((ROOT / 'manifest.json').is_file(), 'Source manifest has not been created')
        manifest = json.loads((ROOT / 'manifest.json').read_text())
        self.assertGreaterEqual(len(manifest['documents']), 1)
        for entry in [*manifest['documents'], manifest['map']]:
            with self.subTest(source=entry['id']):
                path = (ROOT / entry['file']).resolve()
                self.assertTrue(path.is_relative_to(ROOT.resolve()))
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), entry['sha256'])
                for key in ('publisher', 'url', 'rights', 'retrieved_at'):
                    self.assertTrue(entry[key])
                if path.suffix == '.pdf':
                    self.assertTrue(path.read_bytes().startswith(b'%PDF-'))
        world = json.loads((ROOT / manifest['map']['file']).read_text())
        self.assertEqual(world['type'], 'FeatureCollection')
        self.assertGreater(len(world['features']), 150)

if __name__ == '__main__':
    unittest.main()
