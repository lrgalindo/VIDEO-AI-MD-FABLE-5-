"""Tests for InferenceQueue: enqueue-before-send, backoff, eviction, cloud-outage recovery.

All tests use an in-memory or temp-file SQLite DB — no real cloud connection needed.
"""

import time
from pathlib import Path
from typing import Callable

import pytest

from edge.inference_queue import InferenceQueue


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PAYLOAD = {"camera_id": "cam-001", "person_id": "p001", "x": 50, "y": 60, "t": 1234567890.0}


def _make_queue(tmp_queue_db: str, **kwargs: object) -> InferenceQueue:
    return InferenceQueue(
        db_path=tmp_queue_db,
        retention_days=kwargs.get("retention_days", 7),  # type: ignore[arg-type]
        backoff_base=kwargs.get("backoff_base", 0.01),   # fast for tests
        backoff_max=kwargs.get("backoff_max", 1.0),
    )


# ---------------------------------------------------------------------------
# (d-1) Enqueue before send — item persists on failure
# ---------------------------------------------------------------------------

def test_enqueue_persists_payload(tmp_queue_db: str) -> None:
    """Enqueued item is stored before any send is attempted."""
    q = _make_queue(tmp_queue_db)
    row_id = q.enqueue(_PAYLOAD)
    assert row_id is not None and row_id > 0
    assert q.pending_count() == 1


def test_item_present_even_when_cloud_is_down(tmp_queue_db: str) -> None:
    """Item stays in queue after a send failure — zero data loss."""
    q = _make_queue(tmp_queue_db)
    q.enqueue(_PAYLOAD)

    def cloud_down(payload: dict) -> None:
        raise ConnectionError("cloud is down")

    sent, failed = q.flush(cloud_down)
    assert sent == 0
    assert failed == 1
    assert q.pending_count() == 1, "Item must still be in queue after failed send"


# ---------------------------------------------------------------------------
# (d-2) Cloud outage → recovery with zero data loss
# ---------------------------------------------------------------------------

def test_zero_data_loss_after_outage_recovery(tmp_queue_db: str) -> None:
    """Items enqueued during a simulated outage are all sent on recovery.

    Scenario:
    1. Enqueue 5 items.
    2. Cloud is down — flush fails, all 5 remain in queue.
    3. Cloud recovers — flush succeeds, 0 items remain.
    """
    q = _make_queue(tmp_queue_db, backoff_base=0.0, backoff_max=0.0)
    payloads = [{"id": i, **_PAYLOAD} for i in range(5)]
    for p in payloads:
        q.enqueue(p)
    assert q.pending_count() == 5

    received: list[dict] = []

    def cloud_down(payload: dict) -> None:
        raise ConnectionError("outage")

    # --- Outage ---
    sent, failed = q.flush(cloud_down)
    assert sent == 0 and failed == 5
    assert q.pending_count() == 5

    def cloud_up(payload: dict) -> None:
        received.append(payload)

    # Backoff delay is 0 in this test, so items are immediately eligible for retry
    sent, failed = q.flush(cloud_up)
    assert failed == 0
    assert sent == 5
    assert q.pending_count() == 0

    ids_sent = {r["id"] for r in received}
    ids_original = {p["id"] for p in payloads}
    assert ids_sent == ids_original, "All enqueued payloads must be delivered exactly once"


# ---------------------------------------------------------------------------
# (d-3) Exponential backoff
# ---------------------------------------------------------------------------

def test_exponential_backoff_grows(tmp_queue_db: str) -> None:
    """After each failure, next_attempt_at grows by 2^attempts × base seconds."""
    q = _make_queue(tmp_queue_db, backoff_base=1.0, backoff_max=100.0)
    q.enqueue(_PAYLOAD)

    import sqlite3
    conn = sqlite3.connect(tmp_queue_db)

    def cloud_down(_: dict) -> None:
        raise Exception("down")

    delays: list[float] = []
    prev_next_at = time.time()

    for _ in range(4):
        # Force next_attempt_at to now so flush processes the item
        conn.execute("UPDATE inference_queue SET next_attempt_at = ?", [time.time() - 0.01])
        conn.commit()

        before = time.time()
        q.flush(cloud_down)
        next_at = conn.execute("SELECT next_attempt_at FROM inference_queue").fetchone()[0]
        delay = next_at - before
        delays.append(delay)

    conn.close()

    # Delays should roughly double: ~1s, ~2s, ~4s, ~8s
    for i in range(1, len(delays)):
        assert delays[i] >= delays[i - 1] * 1.5, (
            f"Backoff should roughly double: {delays}"
        )


def test_backoff_capped_at_max(tmp_queue_db: str) -> None:
    """Backoff must not exceed backoff_max."""
    q = _make_queue(tmp_queue_db, backoff_base=1.0, backoff_max=5.0)
    q.enqueue(_PAYLOAD)

    import sqlite3
    conn = sqlite3.connect(tmp_queue_db)

    def cloud_down(_: dict) -> None:
        raise Exception("down")

    for _ in range(10):
        conn.execute("UPDATE inference_queue SET next_attempt_at = ?", [time.time() - 0.01])
        conn.commit()
        q.flush(cloud_down)

    before = time.time()
    next_at = conn.execute("SELECT next_attempt_at FROM inference_queue").fetchone()[0]
    conn.close()

    assert next_at - before <= 5.5, "next_attempt_at must not exceed backoff_max + small epsilon"


# ---------------------------------------------------------------------------
# (d-4) FIFO eviction at 7 days
# ---------------------------------------------------------------------------

def test_eviction_removes_old_items(tmp_queue_db: str) -> None:
    """Items older than retention_days are evicted FIFO (oldest first)."""
    q = _make_queue(tmp_queue_db, retention_days=1)  # 1-day retention for speed

    import sqlite3
    conn = sqlite3.connect(tmp_queue_db)

    # Insert an item with created_at 25 hours ago (past retention)
    old_ts = time.time() - 25 * 3600
    conn.execute(
        "INSERT INTO inference_queue (payload, created_at, next_attempt_at) VALUES (?, ?, ?)",
        ['{"old": true}', old_ts, old_ts],
    )
    # Insert a fresh item
    fresh_ts = time.time()
    conn.execute(
        "INSERT INTO inference_queue (payload, created_at, next_attempt_at) VALUES (?, ?, ?)",
        ['{"fresh": true}', fresh_ts, fresh_ts],
    )
    conn.commit()
    conn.close()

    evicted = q.evict_now()
    assert evicted == 1, f"Expected 1 evicted item, got {evicted}"
    assert q.pending_count() == 1, "Fresh item must survive eviction"


def test_eviction_is_fifo(tmp_queue_db: str) -> None:
    """When multiple old items exist, they are all evicted; newer ones survive."""
    q = _make_queue(tmp_queue_db, retention_days=1)

    import sqlite3
    conn = sqlite3.connect(tmp_queue_db)
    now = time.time()
    for i in range(3):
        old_ts = now - (25 + i) * 3600
        conn.execute(
            "INSERT INTO inference_queue (payload, created_at, next_attempt_at) VALUES (?, ?, ?)",
            [f'{{"i": {i}}}', old_ts, old_ts],
        )
    # Two fresh items
    for j in range(2):
        conn.execute(
            "INSERT INTO inference_queue (payload, created_at, next_attempt_at) VALUES (?, ?, ?)",
            [f'{{"j": {j}}}', now, now],
        )
    conn.commit()
    conn.close()

    evicted = q.evict_now()
    assert evicted == 3
    assert q.pending_count() == 2


# ---------------------------------------------------------------------------
# (d-5) Poison-pill: permanently-failing item does not block healthy items
# ---------------------------------------------------------------------------

def test_poison_pill_does_not_block_healthy_items(tmp_queue_db: str) -> None:
    """A permanently-failing item at the front of the queue must not block items
    behind it from being sent on the same flush() call.

    Scenario:
    - Item A (oldest, created_at T+0): always fails to send — permanent poison pill.
    - Items B, C (created_at T+1, T+2): send successfully.

    Expectation after one flush():
    - A remains in queue with incremented backoff.
    - B and C are deleted (sent successfully).
    - Total pending count = 1 (only A remains).

    This verifies that flush() does not abort on the first failure; it processes
    all items eligible for this cycle and reports (sent, failed) independently.
    """
    q = _make_queue(tmp_queue_db, backoff_base=0.0, backoff_max=0.0)

    import sqlite3
    conn = sqlite3.connect(tmp_queue_db)
    now = time.time()

    # Poison pill is the oldest item (lowest created_at, processed first by FIFO)
    conn.execute(
        "INSERT INTO inference_queue (payload, created_at, next_attempt_at) VALUES (?, ?, ?)",
        ['{"poison": true}', now, now - 1],
    )
    # Two healthy items behind it
    for i in range(2):
        conn.execute(
            "INSERT INTO inference_queue (payload, created_at, next_attempt_at) VALUES (?, ?, ?)",
            [f'{{"healthy": {i}}}', now + i + 1, now - 1],
        )
    conn.commit()
    conn.close()

    received: list[dict] = []

    def send_fn(payload: dict) -> None:
        if payload.get("poison"):
            raise RuntimeError("this item will never succeed")
        received.append(payload)

    sent, failed = q.flush(send_fn)

    assert failed == 1, "Poison pill counted as 1 failure"
    assert sent == 2, "Both healthy items behind the poison pill were sent"
    assert q.pending_count() == 1, "Only the poison pill remains in the queue"
    assert len(received) == 2 and all("healthy" in r for r in received), (
        "Only healthy payloads were delivered — poison pill never reached the cloud"
    )


# ---------------------------------------------------------------------------
# (d-6) Ordering: FIFO send (oldest item sent first)
# ---------------------------------------------------------------------------

def test_flush_sends_oldest_first(tmp_queue_db: str) -> None:
    """flush() processes items in created_at order (FIFO)."""
    q = _make_queue(tmp_queue_db, backoff_base=0.0, backoff_max=0.0)

    import sqlite3
    conn = sqlite3.connect(tmp_queue_db)
    now = time.time()
    for i in range(3):
        conn.execute(
            "INSERT INTO inference_queue (payload, created_at, next_attempt_at) VALUES (?, ?, ?)",
            [f'{{"seq": {i}}}', now + i, now - 1],
        )
    conn.commit()
    conn.close()

    received: list[dict] = []
    q.flush(received.append)

    seqs = [r["seq"] for r in received]
    assert seqs == sorted(seqs), f"Expected FIFO order, got {seqs}"
