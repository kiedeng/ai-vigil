from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas import TrendSummary
from ..security import get_current_user
from ..services.analytics import trend_summary


router = APIRouter(prefix="/analytics", tags=["analytics"], dependencies=[Depends(get_current_user)])


@router.get("/trends", response_model=TrendSummary)
def trends(db: Session = Depends(get_db)):
    return trend_summary(db)

