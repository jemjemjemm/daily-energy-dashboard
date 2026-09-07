"""Backfill the previous-night companion for every existing morning raw file."""
from __future__ import annotations

from pathlib import Path

from build_report import ROOT, build_previous_night


def main() -> int:
    morning_raw_files = sorted((ROOT / "data" / "raw").glob("????-??-??-morning-raw.json"))
    if not morning_raw_files:
        raise FileNotFoundError("No morning raw files found")
    for raw_path in morning_raw_files:
        morning_date = raw_path.name.removesuffix("-morning-raw.json")
        build_previous_night(morning_date)
    print(f"Backfilled {len(morning_raw_files)} night reports")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
