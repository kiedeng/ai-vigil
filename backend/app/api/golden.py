from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..models import GoldenCase, GoldenRun, GoldenSet
from ..schemas import (
    GoldenCaseCreate,
    GoldenCaseOut,
    GoldenCaseUpdate,
    GoldenRunOut,
    GoldenSetCreate,
    GoldenSetDetail,
    GoldenSetOut,
    GoldenSetUpdate,
)
from ..security import get_current_user
from ..services.golden import run_golden_case, run_golden_set


router = APIRouter(prefix="/golden-sets", tags=["golden-sets"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[GoldenSetOut])
def list_sets(db: Session = Depends(get_db)) -> list[GoldenSet]:
    return db.query(GoldenSet).order_by(GoldenSet.id.desc()).all()


@router.post("", response_model=GoldenSetOut, status_code=status.HTTP_201_CREATED)
def create_set(payload: GoldenSetCreate, db: Session = Depends(get_db)) -> GoldenSet:
    row = GoldenSet(**payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.get("/{set_id}", response_model=GoldenSetDetail)
def get_set(set_id: int, db: Session = Depends(get_db)) -> GoldenSet:
    row = db.query(GoldenSet).options(joinedload(GoldenSet.cases)).filter(GoldenSet.id == set_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Golden set not found")
    return row


@router.put("/{set_id}", response_model=GoldenSetOut)
def update_set(set_id: int, payload: GoldenSetUpdate, db: Session = Depends(get_db)) -> GoldenSet:
    row = db.query(GoldenSet).filter(GoldenSet.id == set_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Golden set not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, key, value)
    db.commit()
    db.refresh(row)
    return row


@router.delete("/{set_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_set(set_id: int, db: Session = Depends(get_db)) -> None:
    row = db.query(GoldenSet).filter(GoldenSet.id == set_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Golden set not found")
    db.delete(row)
    db.commit()


@router.post("/{set_id}/cases", response_model=GoldenCaseOut, status_code=status.HTTP_201_CREATED)
def create_case(set_id: int, payload: GoldenCaseCreate, db: Session = Depends(get_db)) -> GoldenCase:
    if not db.query(GoldenSet.id).filter(GoldenSet.id == set_id).first():
        raise HTTPException(status_code=404, detail="Golden set not found")
    row = GoldenCase(golden_set_id=set_id, **payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.put("/{set_id}/cases/{case_id}", response_model=GoldenCaseOut)
def update_case(set_id: int, case_id: int, payload: GoldenCaseUpdate, db: Session = Depends(get_db)) -> GoldenCase:
    row = db.query(GoldenCase).filter(GoldenCase.id == case_id, GoldenCase.golden_set_id == set_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Golden case not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, key, value)
    db.commit()
    db.refresh(row)
    return row


@router.delete("/{set_id}/cases/{case_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_case(set_id: int, case_id: int, db: Session = Depends(get_db)) -> None:
    row = db.query(GoldenCase).filter(GoldenCase.id == case_id, GoldenCase.golden_set_id == set_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Golden case not found")
    db.delete(row)
    db.commit()


@router.post("/{set_id}/run", response_model=list[GoldenRunOut])
async def run_set(set_id: int, db: Session = Depends(get_db)) -> list[GoldenRun]:
    row = db.query(GoldenSet).options(joinedload(GoldenSet.cases)).filter(GoldenSet.id == set_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Golden set not found")
    return await run_golden_set(db, row)


@router.post("/{set_id}/cases/{case_id}/run", response_model=GoldenRunOut)
async def run_case(set_id: int, case_id: int, db: Session = Depends(get_db)) -> GoldenRun:
    golden_set = db.query(GoldenSet).filter(GoldenSet.id == set_id).first()
    case = db.query(GoldenCase).filter(GoldenCase.id == case_id, GoldenCase.golden_set_id == set_id).first()
    if not golden_set or not case:
        raise HTTPException(status_code=404, detail="Golden case not found")
    return await run_golden_case(db, golden_set, case)


@router.get("/{set_id}/runs", response_model=list[GoldenRunOut])
def list_runs(set_id: int, db: Session = Depends(get_db)) -> list[GoldenRun]:
    return db.query(GoldenRun).filter(GoldenRun.golden_set_id == set_id).order_by(GoldenRun.id.desc()).limit(200).all()

