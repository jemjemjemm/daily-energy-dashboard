#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def copy_tree(source: Path, destination: Path) -> None:
    if not source.exists():
        raise SystemExit(f"[ERROR] required source is missing: {source.relative_to(ROOT)}")
    shutil.copytree(source, destination, dirs_exist_ok=True)


def load_index(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_index(index_path: Path, report_dir: Path, suffix: str) -> None:
    index = load_index(index_path)
    if isinstance(index, list):
        files = sorted(report_dir.glob(f"*{suffix}"))
        if len(files) != len(index):
            raise SystemExit(
                f"[ERROR] index/file mismatch for {index_path}: index={len(index)}, files={len(files)}"
            )
        return
    reports = index.get("reports", [])
    dates = index.get("availableDates", [])
    files = sorted(report_dir.glob(f"*{suffix}"))
    if index.get("count") != len(reports) or len(dates) != len(reports):
        raise SystemExit(f"[ERROR] inconsistent index counts: {index_path}")
    if len(files) != len(reports):
        raise SystemExit(
            f"[ERROR] index/file mismatch for {index_path}: index={len(reports)}, files={len(files)}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Assemble the Daily and oil reports into one Pages artifact")
    parser.add_argument("--output", default="_site")
    args = parser.parse_args()

    output = (ROOT / args.output).resolve()
    if output == ROOT or ROOT not in output.parents:
        raise SystemExit("[ERROR] output must be a child directory of the repository")
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)

    docs = ROOT / "docs"
    for child in docs.iterdir():
        if child.name == "_site":
            continue
        target = output / child.name
        if child.is_dir():
            copy_tree(child, target)
        else:
            shutil.copy2(child, target)

    copy_tree(ROOT / "shared", output / "shared")
    oil_output = output / "oil"
    oil_output.mkdir()
    shutil.copy2(ROOT / "oil/index.html", oil_output / "index.html")
    copy_tree(ROOT / "oil/assets", oil_output / "assets")
    copy_tree(ROOT / "oil/reports", oil_output / "reports")
    (oil_output / "data/reports").mkdir(parents=True)
    shutil.copy2(ROOT / "oil/data/report-index.json", oil_output / "data/report-index.json")
    copy_tree(ROOT / "oil/data/reports", oil_output / "data/reports")
    (output / ".nojekyll").touch()

    validate_index(output / "report-index.json", output / "reports", ".html")
    validate_index(oil_output / "data/report-index.json", oil_output / "data/reports", ".json")
    print("[OK] Pages artifact assembled")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
