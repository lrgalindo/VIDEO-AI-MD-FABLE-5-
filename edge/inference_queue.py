"""Local SQLite inference queue with exponential backoff and FIFO eviction (SDD §4).

Every inference result is written to the queue *before* the cloud send is attempted.
The cloud send is best-effort; on failure, the item stays in the queue and is retried
with exponential backoff. Items older than QUEUE_RETENTION_DAYS are evicted FIFO
(oldest-first) to bound disk usage.

Schema
------
  inference_queue(
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    payload         TEXT    NOT NULL,        -- JSON string
    created_at      REAL    NOT NULL,        -- unix timestamp
    attempts        INTEGER NOT NULL DEFAULT 0,
    next_attempt_at REAL    NOT NULL         -- unix timestamp
  )
"""

import json
import logging
import math
import sqlite3
import time
from contextlib import contextmanager
from typing import Any, Callable, Generator

from edge import config

log = logging.getLogger(__name__)

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS inference_queue (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    payload         TEXT    NOT NULL,
    created_at      REAL    NOT NULL,
    attempts        INTEGER NOT NULL DEFAULT 0,
    next_attempt_at REAL    NOT NULL
)
"""


class InferenceQueue:
    def __init__(
        self,
        db_path: str = config.QUEUE_DB,
        retention_days: int = config.QUEUE_RETENTION_DAYS,
        backoff_base: float = config.BACKOFF_BASE_SECONDS,
        backoff_max: float = config.BACKOFF_MAX_SECONDS,
    ) -> None:
        self._db = db_path
        self._retention = retention_days * 86_400
        self._backoff_base = backoff_base
        self._backoff_max = backoff_max
        self._init_db()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def enqueue(self, payload: dict) -> int:
        """Persist an inference result. Returns the new row id.

        Always called *before* the cloud send attempt so no result is ever lost.
        """
        now = time.time()
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO inference_queue (payload, created_at, next_attempt_at) VALUES (?, ?, ?)",
                [json.dumps(payload), now, now],
            )
            return cur.lastrowid  # type: ignore[return-value]

    def flush(
        self,
        send_fn: Callable[[dict], None],
        *,
        limit: int = 100,
    ) -> tuple[int, int]:
        """Attempt to send pending items via send_fn.

        Items whose next_attempt_at is in the future are skipped.
        On send_fn success: delete the item.
        On send_fn failure: increment attempts and schedule next retry with
          exponential backoff capped at backoff_max.

        Returns (sent_count, failed_count).
        """
        self._evict_old()
        now = time.time()
        sent = failed = 0

        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT id, payload, attempts
                  FROM inference_queue
                 WHERE next_attempt_at <= ?
                 ORDER BY created_at
                 LIMIT ?
                """,
                [now, limit],
            ).fetchall()

        for row_id, payload_json, attempts in rows:
            payload = json.loads(payload_json)
            try:
                send_fn(payload)
                with self._conn() as conn:
                    conn.execute("DELETE FROM inference_queue WHERE id = ?", [row_id])
                sent += 1
            except Exception as exc:
                delay = min(self._backoff_base * (2 ** attempts), self._backoff_max)
                next_at = time.time() + delay
                with self._conn() as conn:
                    conn.execute(
                        "UPDATE inference_queue SET attempts = ?, next_attempt_at = ? WHERE id = ?",
                        [attempts + 1, next_at, row_id],
                    )
                log.warning("Send failed (attempt %d, retry in %.0fs): %s", attempts + 1, delay, exc)
                failed += 1

        return sent, failed

    def pending_count(self) -> int:
        with self._conn() as conn:
            return conn.execute("SELECT count(*) FROM inference_queue").fetchone()[0]

    def evict_now(self) -> int:
        """Delete items older than retention_days. Returns evicted count."""
        return self._evict_old()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.execute(_CREATE_TABLE)

    def _evict_old(self) -> int:
        cutoff = time.time() - self._retention
        with self._conn() as conn:
            cur = conn.execute(
                "DELETE FROM inference_queue WHERE created_at < ?", [cutoff]
            )
            count = cur.rowcount
        if count:
            log.info("Evicted %d item(s) older than %d days", count, self._retention // 86_400)
        return count

    @contextmanager
    def _conn(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(self._db, timeout=5)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
