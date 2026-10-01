"""python -m wetstack serve  ->  http://127.0.0.1:8765

Serves the lab workspace from the repo and saves straight into it:
  progress/progress.json  (canonical progress, atomic, merged on conflict, backed up)
  PROGRESS.md             (regenerated on every save)
  photos/<step>/*.jpg     (resized to 1600 px on the long side)

Safety: binds to 127.0.0.1 only; every write needs the X-WetStack header and a matching
Host/Origin, so other web pages cannot write to your repo.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import subprocess
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import progress_store as ps

PAGE = Path("web/wetstack_lab.html")
PHOTO_DIR = Path("photos")
MAX_PHOTO = 25 * 1024 * 1024
MAX_JSON = ps.MAX_BYTES + 1024 * 1024
SERVER_LOCK = threading.Lock()


def _resize_jpeg(data: bytes, long_side: int = 1600) -> bytes:
    import cv2
    import numpy as np
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise ps.ProgressError("Could not read that image. Use JPEG, PNG or WebP (iPhone HEIC: export as JPEG first).")
    h, w = img.shape[:2]
    scale = long_side / max(h, w)
    if scale < 1:
        img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 88])
    if not ok:
        raise ps.ProgressError("Could not encode the photo")
    return buf.tobytes()


def _safe_name(name: str) -> str:
    stem = re.sub(r"[^A-Za-z0-9_-]+", "-", Path(name or "photo").stem).strip("-")[:40] or "photo"
    return stem


def git(args: list[str], timeout: int = 90) -> tuple[int, str]:
    try:
        r = subprocess.run(["git", *args], capture_output=True, text=True, timeout=timeout)
        return r.returncode, (r.stdout + r.stderr).strip()
    except FileNotFoundError:
        return 127, "git is not installed or not on PATH"
    except subprocess.TimeoutExpired:
        return 124, "git timed out (a push may be waiting for sign-in; run it in a terminal once)"


class Handler(BaseHTTPRequestHandler):
    server_version = "wetstack"
    port = 8765

    def log_message(self, fmt, *args):
        if self.command != "GET":
            print(f"  {self.command} {self.path} -> {args[1] if len(args) > 1 else ''}")

    # ---------------------------------------------------------------- helpers
    def _send(self, code: int, body, ctype: str = "application/json") -> None:
        data = body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def _host_ok(self) -> bool:
        allowed = {f"127.0.0.1:{self.port}", f"localhost:{self.port}"}
        if self.headers.get("Host") not in allowed:
            return False
        origin = self.headers.get("Origin")
        return origin is None or origin in {f"http://{h}" for h in allowed}

    def _write_ok(self) -> bool:
        if not self._host_ok() or self.headers.get("X-WetStack") != "1":
            self._send(403, {"error": "Writes are only accepted from the workspace page on this computer"})
            return False
        return True

    def _body(self, limit: int) -> bytes:
        n = int(self.headers.get("Content-Length") or 0)
        if n < 0:
            raise ps.ProgressError("Bad Content-Length")       # read(-1) would block until the client hangs up
        if n > limit:
            raise ps.ProgressError(f"Upload too large ({n // 1048576} MB)")
        return self.rfile.read(n)

    def _json_body(self, limit: int) -> dict:
        body = json.loads(self._body(limit).decode("utf-8") or "{}")
        if not isinstance(body, dict):
            raise ps.ProgressError("Expected a JSON object")
        return body

    # ---------------------------------------------------------------- GET
    def do_GET(self):
        if not self._host_ok():
            return self._send(403, {"error": "Forbidden host"})
        url = urlparse(self.path)
        if url.path in ("/", "/index.html"):
            if not PAGE.exists():
                return self._send(500, b"web/wetstack_lab.html missing: run python tools/build.py", "text/plain")
            return self._send(200, PAGE.read_bytes(), "text/html; charset=utf-8")
        if url.path == "/api/ping":
            return self._send(200, {"ok": True, "server": "wetstack", "version": 2, "repo": str(Path.cwd()),
                                    "rev": ps.load()["rev"]})
        if url.path == "/api/progress":
            doc = ps.load()
            since = parse_qs(url.query).get("rev", [None])[0]
            if since is not None and since.isdigit() and int(since) == doc["rev"]:
                return self._send(200, {"unchanged": True, "rev": doc["rev"]})
            return self._send(200, {"rev": doc["rev"], "doc": doc})
        if url.path.startswith("/photos/"):
            target = (Path.cwd() / url.path.lstrip("/")).resolve()
            root = (Path.cwd() / PHOTO_DIR).resolve()
            if root not in target.parents or not target.is_file():
                return self._send(404, {"error": "Not found"})
            return self._send(200, target.read_bytes(), "image/jpeg")
        return self._send(404, {"error": "Not found"})

    # ---------------------------------------------------------------- PUT/POST
    def do_PUT(self):
        if not self._write_ok():
            return
        if urlparse(self.path).path != "/api/progress":
            return self._send(404, {"error": "Not found"})
        try:
            payload = self._json_body(MAX_JSON)
            base = payload.get("base_rev")
            with SERVER_LOCK:
                doc, merged = ps.save(payload["doc"], base if isinstance(base, int) else None)
            return self._send(200, {"rev": doc["rev"], "merged": merged, "doc": doc if merged else None})
        except (ps.ProgressError, KeyError, ValueError) as e:
            return self._send(400, {"error": str(e)})

    def do_POST(self):
        if not self._write_ok():
            return
        url = urlparse(self.path)
        try:
            if url.path == "/api/photo":
                q = parse_qs(url.query)
                step = ps.safe_step(q.get("step", [None])[0])
                data = _resize_jpeg(self._body(MAX_PHOTO))
                stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
                rel = PHOTO_DIR / step / f"{stamp}-{_safe_name(q.get('name', ['photo'])[0])}.jpg"
                rel.parent.mkdir(parents=True, exist_ok=True)
                rel.write_bytes(data)
                return self._send(200, {"file": rel.as_posix(), "bytes": len(data)})
            if url.path == "/api/commit":
                body = self._json_body(64 * 1024)
                msg = (body.get("message") or "").strip() or f"Lab session {dt.date.today().isoformat()}"
                log = []
                code, out = git(["add", "progress/progress.json", "PROGRESS.md", "photos", "data/raw", "proofs", "config"])
                log.append(out)
                code, out = git(["commit", "-m", msg[:200]])
                log.append(out)
                if code != 0 and "nothing to commit" not in out:
                    return self._send(200, {"ok": False, "log": "\n".join(x for x in log if x)})
                if body.get("push"):
                    code, out = git(["push", "--follow-tags"], timeout=120)
                    log.append(out)
                    if code != 0:
                        return self._send(200, {"ok": False, "log": "\n".join(x for x in log if x)})
                return self._send(200, {"ok": True, "log": "\n".join(x for x in log if x)})
            return self._send(404, {"error": "Not found"})
        except (ps.ProgressError, ValueError) as e:
            return self._send(400, {"error": str(e)})


def serve(port: int = 8765, open_browser: bool = False) -> None:
    if not PAGE.exists():
        raise SystemExit("web/wetstack_lab.html is missing. Run: python tools/build.py")
    Handler.port = port
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}/"
    doc = ps.load()
    print(f"WetStack workspace at {url}")
    print(f"Saving to {ps.PROGRESS_FILE.resolve()} (revision {doc['rev']}). Ctrl+C to stop.")
    if open_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped. Your progress is saved.")
    finally:
        httpd.server_close()
