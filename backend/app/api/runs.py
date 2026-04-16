from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import CheckRun
from ..schemas import CheckRunOut
from ..security import get_current_user


router = APIRouter(prefix="/runs", tags=["runs"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[CheckRunOut])
def list_runs(
    check_id: int | None = None,
    status: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[CheckRun]:
    query = db.query(CheckRun).order_by(CheckRun.id.desc())
    if check_id is not None:
        query = query.filter(CheckRun.check_id == check_id)
    if status:
        query = query.filter(CheckRun.status == status)
    return query.limit(limit).all()

