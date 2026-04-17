from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import SampleAsset
from ..schemas import PageOut, SampleAssetOut
from ..security import get_current_user
from ..services.samples import save_upload


router = APIRouter(prefix="/samples", tags=["samples"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=PageOut[SampleAssetOut])
def list_samples(
    logical_name: str | None = None,
    search: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    query = db.query(SampleAsset).order_by(SampleAsset.logical_name.asc(), SampleAsset.version.desc())
    if logical_name:
        query = query.filter(SampleAsset.logical_name == logical_name)
    if search:
        like = f"%{search}%"
        query = query.filter((SampleAsset.logical_name.like(like)) | (SampleAsset.filename.like(like)))
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post("", response_model=SampleAssetOut)
def upload_sample(
    file: UploadFile = File(...),
    logical_name: str = Form(...),
    description: str | None = Form(default=None),
    db: Session = Depends(get_db),
) -> SampleAsset:
    return save_upload(db, file=file, logical_name=logical_name, description=description)


@router.get("/{sample_id}/content")
def sample_content(sample_id: int, db: Session = Depends(get_db)) -> FileResponse:
    sample = db.query(SampleAsset).filter(SampleAsset.id == sample_id).first()
    if not sample:
        raise HTTPException(status_code=404, detail="Sample not found")
    path = Path(sample.file_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Sample file missing")
    return FileResponse(path, media_type=sample.content_type, filename=sample.filename)
