#!/usr/bin/env python3
"""End-to-end pipeline validation: capture → real YOLO inference → ByteTrack →
XY anonymisation → SQLite queue → send.

This test exercises the full EdgeGateway pipeline with a real ultralytics model
in place of STUB mode.  It does NOT use mediamtx or a live RTSP stream — it
feeds synthetic frames directly to _yolo_detections() to keep the test fast and
dependency-free (no mediamtx needed in the validation environment).

For the full RTSP path (with mediamtx), see edge/tests/test_rtsp_capture.py and
conftest.py's mediamtx_rtsp fixture — those tests run when mediamtx is on PATH.

Usage:
    python3 test_pipeline_e2e.py [--model PATH]

Exit codes:
    0 — pipeline passed end-to-end
    1 — one or more stages failed
"""

import argparse
import pathlib
import sys
import tempfile
import threading
import time
import uuid
from typing import Any
from unittest.mock import MagicMock, patch

import cv2


def _load_model(model_path: str) -> Any:
    from ultralytics import YOLO
    print(f"Loading model for E2E test: {model_path}")
    return YOLO(model_path)


def _get_real_frame() -> Any:
    """Return a real 320×240 BGR frame from the bundled bus.jpg."""
    import ultralytics as _ul
    assets = pathlib.Path(_ul.__file__).parent / "assets"
    frame = cv2.imread(str(assets / "bus.jpg"))
    return cv2.resize(frame, (320, 240))


def _run_pipeline(model_path: str) -> bool:
    """Drive the full gateway pipeline with real inference.

    Stages tested:
      1. _yolo_detections(frame, model) — real ByteTrack inference → person detections
      2. Enqueue results to SQLite InferenceQueue
      3. Flush queue to a mock HTTP endpoint
      4. Assert at least 1 person event was sent
    """
    sys.path.insert(0, str(pathlib.Path(__file__).parents[1]))
    from edge.inference_queue import InferenceQueue
    from edge.gateway import _yolo_detections

    model = _load_model(model_path)
    frame = _get_real_frame()

    # ── Stage 1: real inference ───────────────────────────────────────────────
    print("\n── Stage 1: real YOLO + ByteTrack inference ──")
    detections = _yolo_detections(frame, model)
    if not detections:
        print("  FAIL: _yolo_detections returned 0 detections on a real frame")
        return False
    print(f"  PASS: {len(detections)} detection(s) from real inference")
    for d in detections:
        print(f"    person_id={d['person_id']} x={d['x']} y={d['y']}")

    # ── Stage 2: enqueue to SQLite ────────────────────────────────────────────
    print("\n── Stage 2: SQLite queue enqueue ──")
    tmp_db = str(pathlib.Path(tempfile.mkdtemp()) / "pipeline_test.db")
    queue = InferenceQueue(db_path=tmp_db)
    camera_id = str(uuid.uuid4())
    ts = "2026-07-21T00:00:00+00:00"

    for det in detections:
        queue.enqueue({
            "camera_id": camera_id,
            "person_id": det["person_id"],
            "x": det["x"],
            "y": det["y"],
            "time": ts,
        })

    count = queue.pending_count()
    if count == 0:
        print("  FAIL: queue is empty after enqueue")
        return False
    print(f"  PASS: {count} item(s) in queue")

    # ── Stage 3: flush to mock HTTP endpoint ─────────────────────────────────
    print("\n── Stage 3: flush → mock HTTP send ──")
    sent_payloads: list[dict] = []

    def mock_send(payload: dict) -> None:
        sent_payloads.append(payload)

    sent, failed = queue.flush(mock_send)
    if sent == 0:
        print(f"  FAIL: queue.flush sent=0 failed={failed}")
        return False
    print(f"  PASS: queue.flush sent={sent} failed={failed}")

    # ── Stage 4: assert XY coordinates are within frame bounds ───────────────
    print("\n── Stage 4: XY anonymisation bounds check ──")
    h, w = frame.shape[:2]
    oob = [p for p in sent_payloads if not (0 <= p["x"] < w and 0 <= p["y"] < h)]
    if oob:
        print(f"  FAIL: {len(oob)} payload(s) had XY out of {w}x{h} bounds: {oob[:2]}")
        return False
    print(f"  PASS: all {len(sent_payloads)} XY coordinate(s) within {w}x{h} bounds")

    # ── Summary ───────────────────────────────────────────────────────────────
    print("\n── Pipeline summary ──")
    print(f"  Detections : {len(detections)}")
    print(f"  Enqueued   : {len(detections)}")
    print(f"  Sent       : {sent}")
    print(f"  Failed     : {failed}")
    return True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="yolov8n.pt")
    args = parser.parse_args()

    from datetime import date
    print("=" * 60)
    print("Traxia Edge — E2E Pipeline Validation")
    print(f"Date: {date.today().isoformat()}")
    print(f"Model: {args.model}")
    print("Stages: inference → queue → flush → XY bounds")
    print("=" * 60)

    ok = _run_pipeline(args.model)

    print("\n" + "=" * 60)
    if ok:
        print("RESULT: PIPELINE E2E PASSED ✓")
        sys.exit(0)
    else:
        print("RESULT: PIPELINE E2E FAILED ✗")
        sys.exit(1)


if __name__ == "__main__":
    main()
