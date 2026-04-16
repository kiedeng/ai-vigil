from __future__ import annotations

from pathlib import Path
import re
import shutil

from fastapi import UploadFile
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import SampleAsset


def _safe_name(value: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_.-]+", "_", value.strip())
    return safe.strip("._") or "sample"


def storage_dir() -> Path:
    path = Path(get_settings().sample_storage_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def next_version(db: Session, logical_name: str) -> int:
    current = db.query(func.max(SampleAsset.version)).filter(SampleAsset.logical_name == logical_name).scalar()
    return int(current or 0) + 1


def save_upload(
    db: Session,
    file: UploadFile,
    logical_name: str,
    description: str | None = None,
) -> SampleAsset:
    version = next_version(db, logical_name)
    original_name = file.filename or "sample.bin"
    safe_logical = _safe_name(logical_name)
    safe_file = _safe_name(original_name)
    stored_name = f"{safe_logical}_v{version}_{safe_file}"
    path = storage_dir() / stored_name
    with path.open("wb") as target:
        shutil.copyfileobj(file.file, target)
    asset = SampleAsset(
        logical_name=logical_name,
        version=version,
        filename=original_name,
        content_type=file.content_type,
        file_path=str(path),
        size_bytes=path.stat().st_size,
        description=description,
        sample_metadata={},
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset

