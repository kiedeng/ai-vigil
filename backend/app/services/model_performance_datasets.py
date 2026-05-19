from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
import re
import shutil
from typing import Literal

from fastapi import UploadFile

from ..config import get_settings
from .model_performance import DEFAULT_DATASET


DatasetType = Literal["openqa", "line_by_line"]


@dataclass
class PerformanceDataset:
    name: str
    dataset: DatasetType
    source: Literal["builtin", "uploaded"]
    dataset_path: str
    description: str | None
    size_bytes: int
    item_count: int
    updated_at: datetime | None
    preview: list[str]


BUILTIN_DATASETS = [
    {
        "name": "内置中文问答轻量集",
        "dataset": "openqa",
        "path": DEFAULT_DATASET,
        "description": "适合首次冒烟和低成本验证，覆盖基础问答、改写、JSON 输出和性能概念解释。",
    },
    {
        "name": "内置短输入长输出集",
        "dataset": "line_by_line",
        "path": DEFAULT_DATASET.parent / "long_output_short_input_zh.txt",
        "description": "适合测试短 prompt 触发 3000 到 4000 token 长输出的解码吞吐、超时和稳定性，建议最大输出 token 设置为 4096 或更高。",
    }
]


def dataset_storage_dir() -> Path:
    path = Path(get_settings().model_performance_dataset_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _safe_name(value: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_.-]+", "_", value.strip())
    return safe.strip("._") or "dataset"


def _metadata_path(path: Path) -> Path:
    return path.with_suffix(path.suffix + ".meta.json")


def _read_metadata(path: Path) -> dict[str, object]:
    meta_path = _metadata_path(path)
    if not meta_path.exists():
        return {}
    try:
        data = json.loads(meta_path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def _read_prompts(path: Path, dataset: DatasetType, limit: int | None = None) -> list[str]:
    prompts: list[str] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            text = line.strip()
            if not text:
                continue
            if dataset == "openqa":
                try:
                    item = json.loads(text)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"第 {line_no} 行不是合法 JSON") from exc
                if not isinstance(item, dict) or not str(item.get("question") or "").strip():
                    raise ValueError(f"第 {line_no} 行必须包含非空 question 字段")
                prompts.append(str(item["question"]).strip())
            else:
                prompts.append(text)
            if limit and len(prompts) >= limit:
                break
    return prompts


def _count_items(path: Path, dataset: DatasetType) -> int:
    return len(_read_prompts(path, dataset, None))


def _dataset_from_path(path: Path, fallback: DatasetType = "line_by_line") -> DatasetType:
    metadata = _read_metadata(path)
    value = metadata.get("dataset")
    if value in {"openqa", "line_by_line"}:
        return value  # type: ignore[return-value]
    if path.suffix.lower() == ".jsonl":
        return "openqa"
    return fallback


def _dataset_info(
    *,
    name: str,
    dataset: DatasetType,
    source: Literal["builtin", "uploaded"],
    path: Path,
    description: str | None,
) -> PerformanceDataset:
    stat = path.stat()
    preview = _read_prompts(path, dataset, 5)
    item_count = _count_items(path, dataset)
    return PerformanceDataset(
        name=name,
        dataset=dataset,
        source=source,
        dataset_path=str(path),
        description=description,
        size_bytes=stat.st_size,
        item_count=item_count,
        updated_at=datetime.fromtimestamp(stat.st_mtime),
        preview=preview,
    )


def list_performance_datasets() -> list[PerformanceDataset]:
    datasets: list[PerformanceDataset] = []
    for item in BUILTIN_DATASETS:
        path = Path(item["path"])
        if path.exists():
            datasets.append(
                _dataset_info(
                    name=str(item["name"]),
                    dataset=item["dataset"],  # type: ignore[arg-type]
                    source="builtin",
                    path=path,
                    description=str(item["description"]),
                )
            )

    for path in sorted(dataset_storage_dir().iterdir()):
        if not path.is_file() or path.name.endswith(".meta.json"):
            continue
        if path.suffix.lower() not in {".jsonl", ".txt"}:
            continue
        metadata = _read_metadata(path)
        dataset = _dataset_from_path(path)
        datasets.append(
            _dataset_info(
                name=str(metadata.get("name") or path.stem),
                dataset=dataset,
                source="uploaded",
                path=path,
                description=str(metadata.get("description") or "") or None,
            )
        )
    return datasets


def get_performance_dataset(name: str) -> PerformanceDataset | None:
    for dataset in list_performance_datasets():
        if dataset.name == name or dataset.dataset_path == name:
            return dataset
    return None


def preview_performance_dataset(name: str) -> PerformanceDataset | None:
    return get_performance_dataset(name)


def save_performance_dataset(
    file: UploadFile,
    name: str,
    dataset: DatasetType,
    description: str | None = None,
) -> PerformanceDataset:
    original = file.filename or ("dataset.jsonl" if dataset == "openqa" else "dataset.txt")
    suffix = ".jsonl" if dataset == "openqa" else ".txt"
    safe_name = _safe_name(name)
    safe_file = _safe_name(Path(original).stem)
    path = dataset_storage_dir() / f"{safe_name}_{safe_file}{suffix}"
    with path.open("wb") as target:
        shutil.copyfileobj(file.file, target)
    try:
        _read_prompts(path, dataset, None)
    except Exception:
        path.unlink(missing_ok=True)
        raise
    _metadata_path(path).write_text(
        json.dumps(
            {"name": name, "dataset": dataset, "description": description or "", "filename": original},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return _dataset_info(name=name, dataset=dataset, source="uploaded", path=path, description=description)
