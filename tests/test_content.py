"""Release data gates: originals must exist and match their recorded hashes."""
import hashlib
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1] / 'content'

class ContentTests(unittest.TestCase):
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
