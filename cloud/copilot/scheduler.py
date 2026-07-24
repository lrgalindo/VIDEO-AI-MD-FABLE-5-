"""Stock audit scheduler — runs run_stock_audit_cycle() every AUDIT_INTERVAL_SECONDS.

Multi-replica note: same in-process daemon-thread limit as backoffice/scheduler.py —
multiple replicas will each run a cycle independently (no distributed lock). Acceptable
for MLP; see that file for the full reasoning.
"""

import logging
import threading
import time

from cloud import config
from cloud.copilot.audit import run_stock_audit_cycle

log = logging.getLogger(__name__)

# Same cadence as action engine; offset by 30s so both don't slam DB simultaneously
AUDIT_INTERVAL_SECONDS = 60


def _audit_loop() -> None:
    while True:
        time.sleep(AUDIT_INTERVAL_SECONDS)
        try:
            run_stock_audit_cycle()
        except Exception as exc:
            log.error("Stock audit cycle error: %s", exc)


def start_audit_scheduler() -> None:
    if not config.ANTHROPIC_API_KEY:
        log.info("Stock audit scheduler not started — ANTHROPIC_API_KEY not set")
        return
    t = threading.Thread(target=_audit_loop, daemon=True, name="stock-audit-scheduler")
    t.start()
    log.info("Stock audit scheduler started (interval=%ss)", AUDIT_INTERVAL_SECONDS)
