"""Standalone polling worker for durable scheduled analytics jobs."""

from __future__ import annotations

import logging
import os
import time

from backend.api.dependencies import get_automation_service


_log = logging.getLogger(__name__)


def run_worker() -> None:
    interval = max(1, int(os.getenv("AUTOMATION_POLL_SECONDS", "15")))
    service = get_automation_service()
    _log.info("automation_worker_started poll_seconds=%s", interval)
    while True:
        try:
            queued = service.enqueue_due_automations()
            processed = service.process_pending_runs()
            if queued or processed:
                _log.info("automation_worker_cycle queued=%s processed=%s", queued, processed)
        except Exception:
            _log.exception("automation_worker_cycle_failed")
        time.sleep(interval)


if __name__ == "__main__":
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    run_worker()