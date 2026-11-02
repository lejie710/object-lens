"""Serve Object Lens locally; test fixtures are enabled only with --test-mode."""
from __future__ import annotations

import argparse
import json
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent


class AppHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, test_mode=False, **kwargs):
        self.test_mode = test_mode
        super().__init__(*args, directory=str(ROOT / "dist"), **kwargs)

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == "/runtime-config.json":
            content = json.dumps({"testMode": self.test_mode}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(content)
            return
        if path == "/test-worker.js":
            if not self.test_mode:
                self.send_error(404)
                return
            content = (ROOT / "tests" / "fixtures" / "test-worker.js").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/javascript")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
            return
        super().do_GET()

    def end_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        super().end_headers()


def make_server(port=8765, test_mode=False):
    return ThreadingHTTPServer(("127.0.0.1", port), partial(AppHandler, test_mode=test_mode))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--test-mode", action="store_true", help="Use controlled predictions for UI tests only")
    args = parser.parse_args()
    server = make_server(args.port, args.test_mode)
    print(f"Object Lens: http://127.0.0.1:{server.server_port}", flush=True)
    if args.test_mode:
        print("TEST MODE: predictions may be simulated. Not AI accuracy evidence.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
