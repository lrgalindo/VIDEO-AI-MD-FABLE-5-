"""Threaded HTTP mock server for edge gateway tests.

Exposes just enough of the Cloud API surface to exercise the Model Manager
and InferenceQueue without a running FastAPI instance.

Usage
-----
    with MockCloudServer() as srv:
        # srv.url  — base URL e.g. "http://127.0.0.1:PORT"
        # srv.received  — list of dicts POSTed to /v1/telemetry/ingest
        manager = ModelManager(cloud_api_url=srv.url, ...)
"""

import hashlib
import http.server
import json
import os
import threading
import time
from pathlib import Path
from typing import Optional


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65_536), b""):
            h.update(chunk)
    return h.hexdigest()


class MockCloudServer:
    """Self-contained HTTP server for testing Model Manager and queue behaviour.

    Parameters
    ----------
    model_file:
        Path to a real file that will be served as the "model" download.
        SHA-256 is computed from this file; manifest reports its real checksum.
    expire_after_bytes:
        If > 0, the download endpoint returns 403 after this many bytes have
        been served. The next GET after a manifest re-fetch succeeds normally.
        Simulates a signed-URL expiry mid-download.
    reject_ingest:
        When True, POST /v1/telemetry/ingest returns 503. Flip to False to
        simulate cloud recovery.
    """

    def __init__(
        self,
        model_file: Path,
        expire_after_bytes: int = 0,
        reject_ingest: bool = False,
    ) -> None:
        self.model_file = model_file
        self.model_size = model_file.stat().st_size
        self.model_sha256 = _sha256(model_file)
        self.expire_after_bytes = expire_after_bytes
        self.reject_ingest = reject_ingest
        self.received: list[dict] = []
        self._manifest_fetches = 0
        self._bytes_served = 0
        self._expired_once = False
        self._server: Optional[http.server.HTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    @property
    def url(self) -> str:
        assert self._server is not None
        host, port = self._server.server_address
        return f"http://{host}:{port}"

    def __enter__(self) -> "MockCloudServer":
        self.start()
        return self

    def __exit__(self, *_: object) -> None:
        self.stop()

    def start(self) -> None:
        parent = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args: object) -> None:
                pass  # suppress default HTTP logging in test output

            def do_GET(self) -> None:
                if self.path.startswith("/v1/models/") and self.path.endswith("/manifest"):
                    parent._manifest_fetches += 1
                    body = json.dumps({
                        "version": "1.0.0",
                        "filename": "yolo_retail.pt",
                        "download_url": f"{parent.url}/download/model.pt",
                        "sha256": parent.model_sha256,
                        "size": parent.model_size,
                    }).encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)

                elif self.path == "/download/model.pt":
                    range_header = self.headers.get("Range", "")
                    offset = 0
                    if range_header.startswith("bytes="):
                        offset = int(range_header.split("=")[1].split("-")[0])

                    # Simulate URL expiry: return 403 until the client re-fetches the manifest
                    if (
                        parent.expire_after_bytes > 0
                        and not parent._expired_once
                        and parent._bytes_served + (parent.model_size - offset) > parent.expire_after_bytes
                    ):
                        parent._expired_once = True
                        self.send_response(403)
                        self.end_headers()
                        return

                    data = parent.model_file.read_bytes()[offset:]
                    status = 206 if offset > 0 else 200
                    self.send_response(status)
                    self.send_header("Content-Type", "application/octet-stream")
                    self.send_header("Content-Length", str(len(data)))
                    if status == 206:
                        self.send_header(
                            "Content-Range",
                            f"bytes {offset}-{parent.model_size - 1}/{parent.model_size}",
                        )
                    self.end_headers()
                    self.wfile.write(data)
                    parent._bytes_served += len(data)

                else:
                    self.send_response(404)
                    self.end_headers()

            def do_POST(self) -> None:
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length)

                if self.path == "/v1/telemetry/ingest":
                    if parent.reject_ingest:
                        self.send_response(503)
                        self.end_headers()
                        return
                    parent.received.append(json.loads(body))
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(b'{"ok":true}')
                else:
                    self.send_response(404)
                    self.end_headers()

        self._server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()
