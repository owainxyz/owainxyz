import hashlib
import os
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import gen

poll = 60
fallback = 1800
cache = {"at": 0, "svgs": {}, "tags": {}}
dirty = threading.Event()
etags = {}


def rebuild():
    try:
        svgs = gen.build()
    except Exception as e:
        print("build failed:", e, flush=True)
        return False
    svgs.update({"light/" + k: gen.light(v) for k, v in list(svgs.items())})
    cache["svgs"] = svgs
    cache["tags"] = {k: '"' + hashlib.sha1(v.encode()).hexdigest()[:16] + '"' for k, v in svgs.items()}
    cache["at"] = time.time()
    print("built", time.strftime("%H:%M:%S"), flush=True)
    return True


def changed(path):
    req = urllib.request.Request(
        "https://api.github.com/" + path,
        headers={"Authorization": f"Bearer {gen.token}", "User-Agent": "ghstats", "Accept": "application/vnd.github+json"},
    )
    if path in etags:
        req.add_header("If-None-Match", etags[path])
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            first = path not in etags
            etags[path] = r.headers.get("ETag", "")
            return not first
    except urllib.error.HTTPError as e:
        if e.code != 304:
            print("poll", path, e.code, flush=True)
        return False
    except Exception as e:
        print("poll", path, e, flush=True)
        return False


def watcher():
    feeds = [f"users/{gen.user}/events?per_page=1", f"users/{gen.user}/received_events?per_page=1"]
    while True:
        hit = [changed(f) for f in feeds]
        if any(hit) or dirty.is_set() or time.time() - cache["at"] > fallback:
            dirty.clear()
            if not rebuild():
                dirty.set()
        time.sleep(poll)


order = ["overview", "contributions", "languages", "recent", "contributed", "uncord", "shortleash", "splashdeck"]
page = {
    "/": (
        ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
         '<meta name="viewport" content="width=device-width,initial-scale=1">'
         '<title>stats</title><link rel="stylesheet" href="/s.css"></head><body>'
         + "".join(f'<picture><source media="(prefers-color-scheme: light)" srcset="/light/{n}.svg"><img src="/{n}.svg" alt="{n}"></picture>' for n in order)
         + "</body></html>").encode(),
        "text/html; charset=utf-8",
    ),
    "/s.css": (
        b"body{margin:0 auto;padding:16px;max-width:840px;background:#181a1b}"
        b"img{display:block;width:100%;margin:0 0 16px}"
        b"@media (prefers-color-scheme: light){body{background:#fff}}",
        "text/css; charset=utf-8",
    ),
}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = self.path.split("?")[0]
        if path in page:
            body, kind = page[path]
            self.send_response(200)
            self.send_header("Content-Type", kind)
            self.send_header("Cache-Control", "no-cache, max-age=0")
            self.send_header("Content-Security-Policy", "default-src 'none'; img-src 'self'; style-src 'self'")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        name = path.strip("/").removesuffix(".svg")
        svg = cache["svgs"].get(name) if name.removeprefix("light/").isidentifier() else None
        if svg is None:
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        tag = cache["tags"][name]
        if self.headers.get("If-None-Match") == tag:
            self.send_response(304)
            self.send_header("ETag", tag)
            self.end_headers()
            return
        data = svg.encode()
        self.send_response(200)
        self.send_header("Content-Type", "image/svg+xml; charset=utf-8")
        self.send_header("Cache-Control", "no-cache, max-age=0")
        self.send_header("ETag", tag)
        self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7460))
    threading.Thread(target=watcher, daemon=True).start()
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
