from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import AlertEvent, Check, CheckRun, CheckState, NewApiModel
from ..schemas import DashboardSummary
from ..security import get_current_user


router = APIRouter(prefix="/dashboard", tags=["dashboard"], dependencies=[Depends(get_current_user)])


@router.get("/summary", response_model=DashboardSummary)
def summary(db: Session = Depends(get_db)) -> DashboardSummary:
    total = db.query(Check).count()
    enabled = db.query(Check).filter(Check.enabled.is_(True)).count()
    healthy = db.query(CheckState).filter(CheckState.status == "success").count()
    failing = db.query(CheckState).filter(CheckState.status == "failure").count()
    unknown = max(total - healthy - failing, 0)
    known = healthy + failing
    availability = round((healthy / known) * 100, 2) if known else 0.0
    model_total = db.query(NewApiModel).count()
    model_unmatched = db.query(NewApiModel).filter(NewApiModel.category == "unmatched").count()
    recent_runs = db.query(CheckRun).order_by(CheckRun.id.desc()).limit(10).all()
    recent_alerts = db.query(AlertEvent).order_by(AlertEvent.id.desc()).limit(10).all()
    return DashboardSummary(
        total_checks=total,
        enabled_checks=enabled,
        healthy_checks=healthy,
        failing_checks=failing,
        unknown_checks=unknown,
        availability=availability,
        model_total=model_total,
        model_unmatched=model_unmatched,
        recent_runs=recent_runs,
        recent_alerts=recent_alerts,
    )

