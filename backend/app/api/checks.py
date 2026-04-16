from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..models import Check, CheckRun
from ..schemas import CheckCreate, CheckOut, CheckRunOut, CheckUpdate
from ..security import get_current_user
from ..services.check_runner import run_check_once


router = APIRouter(prefix="/checks", tags=["checks"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[CheckOut])
def list_checks(
    type: str | None = None,
    enabled: bool | None = None,
    db: Session = Depends(get_db),
) -> list[Check]:
    query = db.query(Check).options(joinedload(Check.state)).order_by(Check.id.desc())
    if type:
        query = query.filter(Check.type == type)
    if enabled is not None:
        query = query.filter(Check.enabled.is_(enabled))
    return query.all()


@router.post("", response_model=CheckOut, status_code=status.HTTP_201_CREATED)
def create_check(payload: CheckCreate, db: Session = Depends(get_db)) -> Check:
    check = Check(**payload.model_dump())
    db.add(check)
    db.commit()
    db.refresh(check)
    return check


@router.get("/{check_id}", response_model=CheckOut)
def get_check(check_id: int, db: Session = Depends(get_db)) -> Check:
    check = db.query(Check).options(joinedload(Check.state)).filter(Check.id == check_id).first()
    if not check:
        raise HTTPException(status_code=404, detail="Check not found")
    return check


@router.put("/{check_id}", response_model=CheckOut)
def update_check(check_id: int, payload: CheckUpdate, db: Session = Depends(get_db)) -> Check:
    check = db.query(Check).filter(Check.id == check_id).first()
    if not check:
        raise HTTPException(status_code=404, detail="Check not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(check, key, value)
    db.commit()
    db.refresh(check)
    return check


@router.delete("/{check_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_check(check_id: int, db: Session = Depends(get_db)) -> None:
    check = db.query(Check).filter(Check.id == check_id).first()
    if not check:
        raise HTTPException(status_code=404, detail="Check not found")
    db.delete(check)
    db.commit()


@router.post("/{check_id}/run", response_model=CheckRunOut)
async def run_check(check_id: int, db: Session = Depends(get_db)) -> CheckRun:
    check = db.query(Check).options(joinedload(Check.state)).filter(Check.id == check_id).first()
    if not check:
        raise HTTPException(status_code=404, detail="Check not found")
    return await run_check_once(db, check)


@router.get("/{check_id}/runs", response_model=list[CheckRunOut])
def list_check_runs(
    check_id: int,
    status: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[CheckRun]:
    if not db.query(Check.id).filter(Check.id == check_id).first():
        raise HTTPException(status_code=404, detail="Check not found")
    query = db.query(CheckRun).filter(CheckRun.check_id == check_id).order_by(CheckRun.id.desc())
    if status:
        query = query.filter(CheckRun.status == status)
    return query.limit(limit).all()

