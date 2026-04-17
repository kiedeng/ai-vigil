from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..models import NewApiInstance, NewApiModel
from ..schemas import (
    NewApiInstanceCreate,
    NewApiInstanceOut,
    NewApiInstanceTestOut,
    NewApiInstanceUpdate,
    NewApiModelOut,
    PageOut,
)
from ..security import get_current_user
from ..services.new_api import sync_all_new_api_models, sync_new_api_models
from ..services.new_api_instances import can_delete_instance, set_default_instance, test_instance


router = APIRouter(prefix="/new-api", tags=["new-api"], dependencies=[Depends(get_current_user)])


@router.get("/instances", response_model=list[NewApiInstanceOut])
def list_instances(db: Session = Depends(get_db)) -> list[NewApiInstance]:
    return db.query(NewApiInstance).order_by(NewApiInstance.is_default.desc(), NewApiInstance.id.asc()).all()


@router.post("/instances", response_model=NewApiInstanceOut)
def create_instance(payload: NewApiInstanceCreate, db: Session = Depends(get_db)) -> NewApiInstance:
    data = payload.model_dump()
    instance = NewApiInstance(**data)
    if data.get("is_default"):
        db.add(instance)
        db.flush()
        set_default_instance(db, instance)
    else:
        db.add(instance)
        db.commit()
    db.refresh(instance)
    return instance


@router.put("/instances/{instance_id}", response_model=NewApiInstanceOut)
def update_instance(instance_id: int, payload: NewApiInstanceUpdate, db: Session = Depends(get_db)) -> NewApiInstance:
    instance = db.query(NewApiInstance).filter(NewApiInstance.id == instance_id).first()
    if not instance:
        raise HTTPException(status_code=404, detail="new-api instance not found")
    data = payload.model_dump(exclude_unset=True)
    make_default = bool(data.pop("is_default", False))
    for key, value in data.items():
        setattr(instance, key, value)
    if make_default:
        set_default_instance(db, instance)
    else:
        db.commit()
    db.refresh(instance)
    return instance


@router.delete("/instances/{instance_id}", status_code=204)
def delete_instance(instance_id: int, db: Session = Depends(get_db)) -> None:
    instance = db.query(NewApiInstance).filter(NewApiInstance.id == instance_id).first()
    if not instance:
        raise HTTPException(status_code=404, detail="new-api instance not found")
    ok, reason = can_delete_instance(db, instance_id)
    if not ok:
        raise HTTPException(status_code=409, detail=reason)
    db.delete(instance)
    db.commit()


@router.post("/instances/{instance_id}/default", response_model=NewApiInstanceOut)
def make_default(instance_id: int, db: Session = Depends(get_db)) -> NewApiInstance:
    instance = db.query(NewApiInstance).filter(NewApiInstance.id == instance_id).first()
    if not instance:
        raise HTTPException(status_code=404, detail="new-api instance not found")
    return set_default_instance(db, instance)


@router.post("/instances/{instance_id}/test", response_model=NewApiInstanceTestOut)
async def test_new_api_instance(instance_id: int, db: Session = Depends(get_db)):
    instance = db.query(NewApiInstance).filter(NewApiInstance.id == instance_id).first()
    if not instance:
        raise HTTPException(status_code=404, detail="new-api instance not found")
    try:
        return await test_instance(instance)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"new-api instance test failed: {exc}") from exc


@router.get("/models", response_model=PageOut[NewApiModelOut])
def list_models(
    category: str | None = None,
    instance_id: int | None = None,
    search: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    query = db.query(NewApiModel).options(joinedload(NewApiModel.instance)).order_by(NewApiModel.model_id.asc())
    if category:
        query = query.filter(NewApiModel.category == category)
    if instance_id:
        query = query.filter(NewApiModel.instance_id == instance_id)
    if search:
        query = query.filter(NewApiModel.model_id.like(f"%{search}%"))
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post("/models/sync", response_model=list[NewApiModelOut])
async def sync_models(instance_id: int | None = None, db: Session = Depends(get_db)) -> list[NewApiModel]:
    try:
        return await sync_new_api_models(db, instance_id)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"new-api sync failed: {exc}") from exc


@router.post("/models/sync-all", response_model=list[NewApiModelOut])
async def sync_all_models(db: Session = Depends(get_db)) -> list[NewApiModel]:
    try:
        return await sync_all_new_api_models(db)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"new-api sync failed: {exc}") from exc
