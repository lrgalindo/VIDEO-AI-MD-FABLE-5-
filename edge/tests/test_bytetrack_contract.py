"""CI regression guard: verifies that _yolo_detections() calls model.track()
with tracker="bytetrack.yaml" and persist=True — not a plain model() call.

This test is cheap (no ultralytics/PyTorch needed — model is fully mocked) and
runs in the fast per-commit suite alongside the other edge/ tests.

Background: the original implementation called model(frame) which does detection
only — box.id was always None, ByteTrack was never engaged, and every detection
got a fresh ID on every frame. This broke dwell-time continuity silently (no test
caught it because the smoke-test suite uses STUB mode). The fix changed the call
to model.track(persist=True, tracker="bytetrack.yaml"). This test ensures that
change cannot be reverted accidentally.
"""

from unittest.mock import MagicMock, call
import numpy as np


def _make_mock_model(n_persons: int = 2) -> MagicMock:
    """Return a mock YOLO model whose .track() returns n person boxes with stable IDs."""
    box_mocks = []
    for i in range(n_persons):
        box = MagicMock()
        box.cls = MagicMock()
        box.cls.__getitem__ = lambda self, k: MagicMock(__int__=lambda s: 0)  # person
        box.conf = MagicMock()
        box.conf.__getitem__ = lambda self, k: MagicMock(__float__=lambda s: 0.85)
        box.xyxy = MagicMock()
        box.xyxy.__getitem__ = lambda self, k: MagicMock(tolist=lambda: [10.0, 20.0, 50.0, 80.0])
        box.id = MagicMock()
        box.id.__getitem__ = lambda self, k: MagicMock(__int__=lambda s: i + 1)
        box_mocks.append(box)

    result = MagicMock()
    result.boxes = box_mocks

    model = MagicMock()
    model.track.return_value = [result]
    return model


def test_yolo_detections_uses_track_not_call() -> None:
    """_yolo_detections must call model.track(), not model().

    If model() were called instead, model.track would not be invoked and this
    test would fail on the assert_called_once_with check.
    """
    import numpy as np
    from edge.gateway import _yolo_detections

    model = _make_mock_model(n_persons=2)
    frame = np.zeros((240, 320, 3), dtype=np.uint8)

    result = _yolo_detections(frame, model)

    # model.track() must have been called — not model()
    model.track.assert_called_once()
    model.assert_not_called()  # plain model(frame) must NOT have been invoked


def test_bytetrack_tracker_config_is_explicit() -> None:
    """model.track() must be called with tracker='bytetrack.yaml'.

    Omitting tracker= defaults to BoT-SORT in some ultralytics versions.
    Explicit tracker='bytetrack.yaml' matches the architecture spec (SDD §7.2).
    """
    from edge.gateway import _yolo_detections

    model = _make_mock_model()
    frame = np.zeros((240, 320, 3), dtype=np.uint8)

    _yolo_detections(frame, model)

    _call = model.track.call_args
    assert _call is not None, "model.track() was not called"
    kwargs = _call.kwargs if _call.kwargs else {}
    positional = _call.args if _call.args else ()

    tracker_arg = kwargs.get("tracker")
    assert tracker_arg == "bytetrack.yaml", (
        f"Expected tracker='bytetrack.yaml', got {tracker_arg!r}. "
        "Reverting to model() or changing tracker= would break dwell-time continuity."
    )


def test_persist_true_is_set() -> None:
    """model.track() must be called with persist=True.

    persist=False resets ByteTrack state on every call — each frame would produce
    fresh IDs, making dwell-time continuity impossible.
    """
    from edge.gateway import _yolo_detections

    model = _make_mock_model()
    frame = np.zeros((240, 320, 3), dtype=np.uint8)

    _yolo_detections(frame, model)

    _call = model.track.call_args
    kwargs = _call.kwargs if _call.kwargs else {}
    persist = kwargs.get("persist")

    assert persist is True, (
        f"Expected persist=True, got {persist!r}. "
        "Without persist=True, ByteTrack loses state between frames."
    )


def test_person_class_filter_applied() -> None:
    """Only class-0 (person) detections must be returned, not all classes."""
    from edge.gateway import _yolo_detections

    # Build a model that returns 1 person (cls=0) and 1 bus (cls=5)
    person_box = MagicMock()
    person_box.cls.__getitem__ = lambda self, k: MagicMock(__int__=lambda s: 0)
    person_box.conf.__getitem__ = lambda self, k: MagicMock(__float__=lambda s: 0.9)
    person_box.xyxy.__getitem__ = lambda self, k: MagicMock(tolist=lambda: [10.0, 20.0, 50.0, 80.0])
    person_box.id.__getitem__ = lambda self, k: MagicMock(__int__=lambda s: 1)

    bus_box = MagicMock()
    bus_box.cls.__getitem__ = lambda self, k: MagicMock(__int__=lambda s: 5)  # bus
    bus_box.conf.__getitem__ = lambda self, k: MagicMock(__float__=lambda s: 0.9)
    bus_box.xyxy.__getitem__ = lambda self, k: MagicMock(tolist=lambda: [0.0, 0.0, 100.0, 100.0])
    bus_box.id.__getitem__ = lambda self, k: MagicMock(__int__=lambda s: 2)

    result = MagicMock()
    result.boxes = [person_box, bus_box]
    model = MagicMock()
    model.track.return_value = [result]

    frame = np.zeros((240, 320, 3), dtype=np.uint8)
    detections = _yolo_detections(frame, model)

    # Only the person detection should be returned
    assert len(detections) == 1, (
        f"Expected 1 detection (person only), got {len(detections)}: {detections}"
    )
    assert detections[0]["person_id"] == "track-001"
