#!/usr/bin/env python3
"""Explicit maintainer-only refresh of the pinned Census catalog/rights evidence."""
import csv
import hashlib
import io
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1] / 'content/maps'
URL = 'https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2025_Gazetteer/2025_Gaz_counties_national.zip'
RIGHTS = 'https://www2.census.gov/geo/tiger/TIGER2025/ROADS/tl_2025_11001_roads.zip'


def fetch(url):
    with urlopen(url, timeout=30) as response:
        raw = response.read(4 * 1024 * 1024 + 1)
        if len(raw) > 4 * 1024 * 1024:
            raise ValueError('Metadata exceeds 4 MiB')
        return raw, response.url


def main():
    raw, final = fetch(URL)
    with ZipFile(io.BytesIO(raw)) as archive:
        names = archive.namelist()
        print(names)
        text = archive.read(next(n for n in names if n.endswith('.txt')))
    regions = []
    for row in csv.DictReader(io.StringIO(text.decode('utf-8-sig')), delimiter='|'):
        row = {k.strip(): v.strip() for k, v in row.items()}
        regions.append({'id': row['GEOID'], 'state': row['USPS'], 'name': row['NAME'],
                        'lat': float(row['INTPTLAT']), 'lon': float(row['INTPTLONG'])})
    rights_zip, rights_final = fetch(RIGHTS)
    with ZipFile(io.BytesIO(rights_zip)) as archive:
        rights = archive.read('tl_2025_11001_roads.shp.iso.xml')
    assert b'not copyrighted' in rights.lower(), 'Rights statement missing'
    ROOT.mkdir(exist_ok=True, parents=True)
    (ROOT / 'tiger-catalog-original.zip').write_bytes(raw)
    (ROOT / 'tiger-catalog-original.txt').write_bytes(text)
    (ROOT / 'tiger-rights-original.xml').write_bytes(rights)
    metadata = {'year': 2025, 'publisher': 'U.S. Census Bureau', 'source_url': URL,
                'final_url': final, 'retrieved_at': datetime.now(timezone.utc).isoformat(),
                'source_sha256': hashlib.sha256(raw).hexdigest(),
                'original_text_sha256': hashlib.sha256(text).hexdigest(),
                'rights': 'TIGER public-domain U.S. federal geography; no Census endorsement.',
                'rights_url': RIGHTS, 'rights_final_url': rights_final,
                'rights_sha256': hashlib.sha256(rights).hexdigest(),
                'transformation': 'Official tab-delimited gazetteer county ID, USPS, NAME, INTPTLAT, INTPTLONG only.',
                'layers': ['roads', 'water'], 'regions': regions}
    (ROOT / 'tiger-catalog.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'counties': len(regions), 'states': len({r['state'] for r in regions}), 'sha256': metadata['source_sha256']}))


if __name__ == '__main__':
    main()
