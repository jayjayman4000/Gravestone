#!/usr/bin/env python3
"""Explicit pinned pyshp vendoring; retain the upstream MIT license verbatim."""
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen

root = Path(__file__).resolve().parents[1]
records = []
for source, target in [('shapefile.py', 'app/_vendor/shapefile.py'), ('LICENSE.TXT', 'app/_vendor/LICENSE-pyshp.TXT')]:
    url = 'https://raw.githubusercontent.com/GeospatialPython/pyshp/2.3.1/' + source
    with urlopen(url, timeout=30) as response:
        raw = response.read(300000)
    assert len(raw) < 300000
    path = root / target
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    records.append({'url': url, 'path': target, 'sha256': hashlib.sha256(raw).hexdigest()})
(root / 'content/maps/pyshp-provenance.json').write_text(json.dumps({'version': '2.3.1', 'license': 'MIT', 'files': records}, indent=2) + '\n')
print(json.dumps(records))
