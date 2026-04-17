from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import String, cast, or_
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..models import Check, CheckRun, CheckState
from ..schemas import CheckCreate, CheckOut, CheckRunOut, CheckUpdate, PageOut
from ..security import get_current_user
from ..services.check_runner import run_check_once


router = APIRouter(prefix="/checks", tags=["checks"], dependencies=[Depends(get_current_user)])


def _category_types(category: str | None) -> set[str] | None:
    mapping = {
        "model": {"model_llm_chat", "model_llm_completion", "model_embedding", "model_rerank", "model_moderation"},
        "http": {"http_health", "model_custom_http"},
        "ai": {"http_content_ai"},
        "audio": {"model_audio_transcription", "model_audio_translation", "model_audio_speech"},
        "image": {"model_vision_chat", "model_image_generation", "model_image_edit"},
    }
    return mapping.get(category or "")


@router.get("", response_model=PageOut[CheckOut])
def list_checks(
    type: str | None = None,
    enabled: bool | None = None,
    status: str | None = None,
    instance_id: int | None = None,
    category: str | None = None,
    search: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    query = db.query(Check).options(joinedload(Check.state)).order_by(Check.id.desc())
    if type:
        query = query.filter(Check.type == type)
    if enabled is not None:
        query = query.filter(Check.enabled.is_(enabled))
    if status:
        query = query.join(CheckState, CheckState.check_id == Check.id).filter(CheckState.status == status)
    if instance_id is not None:
        query = query.filter(Check.new_api_instance_id == instance_id)
    if category_types := _category_types(category):
        query = query.filter(Check.type.in_(category_types))
    if search:
        like = f"%{search}%"
        query = query.filter(
            or_(
                Check.name.like(like),
                Check.model_name.like(like),
                cast(Check.request_config, String).like(like),
            )
        )
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return {"items": items, "total": total, "page": page, "page_size": page_size}


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
    return await run_check_once(db, check, run_mode="manual", notify=True)


@router.post("/{check_id}/test-run", response_model=CheckRunOut)
async def test_run_check(check_id: int, db: Session = Depends(get_db)) -> CheckRun:
    check = db.query(Check).options(joinedload(Check.state)).filter(Check.id == check_id).first()
    if not check:
        raise HTTPException(status_code=404, detail="Check not found")
    return await run_check_once(db, check, run_mode="test", notify=False)


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
