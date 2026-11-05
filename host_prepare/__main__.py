"""Run from the source folder: python3 -m host_prepare (Windows: py -3)."""
import argparse
from . import make_server


def main():
    parser = argparse.ArgumentParser(description='Private local-only preparation; no dependencies, downloads or disk/device writes.')
    parser.add_argument('--port', type=int, default=0, help='Loopback port; default chooses a free port')
    args = parser.parse_args()
    if not 0 <= args.port <= 65535:
        parser.error('port must be 0–65535')
    with make_server(args.port) as server:
        print('Open http://127.0.0.1:' + str(server.server_port) + '/', flush=True)
        print('Keep this terminal open. Ctrl+C stops it. Save private ZIPs outside the public checkout.', flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == '__main__':
    main()
