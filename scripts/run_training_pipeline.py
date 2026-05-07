#!/usr/bin/env python3
"""Run the deterministic LightClaw training-preparation pipeline."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.training.pipeline import run_training_pipeline  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Run LightClaw local training-preparation pipeline.")
    parser.add_argument("--output-root", default=None)
    parser.add_argument("--no-fixtures", action="store_true", help="Do not include deterministic fixtures in export.")
    args = parser.parse_args()

    result = run_training_pipeline(
        output_root=Path(args.output_root) if args.output_root else None,
        include_fixtures=not args.no_fixtures,
    )
    print(json.dumps({
        "status": result["status"],
        "training_status": result["training_status"],
        "report_path": result["report_path"],
        "markdown_path": result["markdown_path"],
        "stage_count": len(result["stages"]),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
