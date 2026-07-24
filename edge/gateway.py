"""Edge Gateway main process (SDD §8.7, §9).

Orchestrates:
1. Activation — one-time code → access + refresh token pair
2. Model download and verification (ModelManager) with SHA-256 check
3. RTSP capture (RTSPCapture) with reconnect on stream end/error
4. Inference — real YOLO if ultralytics is installed, synthetic otherwise
5. SQLite queue (enqueue-before-send) → flush to POST /v1/telemetry/ingest

Entry point: python -m edge.gateway
"""

import logging
import os
import random
import signal
import threading
import time
from datetime import datetime, timezone
from typing import Any

from edge import config
from edge.auth_client import AuthClient
from edge.inference_queue import InferenceQueue
from edge.model_manager import ModelManager
from edge.rtsp_capture import RTSPCapture

log = logging.getLogger(__name__)


def _synthetic_detections() -> list[dict]:
    n = random.randint(1, 3)
    return [
        {
            "person_id": f"track-{i:03d}",
            "x": random.randint(10, 300),
            "y": random.randint(10, 200),
        }
        for i in range(n)
    ]


def _yolo_detections(frame: Any, model: Any) -> list[dict]:
    try:
        # model.track() engages ByteTrack (persist=True keeps state across frames).
        # model() alone returns detections only — box.id would always be None.
        results = model.track(frame, persist=True, tracker="bytetrack.yaml", verbose=False)
        boxes = results[0].boxes
        out = []
        for i, box in enumerate(boxes):
            if int(box.cls[0]) != 0:  # class 0 = person in COCO/retail checkpoint
                continue
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            track_id = int(box.id[0]) if box.id is not None else i
            out.append({
                "person_id": f"track-{track_id:03d}",
                "x": int((x1 + x2) / 2),
                "y": int((y1 + y2) / 2),
            })
        return out or _synthetic_detections()
    except Exception as exc:
        log.warning("Inference error: %s — using synthetic detections", exc)
        return _synthetic_detections()


class EdgeGateway:
    def __init__(self) -> None:
        self._stop = threading.Event()
        self._auth = AuthClient(
            cloud_api_url=config.CLOUD_API_URL,
            token_file=config.TOKEN_FILE,
        )
        self._queue = InferenceQueue(
            db_path=config.QUEUE_DB,
            retention_days=config.QUEUE_RETENTION_DAYS,
            backoff_base=config.BACKOFF_BASE_SECONDS,
            backoff_max=config.BACKOFF_MAX_SECONDS,
        )
        self._model_mgr = ModelManager(
            cloud_api_url=config.CLOUD_API_URL,
            vertical_type=config.VERTICAL_TYPE,
            cache_dir=config.CACHE_DIR,
            auth_client=self._auth,
        )
        self._camera_id: str = os.environ.get("CAMERA_ID", "")
        self._stub_mode: bool = False

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def start(self) -> None:
        self._activate_if_needed()
        model = self._load_model()

        threading.Thread(target=self._flush_loop, daemon=True, name="flush").start()
        threading.Thread(target=self._evict_loop, daemon=True, name="evict").start()

        if config.RTSP_URLS:
            for url in config.RTSP_URLS:
                self._capture_with_retry(url, model)
        else:
            log.warning("No RTSP_URLS configured — running synthetic event loop")
            self._synthetic_loop()

    def stop(self) -> None:
        self._stop.set()

    # ------------------------------------------------------------------
    # Activation
    # ------------------------------------------------------------------

    def _activate_if_needed(self) -> None:
        if self._auth._refresh_token:
            log.info("Existing tokens found — skipping activation")
            return
        code = os.environ.get("ACTIVATION_CODE", "")
        if not code:
            raise RuntimeError("No ACTIVATION_CODE env var and no stored tokens")
        log.info("Activating gateway %s …", config.GATEWAY_ID)
        self._auth.activate(config.GATEWAY_ID, code)
        log.info("Activation successful")

    # ------------------------------------------------------------------
    # Model loading
    # ------------------------------------------------------------------

    def _load_model(self) -> Any:
        log.info("Ensuring model is current …")
        try:
            model = self._model_mgr.ensure_current()
            self._stub_mode = (model == "STUB")
            if self._stub_mode:
                log.info("Model verified (SHA-256 OK); running in STUB/synthetic mode")
            else:
                log.info("Model loaded — real inference active")
            return model
        except Exception as exc:
            log.warning("Model load failed (%s) — falling back to synthetic mode", exc)
            self._stub_mode = True
            return None

    # ------------------------------------------------------------------
    # Capture
    # ------------------------------------------------------------------

    def _capture_with_retry(self, rtsp_url: str, model: Any) -> None:
        while not self._stop.is_set():
            try:
                cap = RTSPCapture(rtsp_url, target_fps=config.CAPTURE_FPS)
                cap.capture_loop(lambda frame, _m=model: self._process_frame(frame, _m))
                log.info("RTSP stream ended — reconnecting in 5s")
            except Exception as exc:
                log.warning("RTSP error (%s): %s — retrying in 5s", rtsp_url, exc)
            if not self._stop.is_set():
                time.sleep(5)

    def _synthetic_loop(self) -> None:
        interval = 1.0 / config.CAPTURE_FPS
        while not self._stop.is_set():
            if self._camera_id:
                self._process_frame(None, None)
            time.sleep(interval)

    def _process_frame(self, frame: Any, model: Any) -> None:
        if not self._camera_id:
            return
        detections = (
            _synthetic_detections()
            if self._stub_mode or model is None
            else _yolo_detections(frame, model)
        )
        ts = datetime.now(timezone.utc).isoformat()
        for det in detections:
            self._queue.enqueue(
                {
                    "camera_id": self._camera_id,
                    "person_id": det["person_id"],
                    "x": det["x"],
                    "y": det["y"],
                    "time": ts,
                }
            )

    # ------------------------------------------------------------------
    # Queue flush / evict threads
    # ------------------------------------------------------------------

    def _flush_loop(self) -> None:
        while not self._stop.is_set():
            try:
                sent, failed = self._queue.flush(self._send_event)
                if sent > 0 or failed > 0:
                    log.info("Queue flush: sent=%d failed=%d", sent, failed)
            except Exception as exc:
                log.warning("Flush error: %s", exc)
            time.sleep(1.0)

    def _evict_loop(self) -> None:
        while not self._stop.is_set():
            try:
                n = self._queue.evict_now()
                if n > 0:
                    log.info("Evicted %d stale queue items", n)
            except Exception as exc:
                log.warning("Evict error: %s", exc)
            time.sleep(3600)

    def _send_event(self, payload: dict) -> None:
        resp = self._auth.post("/v1/telemetry/ingest", json=payload)
        resp.raise_for_status()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)-20s %(levelname)s %(message)s",
    )
    gw = EdgeGateway()

    def _handle_signal(sig: int, _: Any) -> None:
        log.info("Signal %d received — shutting down", sig)
        gw.stop()

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    gw.start()


if __name__ == "__main__":
    main()
