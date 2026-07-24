"""Shared pytest fixtures for edge gateway tests."""

import hashlib
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Generator

import pytest


# ---------------------------------------------------------------------------
# Temporary directories
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_cache(tmp_path: Path) -> Path:
    cache = tmp_path / "model_cache"
    cache.mkdir()
    return cache


@pytest.fixture()
def tmp_queue_db(tmp_path: Path) -> str:
    return str(tmp_path / "queue.db")


# ---------------------------------------------------------------------------
# Fake model file (stands in for yolo_retail.pt in unit tests)
# ---------------------------------------------------------------------------

@pytest.fixture()
def fake_model_file(tmp_path: Path) -> Path:
    """A small binary file with known SHA-256, used instead of a real .pt."""
    content = b"FAKE_YOLO_MODEL_BYTES_" * 512  # ~10 KB
    p = tmp_path / "fake_model.pt"
    p.write_bytes(content)
    return p


@pytest.fixture()
def fake_model_sha256(fake_model_file: Path) -> str:
    h = hashlib.sha256()
    h.update(fake_model_file.read_bytes())
    return h.hexdigest()


# ---------------------------------------------------------------------------
# mediamtx RTSP server fixture
# ---------------------------------------------------------------------------

_MEDIAMTX = shutil.which("mediamtx")


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "mediamtx: requires mediamtx binary on PATH")


def _mediamtx_available() -> bool:
    return _MEDIAMTX is not None


@pytest.fixture()
def mediamtx_rtsp(tmp_path: Path) -> Generator[str, None, None]:
    """Start a mediamtx server + ffmpeg publisher serving a synthetic video via RTSP.

    Yields the RTSP URL once the stream is confirmed live.
    Skips the test if mediamtx or ffmpeg is not installed.
    """
    if not _mediamtx_available():
        pytest.skip("mediamtx not found on PATH — skipping RTSP integration test")

    ffmpeg_bin = shutil.which("ffmpeg")
    if not ffmpeg_bin:
        pytest.skip("ffmpeg not found — cannot generate RTSP test stream")

    # Minimal mediamtx config: accept any publisher, no auth
    cfg = tmp_path / "mediamtx.yml"
    cfg.write_text(
        "logLevel: error\n"
        "rtspAddress: :18554\n"
        "paths:\n"
        "  all_others:\n"
    )

    rtsp_url = "rtsp://127.0.0.1:18554/test"
    mediamtx_proc = subprocess.Popen(
        [_MEDIAMTX, str(cfg)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(1.0)  # let mediamtx bind the port

    # Push a 15-second synthetic test pattern at 30 fps
    feeder_proc = subprocess.Popen(
        [
            ffmpeg_bin, "-re",
            "-f", "lavfi", "-i", "testsrc=duration=15:size=320x240:rate=30",
            "-c:v", "libx264", "-preset", "ultrafast", "-tune", "zerolatency",
            "-f", "rtsp", "-rtsp_transport", "tcp", rtsp_url,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # Poll until the stream is reachable (up to 8 seconds)
    import cv2 as _cv2
    deadline = time.monotonic() + 8.0
    ready = False
    while time.monotonic() < deadline:
        cap = _cv2.VideoCapture(rtsp_url)
        if cap.isOpened():
            cap.release()
            ready = True
            break
        cap.release()
        time.sleep(0.5)

    if not ready:
        feeder_proc.terminate()
        mediamtx_proc.terminate()
        mediamtx_proc.wait(timeout=5)
        pytest.skip("mediamtx RTSP stream did not become available within 8s")

    try:
        yield rtsp_url
    finally:
        feeder_proc.terminate()
        mediamtx_proc.terminate()
        mediamtx_proc.wait(timeout=5)
