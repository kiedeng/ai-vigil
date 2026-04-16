"""
Config import API endpoint and CLI entry point.

Usage (CLI):
    python -m backend.app.config_import [--path ai-vigil.yaml]

Usage (API):
    POST /api/config-import
    Body (optional): { "path": "ai-vigil.yaml" }
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..config import PROJECT_ROOT, get_settings
from ..database import SessionLocal, get_db
from ..security import get_current_user
from ..services.config_import import ImportResult, import_all


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------


class ConfigImportRequest(BaseModel):
    path: str | None = None  # relative to project root, or absolute


class ConfigImportResponse(BaseModel):
    success: bool
    message: str
    created: dict[str, int]
    updated: dict[str, int]
    errors: dict[str, list[str]]


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/config-import", tags=["config-import"], dependencies=[Depends(get_current_user)])


@router.post("", response_model=ConfigImportResponse)
def import_config(payload: ConfigImportRequest | None = None, db: Session = Depends(get_db)) -> ConfigImportResponse:
    settings_obj = get_settings()
    if payload and payload.path:
        config_path = (PROJECT_ROOT / payload.path).resolve()
    else:
        config_path = PROJECT_ROOT / "ai-vigil.yaml"

    if not config_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Config file not found: {config_path}. Copy ai-vigil.yaml.example to ai-vigil.yaml and edit it.",
        )

    try:
        result: ImportResult = import_all(db, config_path)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Import failed: {exc}") from exc

    data = result.to_dict()
    has_errors = any(v for v in data["errors"].values())

    return ConfigImportResponse(
        success=not has_errors,
        message=(
            f"Import complete. "
            f"Created: instances={result.instances_created}, checks={result.checks_created}, "
            f"alert_channels={result.alert_channels_created}, golden_sets={result.golden_sets_created} | "
            f"Updated: instances={result.instances_updated}, checks={result.checks_updated}, "
            f"alert_channels={result.alert_channels_updated}, golden_sets={result.golden_sets_updated}"
        ),
        created={
            "instances": result.instances_created,
            "checks": result.checks_created,
            "alert_channels": result.alert_channels_created,
            "golden_sets": result.golden_sets_created,
            "golden_cases": result.golden_cases_created,
        },
        updated={
            "instances": result.instances_updated,
            "checks": result.checks_updated,
            "alert_channels": result.alert_channels_updated,
            "golden_sets": result.golden_sets_updated,
            "golden_cases": result.golden_cases_updated,
        },
        errors={
            "instances": result.errors.instances,
            "checks": result.errors.checks,
            "alert_channels": result.errors.alert_channels,
            "golden_sets": result.errors.golden_sets,
        },
    )


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Import AI Vigil configuration from YAML file")
    parser.add_argument(
        "--path",
        type=str,
        default="ai-vigil.yaml",
        help="Path to YAML config file (relative to project root or absolute)",
    )
    args = parser.parse_args()

    config_path = Path(args.path)
    if not config_path.is_absolute():
        config_path = PROJECT_ROOT / args.path

    db = SessionLocal()
    try:
        result = import_all(db, config_path)
    finally:
        db.close()

    data = result.to_dict()
    has_errors = any(v for v in data["errors"].values())

    print(f"\n{'='*50}")
    print(f"AI Vigil Config Import")
    print(f"{'='*50}")
    print(f"\nInstances : created={result.instances_created}, updated={result.instances_updated}")
    print(f"Checks    : created={result.checks_created}, updated={result.checks_updated}")
    print(f"Alert ch. : created={result.alert_channels_created}, updated={result.alert_channels_updated}")
    print(f"GoldenSet : created={result.golden_sets_created}, updated={result.golden_sets_updated}")
    print(f"GoldenCase: created={result.golden_cases_created}, updated={result.golden_cases_updated}")

    all_errors = {
        k: v for k, v in data["errors"].items() if v
    }
    if all_errors:
        print(f"\nErrors:")
        for section, errs in all_errors.items():
            for err in errs:
                print(f"  [{section}] {err}")

    if not has_errors:
        print("\nImport succeeded with no errors.")
        sys.exit(0)
    else:
        print("\nImport completed with errors.")
        sys.exit(1)


if __name__ == "__main__":
    main()
