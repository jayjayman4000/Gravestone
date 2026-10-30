"""Physical-page locations for literal library searches (test-only text)."""
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.request import urlopen

from app import make_server


class LiteralSearchPageTests(unittest.TestCase):
    def test_literal_results_include_physical_page_and_page_local_excerpt(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            content = base / 'content'
            content.mkdir()
            (content / 'original.pdf').write_bytes(b'%PDF-test fixture only')
            pages = ['First page fixture.', 'Second page needle fixture.', 'Third page needle fixture.']
            (content / 'original.txt').write_text('\f'.join(pages))
            (content / 'manifest.json').write_text(json.dumps({'documents': [
                {'id': 'fixture', 'title': 'Fixture title', 'publisher': 'Fixture publisher',
                 'file': 'original.pdf', 'text_file': 'original.txt', 'pages': 3}], 'map': {}}))
            server = make_server(content_dir=content, data_dir=base / 'data', port=0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                with urlopen(f'http://127.0.0.1:{server.server_port}/api/search?q=needle', timeout=3) as response:
                    results = json.load(response)['results']
                self.assertEqual([hit.get('page') for hit in results], [2, 3])
                for hit in results:
                    self.assertIn(hit['excerpt'], pages[hit['page'] - 1])
                    self.assertEqual(hit['publisher'], 'Fixture publisher')
            finally:
                server.shutdown()
                server.server_close()
                thread.join()


if __name__ == '__main__':
    unittest.main()
