"""Dev server for the WebXR app that actually disables caching.

Plain `python -m http.server` lets the browser cache the JS module files,
which silently serves stale code after an edit — a normal reload doesn't
always re-fetch them. This sends Cache-Control: no-store on every response
so a plain reload always gets the current files.

Run from rehab_vr/web/: python serve.py [port, default 5500]
"""
from __future__ import annotations

import functools
import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path


class NoCacheHandler(SimpleHTTPRequestHandler):
    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("Pragma", "no-cache")
        super().end_headers()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5500
    # Bind to this script's own directory, not the caller's cwd — running it
    # via `python rehab_vr/web/serve.py` from the repo root would otherwise
    # serve the whole repo (and a directory listing instead of index.html),
    # exactly the kind of "ran it from the wrong place" mistake this script
    # exists to eliminate.
    web_dir = Path(__file__).resolve().parent
    handler = functools.partial(NoCacheHandler, directory=str(web_dir))
    with HTTPServer(("0.0.0.0", port), handler) as httpd:
        print(f"Serving {web_dir} (no-cache) on http://0.0.0.0:{port}")
        httpd.serve_forever()
