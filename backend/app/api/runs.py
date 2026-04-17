from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import CheckRun
from ..schemas import CheckRunOut, PageOut
from ..security import get_current_user


router = APIRouter(prefix="/runs", tags=["runs"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=PageOut[CheckRunOut])
def list_runs(
    check_id: int | None = None,
    status: str | None = None,
    run_mode: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    query = db.query(CheckRun).order_by(CheckRun.id.desc())
    if check_id is not None:
        query = query.filter(CheckRun.check_id == check_id)
    if status:
        query = query.filter(CheckRun.status == status)
    if run_mode:
        query = query.filter(CheckRun.run_mode == run_mode)
    if limit != 100 and page == 1:
        page_size = limit
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return {"items": items, "total": total, "page": page, "page_size": page_size}
