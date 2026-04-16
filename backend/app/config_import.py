"""
CLI entry point for config import.

Usage:
    python -m backend.app.config_import [--path ai-vigil.yaml]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from backend.app.config import PROJECT_ROOT
from backend.app.database import SessionLocal
from backend.app.services.config_import import import_all


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

    if not config_path.exists():
        print(f"Error: Config file not found: {config_path}", file=sys.stderr)
        print(
            f"Hint: Copy {PROJECT_ROOT / 'ai-vigil.yaml.example'} to "
            f"{PROJECT_ROOT / 'ai-vigil.yaml'} and edit it.",
            file=sys.stderr,
        )
        sys.exit(1)

    db = SessionLocal()
    try:
        result = import_all(db, config_path)
    finally:
        db.close()

    print(f"\n{'='*50}")
    print("AI Vigil Config Import")
    print(f"{'='*50}")
    print(f"\nInstances : created={result.instances_created}, updated={result.instances_updated}")
    print(f"Checks    : created={result.checks_created}, updated={result.checks_updated}")
    print(f"Alert ch. : created={result.alert_channels_created}, updated={result.alert_channels_updated}")
    print(f"GoldenSet : created={result.golden_sets_created}, updated={result.golden_sets_updated}")
    print(f"GoldenCase: created={result.golden_cases_created}, updated={result.golden_cases_updated}")

    data = result.to_dict()
    all_errors = {k: v for k, v in data["errors"].items() if v}
    if all_errors:
        print("\nErrors:")
        for section, errs in all_errors.items():
            for err in errs:
                print(f"  [{section}] {err}")

    has_errors = bool(all_errors)
    print(f"\n{'Import succeeded.' if not has_errors else 'Import completed with errors.'}")
    sys.exit(0 if not has_errors else 1)


if __name__ == "__main__":
    main()
