"""Bounded parser worker; stdin is a personal PDF, stdout bounded extraction JSON."""
import io
import json
import resource
import sys


def main():
    resource.setrlimit(resource.RLIMIT_AS, (384 * 1024 * 1024,) * 2)
    resource.setrlimit(resource.RLIMIT_CPU, (8, 8))
    resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
    resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
    try:
        import pypdf as parser
    except ImportError:
        try:
            import PyPDF2 as parser
        except ImportError:
            return 3
    try:
        raw = sys.stdin.buffer.read(32 * 1024 * 1024 + 1)
        if len(raw) > 32 * 1024 * 1024:
            return 1
        pdf = parser.PdfReader(io.BytesIO(raw), strict=True)
        if pdf.is_encrypted or not 0 < len(pdf.pages) <= 1000:
            return 1
        pages = []; size = 0
        for page in pdf.pages:
            text = (page.extract_text() or '').replace('\f', '\n')
            size += len(text.encode('utf-8')) + 1
            if size > 2 * 1024 * 1024:
                return 1
            pages.append(text)
        # ensure_ascii can expand to 6 bytes per character: keep output bounded.
        sys.stdout.write(json.dumps({'pages': len(pages), 'text': '\f'.join(pages),
                                    'parser': parser.__name__ + ' ' + parser.__version__}, ensure_ascii=True))
        return 0
    except Exception:
        return 1


if __name__ == '__main__':
    sys.exit(main())
