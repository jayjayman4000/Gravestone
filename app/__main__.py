"""Run with python3 -m app --data-dir /path/outside/repository."""
import argparse
from pathlib import Path

from . import make_server


def main():
    parser = argparse.ArgumentParser(description='Gravestone offline dashboard (loopback only)')
    parser.add_argument('--data-dir', required=True, type=Path,
                        help='Private notebook directory outside the repository; persistence is not assumed')
    parser.add_argument('--host', choices=('127.0.0.1', 'localhost'), default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8766)
    args = parser.parse_args()
    if not 0 <= args.port <= 65535:
        parser.error('port must be between 0 and 65535')
    try:
        server = make_server(content_dir=Path(__file__).resolve().parent.parent / 'content',
                             data_dir=args.data_dir, host=args.host, port=args.port)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    print(f'Gravestone prototype: http://127.0.0.1:{server.server_port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
