"""Serve the graph page and compute statistics for an uploaded CSV.

    python -m qualgraph.server --port 8000

Uploads and results live only in this process's memory; nothing is written to
disk, and everything is gone when the server stops. One computation runs at a
time, and the latest result replaces the previous one.

    GET  /             the page
    POST /api/run      body: the CSV; query: n_perm, seed, name (file name to
                       show on the page). Starts a run.
    GET  /api/status   {"state": "idle" | "running" | "done" | "error", ...};
                       includes "result" once done.
"""

import argparse
import json
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

from .build import compute, render_html
from .data import parse_data

MAX_UPLOAD = 50 * 1024 * 1024
MAX_PERM = 100_000_000


class Job:
    """The one in-memory computation and its result."""

    def __init__(self):
        self.lock = threading.Lock()
        self.status = {"state": "idle"}

    def start(self, records, n_perm: int, seed: int, source: str) -> bool:
        with self.lock:
            if self.status["state"] == "running":
                return False
            self.status = {"state": "running", "mode": None, "done": 0, "total": n_perm}
        threading.Thread(target=self._run, args=(records, n_perm, seed, source), daemon=True).start()
        return True

    def _run(self, records, n_perm, seed, source):
        def progress(mode, done, total):
            with self.lock:
                self.status = {"state": "running", "mode": mode, "done": done, "total": total}

        try:
            result = compute(records, n_perm, seed, progress)
            result["meta"]["source"] = source
            status = {"state": "done", "result": result}
        except Exception as e:
            status = {"state": "error", "error": f"{type(e).__name__}: {e}"}
        with self.lock:
            self.status = status

    def snapshot(self) -> dict:
        with self.lock:
            return dict(self.status)


class Handler(BaseHTTPRequestHandler):
    job: Job  # set by serve()

    def do_GET(self):
        path = urlsplit(self.path).path
        if path in ("/", "/index.html"):
            self._send(HTTPStatus.OK, render_html(None).encode(), "text/html; charset=utf-8")
        elif path == "/api/status":
            self._json(HTTPStatus.OK, self.job.snapshot())
        else:
            self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})

    def do_POST(self):
        url = urlsplit(self.path)
        if url.path != "/api/run":
            return self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})
        length = int(self.headers.get("Content-Length") or 0)
        if not 0 < length <= MAX_UPLOAD:
            return self._json(HTTPStatus.BAD_REQUEST, {"error": f"upload must be 1 byte to {MAX_UPLOAD // 2**20} MB"})
        body = self.rfile.read(length)
        try:
            query = parse_qs(url.query)
            n_perm = int(query.get("n_perm", ["1000000"])[0])
            seed = int(query.get("seed", ["0"])[0])
            source = query.get("name", ["upload.csv"])[0][:200]
            if not 1 <= n_perm <= MAX_PERM:
                raise ValueError(f"n_perm must be between 1 and {MAX_PERM:,}")
            records = parse_data(body.decode("utf-8-sig"))
            if not records:
                raise ValueError("CSV has no rows")
        except (ValueError, UnicodeDecodeError) as e:
            return self._json(HTTPStatus.BAD_REQUEST, {"error": str(e)})
        if not self.job.start(records, n_perm, seed, source):
            return self._json(HTTPStatus.CONFLICT, {"error": "a computation is already running"})
        self._json(HTTPStatus.ACCEPTED, {"state": "running"})

    def _json(self, status, obj):
        self._send(status, json.dumps(obj).encode(), "application/json")

    def _send(self, status, body: bytes, content_type: str):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        if not self.path.startswith("/api/status"):
            super().log_message(fmt, *args)


def serve(host: str, port: int):
    Handler.job = Job()
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"serving on http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    args = ap.parse_args()
    serve(args.host, args.port)


if __name__ == "__main__":
    main()
