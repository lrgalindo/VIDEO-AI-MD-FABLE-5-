"""RTSP capture with configurable FPS downsampling (SDD §4, §7.2).

Reads an RTSP stream (or any OpenCV-compatible source) and calls `on_frame`
for every frame that survives the downsampling gate.

Downsampling strategy
---------------------
- Source FPS known (file or stream that reports CAP_PROP_FPS > 0):
    Frame-skip gate — deliver every round(source_fps / target_fps)-th frame.
    Correct for both file sources and RTSP streams with reliable metadata.
- Source FPS unknown (live RTSP reporting 0):
    Wall-clock gate — deliver a frame only when at least 1/target_fps seconds
    have elapsed since the last delivery.

Target FPS must be between 3 and 10 (per SDD §7.2).
"""

import logging
import time
from typing import Callable

import cv2
import numpy as np

from edge import config

log = logging.getLogger(__name__)

_FPS_MIN = 3
_FPS_MAX = 10


class RTSPCapture:
    def __init__(
        self,
        source: str,
        target_fps: int = config.CAPTURE_FPS,
    ) -> None:
        if not (_FPS_MIN <= target_fps <= _FPS_MAX):
            raise ValueError(f"target_fps must be {_FPS_MIN}–{_FPS_MAX}, got {target_fps}")
        self.source = source
        self.target_fps = target_fps

    def capture_loop(
        self,
        on_frame: Callable[[np.ndarray], None],
        *,
        max_frames: int = 0,
    ) -> int:
        """Read frames from the source, calling on_frame at target_fps.

        Args:
            on_frame: callback invoked with each sampled frame (numpy BGR array).
            max_frames: stop after this many total source frames read (0 = stream end).

        Returns:
            Number of frames passed to on_frame.
        """
        cap = cv2.VideoCapture(self.source)
        if not cap.isOpened():
            raise RuntimeError(f"Cannot open source: {self.source}")

        source_fps = cap.get(cv2.CAP_PROP_FPS)
        log.info("Source FPS: %.1f → downsampled to %d FPS", source_fps or 0, self.target_fps)

        use_clock_gate = not source_fps or source_fps <= 0
        skip_every = max(1, round(source_fps / self.target_fps)) if not use_clock_gate else 1
        interval = 1.0 / self.target_fps

        frame_count = 0
        delivered = 0
        last_delivered = time.monotonic() - interval  # first frame always eligible

        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    log.info("Stream ended after %d source frames", frame_count)
                    break

                frame_count += 1
                if max_frames and frame_count > max_frames:
                    break

                if use_clock_gate:
                    now = time.monotonic()
                    if now - last_delivered >= interval * 0.9:
                        on_frame(frame)
                        delivered += 1
                        last_delivered = now
                else:
                    if frame_count % skip_every == 1:
                        on_frame(frame)
                        delivered += 1
        finally:
            cap.release()

        return delivered
