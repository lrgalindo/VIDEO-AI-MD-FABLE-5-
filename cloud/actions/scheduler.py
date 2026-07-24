"""Action Engine scheduler — same cadence as Motor Matemático batch cycle.

Runs evaluate_rule() for all enabled rules once per CHECK_INTERVAL_SECONDS.
Daemonized thread — same pattern as backoffice/scheduler.py.

Horizontal scaling note: same caveat as the revocation scheduler applies —
multiple replicas each run the full evaluation cycle.  Rule triggers are
idempotent (the action_log INSERT has no UNIQUE constraint so duplicates are
possible at scale).  Mitigation: pg_cron or Cloud Scheduler for production.
This does not block MLP with a single instance.
"""

import logging
import threading
import time

from cloud.actions.engine import run_evaluation_cycle

log = logging.getLogger(__name__)

CHECK_INTERVAL_SECONDS: int = 60  # 1-5 min configurable; matches Motor Matemático cadence


def start_action_engine_scheduler() -> None:
    def _loop() -> None:
        log.info("Action Engine scheduler started (interval=%ds)", CHECK_INTERVAL_SECONDS)
        while True:
            time.sleep(CHECK_INTERVAL_SECONDS)
            try:
                run_evaluation_cycle()
            except Exception as exc:
                log.error("Action Engine cycle error: %s", exc)

    t = threading.Thread(target=_loop, daemon=True, name="action-engine")
    t.start()
