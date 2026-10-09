"""Issue #8's local preview: exact static routes, never a repository file server."""
import argparse
import os
import stat
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[2]
BASE = "investigations/frontier-economics/"
ROUTES = {
    "/web/prototypes/index.html": ("web/prototypes/index.html", "text/html; charset=utf-8"),
    "/web/prototypes/explorer.css": ("web/prototypes/explorer.css", "text/css; charset=utf-8"),
    "/web/prototypes/explorer.js": ("web/prototypes/explorer.js", "text/javascript; charset=utf-8"),
    "/" + BASE + "evidence.json": (BASE + "evidence.json", "application/json; charset=utf-8"),
    "/" + BASE + "assessment.md": (BASE + "assessment.md", "text/plain; charset=utf-8"),
    "/" + BASE + "sources.json": (BASE + "sources.json", "application/json; charset=utf-8"),
    "/" + BASE + "licensed-sources/NOTICE.md": (BASE + "licensed-sources/NOTICE.md", "text/plain; charset=utf-8"),
}
for name in ("Q2283-r2550576892", "Q3884-r2546229470", "P2139-r2547354403", "Q4917-r2554037296"):
    path = BASE + "licensed-sources/" + name + ".json.bin"
    ROUTES["/" + path] = (path, "application/octet-stream")


class Preview(BaseHTTPRequestHandler):
    def send_head(self):
        route = unquote(urlsplit(self.path).path)
        target = ROUTES.get(route)
        if target is None:
            self.send_error(404, "Not an admitted preview route")
            return None
        relative, media = target
        path = ROOT / relative
        # Neither an admitted file nor an intermediate directory may redirect
        # reads through a symlink. No arbitrary path is ever joined from a URL.
        if any(p.is_symlink() for p in (path, *path.parents)):
            self.send_error(404, "Preview file unavailable")
            return None
        try:
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
            body = os.fdopen(fd, "rb")
            info = os.fstat(body.fileno())
            if not stat.S_ISREG(info.st_mode):
                body.close()
                raise OSError("not a regular file")
        except OSError:
            self.send_error(404, "Preview file unavailable")
            return None
        self.send_response(200)
        self.send_header("Content-Type", media)
        self.send_header("Content-Length", str(info.st_size))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'")
        if media == "application/octet-stream":
            self.send_header("Content-Disposition", 'attachment; filename="' + path.name + '"')
        self.end_headers()
        return body

    def do_GET(self):
        body = self.send_head()
        if body:
            with body:
                while chunk := body.read(65536):
                    self.wfile.write(chunk)

    def do_HEAD(self):
        body = self.send_head()
        if body:
            body.close()

    def do_POST(self):
        self.send_error(405, "Read-only preview; GET and HEAD only")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8878)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Preview)
    print(f"Issue8 preview ready at http://127.0.0.1:{args.port}/web/prototypes/index.html", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
