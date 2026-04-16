from __future__ import annotations

from datetime import datetime, timedelta
from statistics import quantiles
from typing import Any

from sqlalchemy.orm import Session

from ..models import CheckRun, CheckState, GoldenRun


def _percentile(values: list[int], percentile: int) -> float | None:
    if not values:
        return None
    if len(values) == 1:
        return float(values[0])
    ordered = sorted(values)
    index = round((percentile / 100) * (len(ordered) - 1))
    return float(ordered[index])


def _bucket(db: Session, label: str, delta: timedelta) -> dict[str, Any]:
    since = datetime.utcnow() - delta
    rows = db.query(CheckRun).filter(CheckRun.created_at >= since).all()
    total = len(rows)
    success = sum(1 for row in rows if row.status == "success")
    failure = total - success
    latencies = [row.duration_ms for row in rows if row.duration_ms is not None]
    return {
        "label": label,
        "total": total,
        "success": success,
        "failure": failure,
        "availability": round((success / total) * 100, 2) if total else 0.0,
        "error_rate": round((failure / total) * 100, 2) if total else 0.0,
        "p50_ms": _percentile(latencies, 50),
        "p90_ms": _percentile(latencies, 90),
        "p95_ms": _percentile(latencies, 95),
        "p99_ms": _percentile(latencies, 99),
    }


def trend_summary(db: Session) -> dict[str, Any]:
    golden_total = db.query(GoldenRun).count()
    golden_success = db.query(GoldenRun).filter(GoldenRun.status == "success").count()
    current_failures = (
        db.query(CheckState)
        .filter(CheckState.status == "failure")
        .order_by(CheckState.consecutive_failures.desc())
        .limit(20)
        .all()
    )
    return {
        "windows": {
            "1h": _bucket(db, "1h", timedelta(hours=1)),
            "24h": _bucket(db, "24h", timedelta(hours=24)),
            "7d": _bucket(db, "7d", timedelta(days=7)),
        },
        "current_failures": [
            {
                "check_id": state.check_id,
                "status": state.status,
                "consecutive_failures": state.consecutive_failures,
                "last_failure_at": state.last_failure_at,
            }
            for state in current_failures
        ],
        "golden": {
            "total": golden_total,
            "success": golden_success,
            "failure": golden_total - golden_success,
            "pass_rate": round((golden_success / golden_total) * 100, 2) if golden_total else 0.0,
        },
    }

