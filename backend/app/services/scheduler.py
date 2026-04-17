from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import logging

from apscheduler.schedulers.background import BackgroundScheduler

from ..config import get_settings
from ..database import SessionLocal
from ..models import Check
from .check_runner import run_check_once
from .daily_report import send_daily_report
from .settings import effective_settings


logger = logging.getLogger(__name__)
_scheduler: BackgroundScheduler | None = None


def _is_due(check: Check) -> bool:
    if check.state is None or check.state.last_run_id is None:
        return True
    last_at = check.state.updated_at
    return datetime.utcnow() - last_at >= timedelta(seconds=check.interval_seconds)


def run_due_checks() -> None:
    db = SessionLocal()
    try:
        checks = db.query(Check).filter(Check.enabled.is_(True)).all()
        for check in checks:
            if not _is_due(check):
                continue
            try:
                asyncio.run(run_check_once(db, check, run_mode="scheduled", notify=True))
            except Exception:
                logger.exception("Scheduled check failed: %s", check.id)
    finally:
        db.close()


def run_daily_report() -> None:
    db = SessionLocal()
    try:
        settings = effective_settings(db)
        if not settings.get("daily_report_enabled", True):
            return
        asyncio.run(send_daily_report(db))
    except Exception:
        logger.exception("Daily report failed")
    finally:
        db.close()


def start_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        return
    settings = get_settings()
    _scheduler = BackgroundScheduler(timezone="Asia/Shanghai")
    _scheduler.add_job(
        run_due_checks,
        "interval",
        seconds=settings.scheduler_poll_seconds,
        id="run_due_checks",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    db = SessionLocal()
    try:
        app_settings = effective_settings(db)
        report_hour = int(app_settings.get("daily_report_hour", 9))
        report_minute = int(app_settings.get("daily_report_minute", 0))
    finally:
        db.close()
    _scheduler.add_job(
        run_daily_report,
        "cron",
        hour=report_hour,
        minute=report_minute,
        id="daily_report",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    _scheduler.start()


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
    _scheduler = None
