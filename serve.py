#!/usr/bin/env python3
"""Dev server: static files + Agentation webhook sink.

POST /agentation appends the annotation markdown to annotations.md so Claude
can read it straight from disk. Same origin as the site, so no CORS.

    python3 serve.py [port]     # default 8080, binds 0.0.0.0
"""
import http.server
from functools import partial
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).parent
OUT = ROOT / "annotations.md"


class Handler(http.server.SimpleHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/agentation":
            self.send_error(404)
            return
        try:
            body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            data = json.loads(body)
        except (ValueError, TypeError):
            self.send_error(400)
            return
        # Agentation fires two payload shapes: "submit" carries the full
        # markdown in `output`, the live annotation.* events carry a single
        # `annotation`. Everything else (delete, clear) is noise here.
        if data.get("output"):
            text = data["output"]
        elif data.get("event") in ("annotation.add", "annotation.update"):
            a = data["annotation"]
            text = "- %s\n  `%s`" % (
                a.get("comment", ""),
                a.get("elementPath") or a.get("element", ""),
            )
        else:
            self.send_response(204)
            self.end_headers()
            return
        # ponytail: append-only log. If it ever gets noisy, truncate by hand.
        with OUT.open("a", encoding="utf-8") as f:
            f.write("\n\n--- %s %s\n%s\n" % (data.get("event", "?"), data.get("url", "?"), text))
        self.send_response(204)
        self.end_headers()

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    print("serving %s on 0.0.0.0:%d, annotations -> %s" % (ROOT, port, OUT.name))
    handler = partial(Handler, directory=str(ROOT))
    # ThreadingHTTPServer: a browser keep-alive connection must not block others
    http.server.ThreadingHTTPServer(("0.0.0.0", port), handler).serve_forever()
