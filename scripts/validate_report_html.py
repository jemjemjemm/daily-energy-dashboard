#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validate generated report HTML and dashboard index structure."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})\.html$")
SECTION_RE = re.compile(
    r'<span class="section-num">(\d+)</span><span class="section-title">([^<]+)</span>'
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate generated report HTML files.")
    parser.add_argument("--reports-dir", default="docs/reports")
    parser.add_argument("--index", default="docs/report-index.json")
    parser.add_argument("--since", default="2026-05-01")
    parser.add_argument("--allow-weekends", action="store_true")
    return parser.parse_args()


def is_weekend(date_text: str) -> bool:
    return datetime.strptime(date_text, "%Y-%m-%d").weekday() >= 5


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_html_file(path: Path, since: str, allow_weekends: bool) -> list[str]:
    match = DATE_RE.match(path.name)
    if not match:
        return []

    date_text = match.group(1)
    if date_text < since:
        return []

    errors: list[str] = []
    text = path.read_text(encoding="utf-8", errors="replace")
    sections = SECTION_RE.findall(text)
    nums = [num for num, _title in sections]
    titles = {num: title for num, title in sections}

    if is_weekend(date_text) and not allow_weekends:
        errors.append(f"{path}: weekend report should not exist")
    if "이해관계자·정책 주요 동향 (전일 기준)" in text:
        errors.append(f"{path}: removed stakeholder/policy section still exists")
    if nums != ["1", "2", "3", "4", "5", "6"]:
        errors.append(f"{path}: expected section numbers 1..6, got {nums}")
    if "schedule-list" not in text or "schedule-row" not in text:
        errors.append(f"{path}: schedule body is missing")
    if "News Trend" not in titles.get("6", "") or "news-body" not in text:
        errors.append(f"{path}: News Trend section is missing")

    return errors


def validate_index(path: Path, since: str, allow_weekends: bool) -> list[str]:
    if not path.exists():
        return [f"{path}: index file is missing"]

    errors: list[str] = []
    payload = read_json(path)
    reports = payload.get("reports", [])
    if not isinstance(reports, list):
        return [f"{path}: reports is not a list"]

    for item in reports:
        if not isinstance(item, dict):
            errors.append(f"{path}: report item is not an object")
            continue
        date_text = str(item.get("date", ""))
        if date_text < since:
            continue
        if is_weekend(date_text) and not allow_weekends:
            errors.append(f"{path}: weekend date is indexed: {date_text}")
        url = str(item.get("url", ""))
        target = path.parent / url
        if not target.exists():
            errors.append(f"{path}: indexed file does not exist: {date_text} -> {url}")

    return errors


def main() -> int:
    args = parse_args()
    reports_dir = Path(args.reports_dir)
    index_path = Path(args.index)
    errors: list[str] = []

    if not reports_dir.exists():
        errors.append(f"{reports_dir}: reports directory is missing")
    else:
        for path in sorted(reports_dir.glob("*.html")):
            errors.extend(validate_html_file(path, args.since, args.allow_weekends))

    errors.extend(validate_index(index_path, args.since, args.allow_weekends))

    if errors:
        for error in errors:
            print(f"[ERROR] {error}")
        return 1

    print(f"[OK] report HTML validation passed: {reports_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
