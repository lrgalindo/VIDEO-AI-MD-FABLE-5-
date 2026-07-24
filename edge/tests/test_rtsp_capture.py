"""Tests for RTSPCapture: FPS downsampling and mediamtx integration.

Unit tests use synthetic OpenCV frames via VideoWriter to a temp file —
no real RTSP stream required.  The mediamtx integration test is skipped
automatically when mediamtx is not installed.
"""

import shutil
import time
from pathlib import Path

import cv2
import numpy as np
import pytest

from edge.rtsp_capture import RTSPCapture


# ---------------------------------------------------------------------------
# Synthetic video helpers
# ---------------------------------------------------------------------------

def _write_test_video(path: Path, *, num_frames: int = 90, fps: int = 30) -> str:
    """Write a short synthetic video and return its file:// path."""
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(path), fourcc, fps, (320, 240))
    for i in range(num_frames):
        frame = np.zeros((240, 320, 3), dtype=np.uint8)
        frame[:, :, 0] = i % 256  # vary colour so frames aren't identical
        writer.write(frame)
    writer.release()
    return str(path)


# ---------------------------------------------------------------------------
# FPS downsampling — unit tests (no RTSP required)
# ---------------------------------------------------------------------------

def test_fps_downsampling_3fps(tmp_path: Path) -> None:
    """30-FPS source → 3 FPS capture → ~10% of frames delivered."""
    video_path = _write_test_video(tmp_path / "test.mp4", num_frames=90, fps=30)
    cap = RTSPCapture(source=video_path, target_fps=3)
    delivered: list[np.ndarray] = []
    cap.capture_loop(delivered.append)
    # 90 source frames at 30 fps / 3 target fps = ~9 frames (allow ±2 for rounding)
    assert 7 <= len(delivered) <= 11, (
        f"Expected ~9 delivered frames at 3 FPS from 90-frame/30fps source, got {len(delivered)}"
    )


def test_fps_downsampling_10fps(tmp_path: Path) -> None:
    """30-FPS source → 10 FPS capture → ~33% of frames delivered."""
    video_path = _write_test_video(tmp_path / "test.mp4", num_frames=90, fps=30)
    cap = RTSPCapture(source=video_path, target_fps=10)
    delivered: list[np.ndarray] = []
    cap.capture_loop(delivered.append)
    # ~30 frames (allow ±4 for rounding)
    assert 26 <= len(delivered) <= 34, (
        f"Expected ~30 delivered frames at 10 FPS from 90-frame/30fps source, got {len(delivered)}"
    )


def test_fps_downsampling_5fps(tmp_path: Path) -> None:
    """30-FPS source → 5 FPS capture → ~17% of frames delivered."""
    video_path = _write_test_video(tmp_path / "test.mp4", num_frames=90, fps=30)
    cap = RTSPCapture(source=video_path, target_fps=5)
    delivered: list[np.ndarray] = []
    cap.capture_loop(delivered.append)
    assert 13 <= len(delivered) <= 20, (
        f"Expected ~15 delivered frames at 5 FPS from 90-frame/30fps source, got {len(delivered)}"
    )


def test_frames_are_numpy_bgr(tmp_path: Path) -> None:
    """Frames delivered to on_frame are numpy arrays with 3 colour channels."""
    video_path = _write_test_video(tmp_path / "test.mp4", num_frames=15, fps=30)
    cap = RTSPCapture(source=video_path, target_fps=3)
    frames: list[np.ndarray] = []
    cap.capture_loop(frames.append)
    assert frames, "At least one frame must be delivered"
    f = frames[0]
    assert isinstance(f, np.ndarray)
    assert f.ndim == 3 and f.shape[2] == 3, f"Expected HxWx3 BGR array, got shape {f.shape}"


def test_invalid_fps_raises() -> None:
    """target_fps outside [3, 10] must raise ValueError."""
    with pytest.raises(ValueError):
        RTSPCapture(source="rtsp://whatever", target_fps=2)
    with pytest.raises(ValueError):
        RTSPCapture(source="rtsp://whatever", target_fps=11)


def test_max_frames_limit(tmp_path: Path) -> None:
    """max_frames stops the loop after reading that many source frames."""
    video_path = _write_test_video(tmp_path / "test.mp4", num_frames=60, fps=30)
    cap = RTSPCapture(source=video_path, target_fps=10)
    delivered: list[np.ndarray] = []
    cap.capture_loop(delivered.append, max_frames=15)
    # 15 source frames at 30fps / 10fps = ~5 delivered
    assert len(delivered) <= 6, (
        f"max_frames=15 should deliver at most ~5 frames at 10 FPS, got {len(delivered)}"
    )


# ---------------------------------------------------------------------------
# mediamtx integration test — skipped when mediamtx is not available
# ---------------------------------------------------------------------------

@pytest.mark.mediamtx
def test_rtsp_capture_via_mediamtx(mediamtx_rtsp: str) -> None:
    """Capture frames from a live RTSP stream served by mediamtx.

    Verifies that:
    1. RTSPCapture can open an RTSP URL.
    2. Frames arrive and are delivered at the configured FPS.
    3. The frame shape is correct (H×W×3 BGR).
    """
    cap = RTSPCapture(source=mediamtx_rtsp, target_fps=3)
    frames: list[np.ndarray] = []

    start = time.monotonic()
    # Read for ~3 seconds (9 frames expected at 3 FPS)
    cap.capture_loop(frames.append, max_frames=90)  # 90 source frames @ 30fps ≈ 3s
    elapsed = time.monotonic() - start

    assert len(frames) >= 3, (
        f"Expected at least 3 frames in {elapsed:.1f}s from mediamtx RTSP source, "
        f"got {len(frames)}"
    )
    f = frames[0]
    assert isinstance(f, np.ndarray) and f.ndim == 3 and f.shape[2] == 3, (
        f"Frame must be H×W×3 BGR numpy array, got shape {f.shape}"
    )
