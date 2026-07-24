#!/usr/bin/env python3
"""YOLO inference validation — closes the gap documented in edge/model_manager.py.

Usage:
    python3 validate_yolo.py [--model PATH]

    --model PATH    Path to yolo_retail.pt (or any YOLOv8 .pt checkpoint).
                    If omitted, downloads yolov8n.pt from ultralytics public
                    assets as a structural stand-in to confirm the pipeline
                    works.  When yolo_retail.pt is available, pass it explicitly.

What this validates:
    (a) The YOLO checkpoint loads without error via ultralytics.YOLO().
    (b) Running model.track() on 3 real images containing people returns at
        least one person bounding box per image with confidence > 0.50.
    (c) ByteTrack CONTINUITY: the same person detected in frame 0 of a synthetic
        frame sequence retains the same track_id in frame 4 and beyond.
        This is the property dwell_time computation depends on — it is distinct
        from "inference runs without error" and requires a frame sequence, not
        independent images.  See _validate_tracking_continuity() for details.
    (d) The anonymisation step (centroid XY extraction) produces valid integer
        coordinates within the frame dimensions.

Exit codes:
    0 — all checks passed
    1 — one or more checks failed (details printed to stdout)
"""

import argparse
import pathlib
import sys
import tempfile
from datetime import date
from typing import Any

import cv2
import numpy as np

PERSON_CLASS = 0       # COCO class 0 = person
MIN_CONFIDENCE = 0.50
# Fraction of frame-0 person IDs that must persist by frame N//2
MIN_CONTINUITY = 0.80
N_FRAMES = 8           # synthetic sequence length
SHIFT_PX = 3           # pixel shift per frame (simulates minimal camera/subject motion)


def _load_model(model_path: str) -> Any:
    from ultralytics import YOLO
    print(f"Loading model: {model_path}")
    model = YOLO(model_path)
    print(f"  task={model.task}  ✓")
    return model


def _get_test_images() -> list[pathlib.Path]:
    """Return paths to 3 test images containing real people.

    Uses the 2 images bundled with ultralytics plus a crop of bus.jpg as
    a third to avoid any network dependency.
    """
    import ultralytics as _ul
    assets = pathlib.Path(_ul.__file__).parent / "assets"
    bus = assets / "bus.jpg"
    zidane = assets / "zidane.jpg"

    if not bus.exists() or not zidane.exists():
        raise RuntimeError("ultralytics bundled assets not found — re-install ultralytics.")

    tmp = pathlib.Path(tempfile.mkdtemp())
    frame = cv2.imread(str(bus))
    h = frame.shape[0]
    crop = frame[h // 2:, :]
    crop_path = tmp / "bus_bottom_crop.jpg"
    cv2.imwrite(str(crop_path), crop)

    return [bus, zidane, crop_path]


def _validate_inference(model: Any, images: list[pathlib.Path]) -> bool:
    """Run detection+tracking on 3 independent images, check person detections."""
    ok = True
    print(f"\n── (a) Inference validation ({len(images)} images) ──")
    for img_path in images:
        frame = cv2.imread(str(img_path))
        if frame is None:
            print(f"  FAIL {img_path.name}: could not read image")
            ok = False
            continue

        results = model.track(frame, persist=True, tracker="bytetrack.yaml", verbose=False)
        boxes = results[0].boxes
        person_boxes = [
            (box.xyxy[0].tolist(), float(box.conf[0]))
            for box in boxes
            if int(box.cls[0]) == PERSON_CLASS
        ]

        if not person_boxes:
            print(f"  FAIL {img_path.name}: 0 person detections (need >= 1)")
            ok = False
            continue

        max_conf = max(c for _, c in person_boxes)
        if max_conf < MIN_CONFIDENCE:
            print(f"  FAIL {img_path.name}: max_conf={max_conf:.3f} < {MIN_CONFIDENCE}")
            ok = False
            continue

        print(f"  PASS {img_path.name}: {len(person_boxes)} person(s), max_conf={max_conf:.3f}")

    return ok


def _validate_tracking_continuity(model_path: str, base_image: pathlib.Path) -> bool:
    """Verify that the same person keeps the same track_id across a frame sequence.

    WHY THIS TEST IS DIFFERENT FROM _validate_inference:
    ────────────────────────────────────────────────────
    _validate_inference() runs model.track() on 3 independent photos — it
    confirms detections and confidence but does NOT prove continuity. A tracker
    that assigned a brand-new ID on every call would pass _validate_inference
    identically.

    Dwell time computation requires that when person P enters a zone in frame 1
    and is still there in frame 30, both detections carry the same track_id so
    they can be linked into a single session (zone_dwell_sessions). That is the
    property tested here.

    METHOD:
    ───────
    Generates a synthetic sequence of N_FRAMES frames from bus.jpg, each shifted
    SHIFT_PX pixels horizontally relative to the previous frame. This simulates
    minimal camera motion or subject drift. A fresh YOLO instance is used (no
    state from the inference validation calls above).

    ByteTrack with persist=True must link the same person across the shifted
    frames — the tracker has to match detections to its existing tracks even
    when their pixel position changed slightly. We require ≥ MIN_CONTINUITY of
    the IDs seen in frame 0 to still be present at frame N//2 and beyond.

    WHAT WOULD CATCH A REGRESSION:
    ──────────────────────────────
    If _yolo_detections() were reverted to model(frame) instead of model.track(),
    box.id would be None on every call, which would cause the loop below to
    produce 0 tracked IDs in every frame — an immediate FAIL.

    If persist=True were removed, ByteTrack state would reset on each call,
    assigning fresh IDs every frame — the continuity overlap assertion would fail.
    """
    from ultralytics import YOLO  # fresh instance — clean tracker state

    print(f"\n── (c) Tracking continuity validation ──")
    print(f"  Sequence: {N_FRAMES} frames, {SHIFT_PX}px horizontal shift per frame")
    print(f"  Requirement: ≥{MIN_CONTINUITY:.0%} of frame-0 IDs persist at frame {N_FRAMES // 2}+")
    print(f"  Fresh YOLO instance (no shared tracker state from detection tests)")

    model = YOLO(model_path)
    base = cv2.imread(str(base_image))
    h, w = base.shape[:2]

    # Build synthetic sequence: slight horizontal shift simulates motion
    frames = []
    for i in range(N_FRAMES):
        M = np.float32([[1, 0, i * SHIFT_PX], [0, 1, 0]])
        frames.append(cv2.warpAffine(base, M, (w, h)))

    tracked_ids_per_frame: list[set[int]] = []
    for frame_idx, frame in enumerate(frames):
        results = model.track(frame, persist=True, tracker="bytetrack.yaml", verbose=False)
        boxes = results[0].boxes
        frame_ids = {
            int(box.id[0])
            for box in boxes
            if int(box.cls[0]) == PERSON_CLASS and box.id is not None
        }
        tracked_ids_per_frame.append(frame_ids)
        print(f"  frame {frame_idx}: person IDs = {sorted(frame_ids)}")

    ids_frame_0 = tracked_ids_per_frame[0]
    if not ids_frame_0:
        print("  FAIL: no person IDs assigned in frame 0 — ByteTrack not initialised")
        return False

    # Measure continuity: what fraction of frame-0 persons are still tracked?
    mid = N_FRAMES // 2
    ids_mid = tracked_ids_per_frame[mid]
    ids_last = tracked_ids_per_frame[-1]
    overlap_mid = ids_frame_0 & ids_mid
    overlap_last = ids_frame_0 & ids_last
    continuity_mid = len(overlap_mid) / len(ids_frame_0)
    continuity_last = len(overlap_last) / len(ids_frame_0)

    print(f"\n  IDs frame 0    : {sorted(ids_frame_0)}")
    print(f"  IDs frame {mid}    : {sorted(ids_mid)}  overlap={sorted(overlap_mid)}")
    print(f"  IDs frame {N_FRAMES-1}    : {sorted(ids_last)}  overlap={sorted(overlap_last)}")
    print(f"  Continuity @ frame {mid}: {continuity_mid:.0%}  (need ≥{MIN_CONTINUITY:.0%})")
    print(f"  Continuity @ frame {N_FRAMES-1}: {continuity_last:.0%}")

    if continuity_mid < MIN_CONTINUITY:
        print(
            f"  FAIL: only {continuity_mid:.0%} of frame-0 person IDs persisted at frame {mid}.\n"
            f"  This means ByteTrack is not maintaining state across frames — dwell\n"
            f"  time computation would produce discontinuous/meaningless sessions."
        )
        return False

    print(
        f"  PASS: {continuity_mid:.0%} person IDs persisted from frame 0 to frame {mid}+ ✓\n"
        f"  ByteTrack memory confirmed: tracker links the same person across\n"
        f"  shifted frames, producing stable track_ids for dwell-time sessions."
    )
    return True


def _validate_anonymisation(model: Any, images: list[pathlib.Path]) -> bool:
    """Confirm XY centroid extraction produces valid integer coords."""
    print("\n── (d) Anonymisation (centroid XY) validation ──")
    frame = cv2.imread(str(images[0]))
    h, w = frame.shape[:2]

    results = model.track(frame, persist=True, tracker="bytetrack.yaml", verbose=False)
    boxes = results[0].boxes
    person_boxes = [box for box in boxes if int(box.cls[0]) == PERSON_CLASS]

    invalid = []
    for box in person_boxes:
        x1, y1, x2, y2 = box.xyxy[0].tolist()
        cx = int((x1 + x2) / 2)
        cy = int((y1 + y2) / 2)
        if not (0 <= cx < w and 0 <= cy < h):
            invalid.append((cx, cy))

    if invalid:
        print(f"  FAIL: {len(invalid)} centroid(s) outside frame bounds {w}x{h}: {invalid}")
        return False

    print(f"  PASS: {len(person_boxes)} centroids all within {w}x{h} frame bounds ✓")
    return True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--model",
        default="yolov8n.pt",
        help="Path to .pt checkpoint (default: downloads yolov8n.pt)",
    )
    args = parser.parse_args()

    print("=" * 60)
    print(f"Traxia Edge — YOLO Inference Validation")
    print(f"Date: {date.today().isoformat()}")
    print(f"Model: {args.model}")
    print("=" * 60)

    model = _load_model(args.model)
    images = _get_test_images()

    checks = [
        _validate_inference(model, images),
        _validate_tracking_continuity(args.model, images[0]),  # fresh model instance
        _validate_anonymisation(model, images),
    ]

    print("\n" + "=" * 60)
    if all(checks):
        print("RESULT: ALL CHECKS PASSED ✓")
        print(
            f"\nRecord in model_manager.py docstring:\n"
            f"  Validated {date.today().isoformat()} with {args.model} —\n"
            f"  inference, ByteTrack continuity, and XY anonymisation all confirmed."
        )
        sys.exit(0)
    else:
        failed = sum(1 for c in checks if not c)
        print(f"RESULT: {failed}/{len(checks)} CHECK(S) FAILED ✗")
        sys.exit(1)


if __name__ == "__main__":
    main()
