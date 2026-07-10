#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fail publication when a SafeTimes schedule source is missing or silently unusable."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from scripts.build_report_draft_from_schedule import (
        schedule_candidate_count,
        schedule_items_from_json_or_body,
        source_body,
        source_url,
    )
except ModuleNotFoundError:  # direct execution: python scripts/validate_schedule_source.py
    from build_report_draft_from_schedule import (  # type: ignore
        schedule_candidate_count,
        schedule_items_from_json_or_body,
        source_body,
        source_url,
    )

OBVIOUS_BUSINESS_KEYWORDS = (
    "석유", "정유", "석유화학", "유가", "LNG", "에너지", "전력", "ESS",
    "원전", "수소", "가스", "공급망", "통상", "반도체", "배터리", "산업",
)


def validate_payload(data: dict, expected_date: str, max_items: int = 12) -> list[str]:
    errors: list[str] = []
    body = source_body(data).strip()
    url = source_url(data).strip()

    if data.get("success") is not True:
        errors.append("success=true가 아닙니다")
    if data.get("date") != expected_date:
        errors.append(f"date={data.get('date')!r}, expected={expected_date!r}")
    if not url or "safetimes.co.kr/news/articleView" not in url:
        errors.append("세이프타임즈 원문 기사 URL이 없습니다")
    if not body:
        errors.append("원문 본문이 비어 있습니다")
    if data.get("approved_date") and data.get("approved_date") != expected_date:
        errors.append(f"승인일이 대상일과 다릅니다: {data.get('approved_date')}")

    if body:
        candidate_count = schedule_candidate_count(data, max_items=max_items)
        relevant_items = schedule_items_from_json_or_body(data, max_items=max_items)
        if candidate_count == 0:
            errors.append("원문에서 일정 후보를 한 건도 파싱하지 못했습니다")
        if any(keyword in body for keyword in OBVIOUS_BUSINESS_KEYWORDS) and not relevant_items:
            errors.append("원문에 명백한 사업 관련 키워드가 있지만 관련 일정 추출 결과가 0건입니다")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    parser.add_argument("--schedule-dir", default="data/schedules")
    parser.add_argument("--max-items", type=int, default=12)
    args = parser.parse_args()

    path = Path(args.schedule_dir) / f"{args.date}.json"
    if not path.exists():
        print(f"[ERROR] 일정 JSON이 없습니다: {path}")
        return 1
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"[ERROR] 일정 JSON 파싱 실패: {path}: {exc}")
        return 1

    errors = validate_payload(data, args.date, max_items=args.max_items)
    if errors:
        for error in errors:
            print(f"[ERROR] {path}: {error}")
        return 1
    print(f"[OK] 일정 원문 검증 통과: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
