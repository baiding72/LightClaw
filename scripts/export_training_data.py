#!/usr/bin/env python3
"""Export LightClaw trajectories into SFT/DPO/GRPO-ready JSONL files."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import get_settings  # noqa: E402
from app.training.exporter import export_training_data  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Export LightClaw training data.")
    parser.add_argument("--fixtures", action="store_true", help="Include deterministic fixture trajectories.")
    parser.add_argument("--with-data-card", action="store_true", help="Write data_card.json with quality checks.")
    parser.add_argument("--output-dir", default=None, help="Output directory. Defaults to backend data exports.")
    parser.add_argument("--trajectory-dir", default=None, help="Recorded trajectory directory.")
    args = parser.parse_args()

    settings = get_settings()
    output_dir = Path(args.output_dir or settings.exports_dir)
    trajectory_dir = Path(args.trajectory_dir or settings.trajectories_dir)
    result = export_training_data(
        output_dir=output_dir,
        trajectory_dir=trajectory_dir,
        include_fixtures=args.fixtures,
        with_data_card=args.with_data_card,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
