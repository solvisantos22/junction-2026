"""Serve the homepage candidate locally. No Modal credentials or SDK are used.

    python3 tools/traverse_farm/home_preview/serve.py

Cached public featured replays stay local. A user-submitted new world redirects to
the existing public site; no cloud request is made just by opening the homepage.
"""
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
import argparse
import re

HERE = Path(__file__).resolve().parent
LIVE = "https://kristjansolvi03--lightlag-traverse-live-web.us-east.modal.run"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=5183)
    parser.add_argument("--cache", type=Path, default=Path.home() / ".codex/tmp/lightlag-home-preview")
    args = parser.parse_args()

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(HERE), **kw)

        def do_GET(self):
            url = urlsplit(self.path)
            if url.path == "/before":
                return self.local_page(args.cache / "before.html")
            match = re.fullmatch(r"/world/(\d+)", url.path)
            if url.path == "/world":
                value = parse_qs(url.query).get("seed", [""])[0]
                match = re.fullmatch(r"(\d+)", value)
            if match:
                seed = int(match.group(1))
                if not 1 <= seed <= 1_000_000:
                    self.send_error(400, "World must be 1 to 1,000,000")
                    return
                local = args.cache / f"world-{seed}.html"
                if local.exists():
                    return self.local_page(local)
                self.send_response(302)
                self.send_header("Location", f"{LIVE}/world/{seed}")
                self.end_headers()
                return
            if url.path.startswith("/world"):
                self.send_error(400, "Enter a whole world number")
                return
            allowed = {"/", "/index.html", "/style.css", "/home.js"}
            if url.path not in allowed and not re.fullmatch(r"/assets/[a-zA-Z0-9_.-]+\.(?:png|woff2|css)", url.path):
                self.send_error(404)
                return
            super().do_GET()

        def local_page(self, file):
            if not file.is_file():
                self.send_error(404, "Local capture unavailable")
                return
            data = file.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Local preview: http://127.0.0.1:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
