import asyncio

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import ModelPerformanceComparison, ModelPerformanceRun, ModelPerformanceTest
from ..schemas import (
    ModelPerformanceComparisonCreate,
    ModelPerformanceComparisonLogOut,
    ModelPerformanceComparisonOut,
    ModelPerformanceComparisonUpdate,
    ModelPerformanceDatasetOut,
    ModelPerformanceDatasetPreviewOut,
    ModelPerformanceRunLogOut,
    ModelPerformanceRunOut,
    ModelPerformanceTestCreate,
    ModelPerformanceTestOut,
    ModelPerformanceTestUpdate,
    PageOut,
)
from ..security import get_current_user
from ..services.model_performance import (
    cancel_model_performance_run,
    create_model_performance_run,
    execute_model_performance_run,
    read_run_log,
)
from ..services.model_performance_comparisons import (
    cancel_comparison,
    create_comparison,
    execute_comparison,
    get_comparison,
    read_comparison_log,
    update_comparison,
)
from ..services.model_performance_datasets import (
    list_performance_datasets,
    preview_performance_dataset,
    save_performance_dataset,
)


router = APIRouter(prefix="/model-performance-tests", tags=["model-performance-tests"], dependencies=[Depends(get_current_user)])
runs_router = APIRouter(
    prefix="/model-performance-runs", tags=["model-performance-runs"], dependencies=[Depends(get_current_user)]
)
datasets_router = APIRouter(
    prefix="/model-performance-datasets",
    tags=["model-performance-datasets"],
    dependencies=[Depends(get_current_user)],
)
comparisons_router = APIRouter(
    prefix="/model-performance-comparisons",
    tags=["model-performance-comparisons"],
    dependencies=[Depends(get_current_user)],
)


@datasets_router.get("", response_model=list[ModelPerformanceDatasetOut])
def list_datasets() -> list[object]:
    return list_performance_datasets()


@datasets_router.post("", response_model=ModelPerformanceDatasetOut)
def upload_dataset(
    file: UploadFile = File(...),
    name: str = Form(...),
    dataset: str = Form(...),
    description: str | None = Form(default=None),
) -> object:
    if dataset not in {"openqa", "line_by_line"}:
        raise HTTPException(status_code=400, detail="dataset must be openqa or line_by_line")
    try:
        return save_performance_dataset(file=file, name=name, dataset=dataset, description=description)  # type: ignore[arg-type]
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@datasets_router.get("/{name}/preview", response_model=ModelPerformanceDatasetPreviewOut)
def dataset_preview(name: str) -> object:
    dataset = preview_performance_dataset(name)
    if not dataset:
        raise HTTPException(status_code=404, detail="Model performance dataset not found")
    return dataset


@router.get("", response_model=PageOut[ModelPerformanceTestOut])
def list_tests(
    search: str | None = None,
    enabled: bool | None = None,
    instance_id: int | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    query = db.query(ModelPerformanceTest).order_by(ModelPerformanceTest.id.desc())
    query = query.filter(ModelPerformanceTest.name.notlike("[对比子项]%"))
    if search:
        query = query.filter(ModelPerformanceTest.name.like(f"%{search}%"))
    if enabled is not None:
        query = query.filter(ModelPerformanceTest.enabled.is_(enabled))
    if instance_id is not None:
        query = query.filter(ModelPerformanceTest.new_api_instance_id == instance_id)
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post("", response_model=ModelPerformanceTestOut, status_code=status.HTTP_201_CREATED)
def create_test(payload: ModelPerformanceTestCreate, db: Session = Depends(get_db)) -> ModelPerformanceTest:
    row = ModelPerformanceTest(**payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.get("/{test_id}", response_model=ModelPerformanceTestOut)
def get_test(test_id: int, db: Session = Depends(get_db)) -> ModelPerformanceTest:
    row = db.query(ModelPerformanceTest).filter(ModelPerformanceTest.id == test_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Model performance test not found")
    return row


@router.put("/{test_id}", response_model=ModelPerformanceTestOut)
def update_test(
    test_id: int,
    payload: ModelPerformanceTestUpdate,
    db: Session = Depends(get_db),
) -> ModelPerformanceTest:
    row = db.query(ModelPerformanceTest).filter(ModelPerformanceTest.id == test_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Model performance test not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, key, value)
    db.commit()
    db.refresh(row)
    return row


@router.delete("/{test_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_test(test_id: int, db: Session = Depends(get_db)) -> None:
    row = db.query(ModelPerformanceTest).filter(ModelPerformanceTest.id == test_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Model performance test not found")
    db.delete(row)
    db.commit()


@router.post("/{test_id}/run", response_model=ModelPerformanceRunOut)
async def run_test(test_id: int, db: Session = Depends(get_db)) -> ModelPerformanceRun:
    row = db.query(ModelPerformanceTest).filter(ModelPerformanceTest.id == test_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Model performance test not found")
    run = create_model_performance_run(db, row)
    asyncio.create_task(execute_model_performance_run(run.id))
    return run


@router.get("/{test_id}/runs", response_model=PageOut[ModelPerformanceRunOut])
def list_runs(
    test_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    if not db.query(ModelPerformanceTest.id).filter(ModelPerformanceTest.id == test_id).first():
        raise HTTPException(status_code=404, detail="Model performance test not found")
    query = db.query(ModelPerformanceRun).filter(ModelPerformanceRun.test_id == test_id).order_by(ModelPerformanceRun.id.desc())
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@runs_router.get("/{run_id}", response_model=ModelPerformanceRunOut)
def get_run(run_id: int, db: Session = Depends(get_db)) -> ModelPerformanceRun:
    row = db.query(ModelPerformanceRun).filter(ModelPerformanceRun.id == run_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Model performance run not found")
    return row


@runs_router.post("/{run_id}/cancel", response_model=ModelPerformanceRunOut)
def cancel_run(run_id: int, db: Session = Depends(get_db)) -> ModelPerformanceRun:
    row = db.query(ModelPerformanceRun).filter(ModelPerformanceRun.id == run_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Model performance run not found")
    if not cancel_model_performance_run(db, row):
        raise HTTPException(status_code=409, detail="Model performance run is not running")
    return row


@runs_router.get("/{run_id}/logs", response_model=ModelPerformanceRunLogOut)
def get_run_logs(
    run_id: int,
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    row = db.query(ModelPerformanceRun).filter(ModelPerformanceRun.id == run_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Model performance run not found")
    return read_run_log(row, offset)


@comparisons_router.get("", response_model=PageOut[ModelPerformanceComparisonOut])
def list_comparisons(
    search: str | None = None,
    enabled: bool | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    query = db.query(ModelPerformanceComparison).order_by(ModelPerformanceComparison.id.desc())
    if search:
        query = query.filter(ModelPerformanceComparison.name.like(f"%{search}%"))
    if enabled is not None:
        query = query.filter(ModelPerformanceComparison.enabled.is_(enabled))
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@comparisons_router.post("", response_model=ModelPerformanceComparisonOut, status_code=status.HTTP_201_CREATED)
def create_model_comparison(
    payload: ModelPerformanceComparisonCreate,
    db: Session = Depends(get_db),
) -> ModelPerformanceComparison:
    try:
        return create_comparison(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@comparisons_router.get("/{comparison_id}", response_model=ModelPerformanceComparisonOut)
def get_model_comparison(comparison_id: int, db: Session = Depends(get_db)) -> ModelPerformanceComparison:
    row = get_comparison(db, comparison_id)
    if not row:
        raise HTTPException(status_code=404, detail="Model performance comparison not found")
    return row


@comparisons_router.put("/{comparison_id}", response_model=ModelPerformanceComparisonOut)
def update_model_comparison(
    comparison_id: int,
    payload: ModelPerformanceComparisonUpdate,
    db: Session = Depends(get_db),
) -> ModelPerformanceComparison:
    row = get_comparison(db, comparison_id)
    if not row:
        raise HTTPException(status_code=404, detail="Model performance comparison not found")
    if row.status in {"pending", "running"}:
        raise HTTPException(status_code=409, detail="Model performance comparison is running")
    try:
        return update_comparison(db, row, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@comparisons_router.delete("/{comparison_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_model_comparison(comparison_id: int, db: Session = Depends(get_db)) -> None:
    row = get_comparison(db, comparison_id)
    if not row:
        raise HTTPException(status_code=404, detail="Model performance comparison not found")
    db.delete(row)
    db.commit()


@comparisons_router.post("/{comparison_id}/run", response_model=ModelPerformanceComparisonOut)
async def run_model_comparison(comparison_id: int, db: Session = Depends(get_db)) -> ModelPerformanceComparison:
    row = get_comparison(db, comparison_id)
    if not row:
        raise HTTPException(status_code=404, detail="Model performance comparison not found")
    if row.status in {"pending", "running"}:
        raise HTTPException(status_code=409, detail="Model performance comparison is already running")
    row.status = "pending"
    row.error = None
    db.commit()
    asyncio.create_task(execute_comparison(row.id))
    refreshed = get_comparison(db, row.id)
    return refreshed or row


@comparisons_router.post("/{comparison_id}/cancel", response_model=ModelPerformanceComparisonOut)
def cancel_model_comparison(comparison_id: int, db: Session = Depends(get_db)) -> ModelPerformanceComparison:
    row = get_comparison(db, comparison_id)
    if not row:
        raise HTTPException(status_code=404, detail="Model performance comparison not found")
    if not cancel_comparison(db, row):
        raise HTTPException(status_code=409, detail="Model performance comparison is not running")
    refreshed = get_comparison(db, row.id)
    return refreshed or row


@comparisons_router.get("/{comparison_id}/logs", response_model=ModelPerformanceComparisonLogOut)
def get_model_comparison_logs(comparison_id: int, db: Session = Depends(get_db)) -> dict[str, object]:
    row = get_comparison(db, comparison_id)
    if not row:
        raise HTTPException(status_code=404, detail="Model performance comparison not found")
    return read_comparison_log(db, row)
