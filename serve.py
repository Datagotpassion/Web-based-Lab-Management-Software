"""Production entry point: waitress rather than the Flask development server.

app.py's __main__ block runs Flask's built-in server, which prints its own
"do not use in production" warning and is single-threaded-ish and unsupervised.
This is what systemd should start on the Pi.

    python serve.py                      # 0.0.0.0:5000
    python serve.py --port 5001          # explicit
    LABMANAGER_PORT=5001 python serve.py # or via the environment

Every option has an environment variable so the systemd unit can set them
without editing this file.
"""

import argparse
import os
import sys


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--host', default=os.environ.get('LABMANAGER_HOST', '0.0.0.0'),
                    help='interface to bind (default 0.0.0.0, all interfaces)')
    ap.add_argument('--port', type=int,
                    default=int(os.environ.get('LABMANAGER_PORT', '5000')))
    ap.add_argument('--threads', type=int,
                    default=int(os.environ.get('LABMANAGER_THREADS', '4')),
                    help='worker threads; 4 is ample for a lab-sized user count')
    args = ap.parse_args()

    try:
        from waitress import serve
    except ImportError:
        sys.exit('waitress is not installed. Run: pip install -r requirements.txt')

    # Imported after the arg parse so --help works without a database present.
    from app import app

    print(f'Lab Management System on http://{args.host}:{args.port} '
          f'({args.threads} threads)', flush=True)
    serve(app, host=args.host, port=args.port, threads=args.threads,
          # Identify ourselves rather than leaking the waitress version.
          ident='LabManagement')


if __name__ == '__main__':
    main()
