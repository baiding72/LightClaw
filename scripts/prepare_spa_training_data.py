#!/usr/bin/env python3
"""Prepare SPA-style dense reward data from LightClaw training exports."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.training.spa import prepare_spa_training_data  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare SPA-style training data. No model training is launched.")
    parser.add_argument("--input-dir", default=str(ROOT / "backend" / "data" / "training_exports" / "latest"))
    parser.add_argument("--output-dir", default=str(ROOT / "backend" / "data" / "training_exports" / "latest_spa"))
    args = parser.parse_args()

    result = prepare_spa_training_data(Path(args.input_dir), Path(args.output_dir))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
