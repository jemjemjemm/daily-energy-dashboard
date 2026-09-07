"""Fail the workflow when generated reports or their index are inconsistent."""
from __future__ import annotations

import json
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

from utils_time import get_period, is_in_period

ROOT = Path(__file__).resolve().parents[1]


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read valid JSON: {path.relative_to(ROOT)}: {exc}") from exc


def validate_report(path: Path) -> list[str]:
    errors: list[str] = []
    report = load_json(path)
    base_date, slot = report.get("base_date"), report.get("slot")
    expected_name = f"{base_date}-{slot}.json"
    if path.name != expected_name:
        errors.append(f"{path.name}: metadata expects {expected_name}")
        return errors
    try:
        start, end = get_period(base_date, slot)
    except (TypeError, ValueError) as exc:
        return [f"{path.name}: invalid base_date/slot: {exc}"]
    if report.get("period_start") != start.isoformat() or report.get("period_end") != end.isoformat():
        errors.append(f"{path.name}: incorrect reporting period")
    articles = report.get("articles")
    if not isinstance(articles, list):
        return errors + [f"{path.name}: articles must be a list"]
    for article in articles:
        if not is_in_period(article.get("published_at"), start, end):
            errors.append(f"{path.name}: article {article.get('id', '(unknown)')} is outside its period")
    if report.get("total_deduped_count") != len(articles):
        errors.append(f"{path.name}: total_deduped_count does not match articles")
    status_counts = Counter(article.get("quality_status") for article in articles)
    grade_counts = Counter(article.get("grade") for article in articles)
    if report.get("total_ok_count") != status_counts["ok"]:
        errors.append(f"{path.name}: total_ok_count is incorrect")
    if report.get("total_review_count") != status_counts["review"]:
        errors.append(f"{path.name}: total_review_count is incorrect")
    if report.get("grade_counts") != {grade: grade_counts[grade] for grade in "ABC"}:
        errors.append(f"{path.name}: grade_counts is incorrect")
    return errors


def validate_all() -> list[str]:
    errors: list[str] = []
    report_dir = ROOT / "data" / "reports"
    report_paths = sorted(report_dir.glob("*.json"))
    report_keys = set()
    for path in report_paths:
        errors.extend(validate_report(path))
        payload = load_json(path)
        report_keys.add((payload.get("base_date"), payload.get("slot")))

    index_path = ROOT / "data" / "report-index.json"
    index = load_json(index_path)
    index_keys = {(entry.get("base_date"), entry.get("slot")) for entry in index}
    if len(index_keys) != len(index):
        errors.append("data/report-index.json contains duplicate entries")
    if index_keys != report_keys:
        errors.append("data/report-index.json does not match report JSON files")
    for entry in index:
        json_path = ROOT / str(entry.get("json_path", ""))
        html_path = ROOT / str(entry.get("html_path", ""))
        if not json_path.is_file():
            errors.append(f"Missing indexed JSON: {entry.get('json_path')}")
        if not html_path.is_file():
            errors.append(f"Missing indexed HTML: {entry.get('html_path')}")

    morning_dates = {date.fromisoformat(day) for day, slot in report_keys if slot == "morning"}
    night_dates = {date.fromisoformat(day) for day, slot in report_keys if slot == "night"}
    missing_nights = sorted(day - timedelta(days=1) for day in morning_dates if day - timedelta(days=1) not in night_dates)
    if missing_nights:
        errors.append("Morning reports missing previous-night companions: " + ", ".join(map(str, missing_nights)))
    return errors


def main() -> int:
    errors = validate_all()
    if errors:
        print("Report validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("All report files, periods, counts, index entries and morning/night pairs are valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
