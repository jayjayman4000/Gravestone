"""Standard-library host preparation. No kiosk imports, PDF parsing or network fetches."""
import base64
import hashlib
import io
import json
import zipfile

from urllib.parse import urlsplit

MAX_PDF = 32 * 1024 * 1024
MAX_TOTAL = 64 * 1024 * 1024
CATEGORIES = ('vehicles', 'radios', 'utilities', 'power', 'water', 'heating', 'tools', 'maps', 'recovery')
FIELDS = ('exact_model', 'official_manual_link', 'local_filename', 'consumables_spares', 'last_checked', 'unknowns')
TRANSFER = '''# Private content pack — manual transfer

This pack is not a kiosk backup or an automatically installable pack.
Do not flash/reflash an existing USB to transfer it. Do not place it in content/ or an ISO.
Keep this unencrypted private pack and original downloads off public Git/shares.

1. Copy this ZIP to a separate ordinary removable data drive (or other private storage).
   Keep another copy. Do not format, repartition, or overwrite your existing Gravestone USB.
2. Extract to a new empty folder using your normal OS ZIP tool. Read manifest.json:
   pdfs/<sha256>.pdf contains the exact original bytes; original_filename and title identify it.
   Compare the SHA-256 if checking transfer integrity; no extraction or parsing is a safety review.
3. Boot the existing Gravestone USB with already provisioned, tested writable persistence.
   In the kiosk's personal PDF setup, choose Other PDF, select each extracted PDF from
   the separate data drive, enter its title from manifest.json, acknowledge applicable
   publisher terms/personal-use permission, and import it individually.
   Never upload this whole ZIP to the PDF importer or the map importer.
4. Check each document in Source Documents, open its original and search extracted text.
   Duplicates must be rejected without replacing originals. A failed import may need checking
   the library before retrying. Images/scans without text require reading original pages.
5. Inventory is an ordinary private JSON/Markdown file, not indexed/imported into the kiosk.
   Retain it on your private data drive; optionally copy selected non-sensitive text into notes.
6. Cleanly shut down and boot again twice; check the same personal PDFs and notes survive.
   Without verified persistence imports may disappear. This tool cannot provision persistence.

Maps: use the kiosk's existing map tools and its supported original Census layer ZIPs.
A category named maps in inventory does not add map data. This pack contains PDFs only.
Notebook/map backups exclude these personal PDFs. Keep this separate private backup.
Copyright, extraction, personal storage and transfer terms remain your responsibility.
'''


def validate_inventory(equipment):
    if not isinstance(equipment, list) or len(equipment) > 100:
        raise ValueError('Use at most 100 equipment entries')
    for item in equipment:
        if not isinstance(item, dict) or set(item) != set(FIELDS) | {'category'}:
            raise ValueError('Equipment fields do not match inventory version 1')
        if item['category'] not in CATEGORIES:
            raise ValueError('Unknown equipment category')
        for field in FIELDS:
            value = item[field]
            if (not isinstance(value, str) or len(value) > 4000
                    or any(ord(c) < 32 and c not in '\n\t' for c in value)):
                raise ValueError('Inventory values must be text up to 4000 characters')
        link = item['official_manual_link']
        if link:
            parsed = urlsplit(link)
            if (parsed.scheme != 'https' or not parsed.hostname or parsed.username is not None
                    or parsed.password is not None or any(c.isspace() for c in link)):
                raise ValueError('Use an HTTPS publisher URL without credentials or whitespace')


def build_pack(payload):
    if not isinstance(payload, dict) or payload.get('rights_acknowledged') is not True:
        raise ValueError('Acknowledge personal storage/use and applicable publisher terms')
    equipment = payload.get('equipment')
    validate_inventory(equipment)
    pdfs = payload.get('pdfs')
    if not isinstance(pdfs, list) or len(pdfs) > 16:
        raise ValueError('Use at most 16 PDFs per pack')
    admitted = []
    seen = set()
    total = 0
    for item in pdfs:
        if not isinstance(item, dict) or set(item) != {'name', 'title', 'base64'}:
            raise ValueError('Invalid PDF entry')
        for field, limit in [('name', 255), ('title', 200)]:
            value = item[field]
            if (not isinstance(value, str) or not value.strip() or len(value) > limit
                    or any(ord(c) < 32 or ord(c) == 127 for c in value)):
                raise ValueError('Filename/title must be bounded printable text')
        encoded = item['base64']
        if not isinstance(encoded, str) or len(encoded) > ((MAX_PDF + 2) // 3) * 4:
            raise ValueError('PDF exceeds 32 MiB')
        try:
            raw = base64.b64decode(encoded, validate=True)
        except (ValueError, UnicodeError) as exc:
            raise ValueError('Invalid PDF encoding') from exc
        total += len(raw)
        if len(raw) > MAX_PDF or total > MAX_TOTAL:
            raise ValueError('Maximum 32 MiB per PDF, 64 MiB total per pack')
        if not raw.startswith(b'%PDF-') or not raw.rstrip().endswith(b'%%EOF'):
            raise ValueError('Expected complete PDF bytes, not a web page; kiosk will validate parsing')
        digest = hashlib.sha256(raw).hexdigest()
        if digest in seen:
            raise ValueError('Duplicate PDF selected; no file replaced')
        seen.add(digest)
        admitted.append((item, raw, digest))
    manifest = {'format': 'gravestone-personal-preparation', 'version': 1, 'documents': []}
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w', compression=zipfile.ZIP_STORED) as archive:
        archive.writestr('inventory.json', json.dumps({'version': 1, 'equipment': equipment}, ensure_ascii=False, indent=2))
        markdown = '# My equipment — private\n\n'
        for item in equipment:
            markdown += '\n## ' + item['category'] + '\n'
            for field in FIELDS:
                # Entity-encode punctuation/newlines so user text cannot become Markdown/HTML.
                # inventory.json remains the authoritative byte-for-character text record.
                safe = ''.join(c if c.isalnum() or c == ' ' else '&#' + str(ord(c)) + ';'
                               for c in item[field])
                markdown += '- ' + field.replace('_', ' ') + ': ' + safe + '\n'
        archive.writestr('MY_EQUIPMENT.md', markdown)
        for item, raw, digest in admitted:
            path = 'pdfs/' + digest + '.pdf'
            archive.writestr(path, raw)
            manifest['documents'].append({'path': path, 'sha256': digest, 'bytes': len(raw),
                                          'original_filename': item['name'], 'title': item['title'],
                                          'source_id': 'other'})
        archive.writestr('manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2))
        archive.writestr('TRANSFER.md', TRANSFER)
    return out.getvalue()


from host_prepare.server import MAX_REQUEST, make_server
