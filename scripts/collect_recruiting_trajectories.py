#!/usr/bin/env python3
"""Collect safe recruiting trajectories.

Supported modes:
- fixture: local HTML snapshots only, deterministic and testable.
- dry-run: open a provided URL, extract visible/static HTML, then stop.

This script never logs in, uploads files, bypasses CAPTCHA, or submits an
application.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.recruiting import collect_dry_run_trajectory, collect_fixture_trajectories  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect safe recruiting trajectories.")
    parser.add_argument("--mode", choices=["fixture", "dry-run"], default="fixture")
    parser.add_argument("--url", default=None, help="Required for --mode dry-run.")
    parser.add_argument("--fixture-dir", default=None)
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args()

    fixture_dir = Path(args.fixture_dir or ROOT / "backend" / "tests" / "fixtures" / "recruiting")
    output_dir = Path(args.output_dir or ROOT / "backend" / "data" / "trajectories" / "recruiting" / "latest")

    if args.mode == "fixture":
        summary = collect_fixture_trajectories(fixture_dir=fixture_dir, output_dir=output_dir)
    else:
        if not args.url:
            raise SystemExit("--url is required for --mode dry-run")
        summary = collect_dry_run_trajectory(url=args.url, output_dir=output_dir)

    print(json.dumps({"mode": args.mode, **summary}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
