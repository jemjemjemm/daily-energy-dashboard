#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validate generated report HTML and dashboard index structure."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})\.html$")
SECTION_RE = re.compile(
    r'<span class="section-num">(\d+)</span><span class="section-title">([^<]+)</span>'
)
NEWS_WINDOW_CUTOFF_DATE = "2026-06-01"
NEWS_QUALITY_CUTOFF_DATE = "2026-06-17"
KOREAN_HOLIDAYS_2026 = {
    "2026-01-01",
    "2026-02-16", "2026-02-17", "2026-02-18",
    "2026-03-02",
    "2026-05-01", "2026-05-05", "2026-05-25",
    "2026-06-03",
    "2026-08-17",
    "2026-09-24", "2026-09-25", "2026-09-28",
    "2026-10-05", "2026-10-09",
    "2026-12-25",
}
BAD_REPORT_PHRASES = (
    "금일 주요 일정 데이터 확인 필요",
    "일정 데이터가 비어 있음",
    "관련 자료 찾지 못함",
    "원문 데이터 없음",
    "자동 확인하지 못했습니다",
    "원문 자동 매칭 실패",
    "대표 기사 데이터 확인 필요",
    "조간 기사 후보를 찾지 못했습니다",
    "자동 매칭 실패",
)
BAD_NEWS_QUALITY_PHRASES = (
    "국제유가와 석유시장 변동 요인을 중심으로 정리",
    "해당 이슈의 업계 관련성을 원문 기준으로 확인 필요",
    "업계 관련성을 원문 기준으로 확인 필요",
    "시장 변동 요인을 중심으로 정리",
    "시장 여건 변화를 중심으로 보도",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate generated report HTML files.")
    parser.add_argument("--reports-dir", default="docs/reports")
    parser.add_argument("--index", default="docs/report-index.json")
    parser.add_argument("--since", default="2026-05-01")
    parser.add_argument("--end", default="")
    parser.add_argument("--date", default="", help="이 날짜의 보고서와 인덱스 항목만 검사")
    parser.add_argument("--allow-weekends", action="store_true")
    return parser.parse_args()


def is_weekend(date_text: str) -> bool:
    return datetime.strptime(date_text, "%Y-%m-%d").weekday() >= 5


def is_holiday(date_text: str) -> bool:
    return date_text in KOREAN_HOLIDAYS_2026


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def section_body(text: str, number: str) -> str:
    pattern = re.compile(
        rf'<span class="section-num">{re.escape(number)}</span>'
        r'<span class="section-title">[^<]+</span></div>\s*(.*?)</section>',
        re.S,
    )
    match = pattern.search(text)
    return match.group(1) if match else ""


def strip_tags(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", value).strip()


SUMMARY_ALIGNMENT_STOPWORDS = {
    "국제유가", "원유", "수급", "변화", "국내", "정유", "석유", "석유제품",
    "가격", "반영", "시차", "업계", "관련", "중심", "보도", "시장", "에너지",
    "주요", "부각", "변수", "정책", "정부", "전망", "가능성", "영향",
}

BROAD_ENERGY_SUMMARY_PATTERNS = (
    "국제유가와 원유 수급 변화",
    "석유화학 업황은 원료 수급",
    "LNG 수급·가격 변동",
    "원유 수급 안정성과 정유 수익성",
)


def normalize_for_compare(value: str) -> str:
    return re.sub(r"[\s\W_]+", "", strip_tags(value), flags=re.UNICODE).lower()


def significant_title_tokens(text: str) -> set[str]:
    tokens = set()
    for token in re.findall(r"[가-힣A-Za-z0-9]{2,}", strip_tags(text)):
        if len(token) < 3:
            continue
        if token in SUMMARY_ALIGNMENT_STOPWORDS:
            continue
        tokens.add(token.lower())
    return tokens


def summary_parts(summary: str) -> list[str]:
    return [part.strip(" .") for part in re.split(r"\s*△\s*", summary) if part.strip(" .")]


def summary_part_matches_title(part: str, title: str) -> bool:
    tokens = significant_title_tokens(title)
    if not tokens:
        return True
    part_norm = normalize_for_compare(part)
    return any(normalize_for_compare(token) in part_norm for token in tokens)


def is_broad_energy_summary(part: str) -> bool:
    return any(pattern in part for pattern in BROAD_ENERGY_SUMMARY_PATTERNS)


def news_texts(body: str) -> tuple[str, list[str], list[str]]:
    summary_match = re.search(r'<div class="news-trend">(.+?)</div>', body, re.S)
    summary = strip_tags(summary_match.group(1)) if summary_match else ""
    titles = [strip_tags(item) for item in re.findall(r'<div class="news-link-title">(.+?)</div>', body, re.S)]
    descs = [strip_tags(item) for item in re.findall(r'<div class="news-link-desc">(.+?)</div>', body, re.S)]
    return summary, titles, descs


def validate_news_quality(path: Path, date_text: str, body: str, slot: str) -> list[str]:
    if date_text < NEWS_QUALITY_CUTOFF_DATE:
        return []

    errors: list[str] = []
    summary, titles, descs = news_texts(body)
    real_titles = [
        title for title in titles
        if title
        and "데이터 대기" not in title
        and "데이터 확인 필요" not in title
        and "뉴스 수집 지연" not in title
    ]

    if real_titles and "△" not in summary:
        errors.append(f"{path}: {slot} news summary is missing per-item △ markers")

    for phrase in BAD_NEWS_QUALITY_PHRASES:
        if phrase in summary:
            errors.append(f"{path}: {slot} news summary contains generic/review phrase: {phrase}")
        if any(phrase in desc for desc in descs):
            errors.append(f"{path}: {slot} news article description contains generic/review phrase: {phrase}")

    for index, (title, desc) in enumerate(zip(real_titles, descs)):
        if is_broad_energy_summary(desc) and not summary_part_matches_title(desc, title):
            errors.append(
                f"{path}: {slot} news article description {index + 1} does not match article title: {title}"
            )

    for title in real_titles:
        if f"△{title}" in summary:
            errors.append(f"{path}: {slot} news summary lists article title instead of content: {title}")

    if real_titles:
        summary_without_markers = re.sub(r"[△·,\s.]+", "", summary)
        titles_joined = re.sub(r"[△·,\s.]+", "", "".join(real_titles[:3]))
        if titles_joined and summary_without_markers == titles_joined:
            errors.append(f"{path}: {slot} news summary is only article titles")
        parts = summary_parts(summary)
        for index, title in enumerate(real_titles[: len(parts)]):
            if is_broad_energy_summary(parts[index]) and not summary_part_matches_title(parts[index], title):
                errors.append(
                    f"{path}: {slot} news summary item {index + 1} does not match article title: {title}"
                )

    return errors


def short_date(dt: datetime) -> str:
    return f"{dt.month}/{dt.day}"


def expected_news_titles(date_text: str, cutoff_hour: str = "08:00") -> tuple[str, str]:
    d = datetime.strptime(date_text, "%Y-%m-%d")
    prev = d - timedelta(days=1)
    return (
        f"News Trend - Morning ({short_date(prev)} 17:00 - {short_date(d)} {cutoff_hour})",
        f"News Trend - Evening ({short_date(d)} {cutoff_hour} - 17:00)",
    )


def allowed_news_titles(date_text: str) -> set[tuple[str, str]]:
    titles = {expected_news_titles(date_text, "08:00")}
    if date_text < NEWS_WINDOW_CUTOFF_DATE:
        titles.add(expected_news_titles(date_text, "09:00"))
    return titles


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
    schedule_body = section_body(text, "5")
    news_body = section_body(text, "6")
    afternoon_news_body = section_body(text, "7")
    expected_title_pairs = allowed_news_titles(date_text)

    if is_weekend(date_text) and not allow_weekends:
        errors.append(f"{path}: weekend report should not exist")
    if is_holiday(date_text):
        errors.append(f"{path}: holiday report should not exist")
    if "이해관계자·정책 주요 동향 (전일 기준)" in text:
        errors.append(f"{path}: removed stakeholder/policy section still exists")
    if nums != ["1", "2", "3", "4", "5", "6", "7"]:
        errors.append(f"{path}: expected section numbers 1..7, got {nums}")
    if "schedule-list" not in schedule_body or "schedule-row" not in schedule_body:
        errors.append(f"{path}: schedule body is missing")
    if "News Trend" not in titles.get("6", "") or "news-body" not in news_body:
        errors.append(f"{path}: News Trend section is missing")
    if "News Trend" not in titles.get("7", "") or "news-body" not in afternoon_news_body:
        errors.append(f"{path}: afternoon News Trend section is missing")
    actual_title_pair = (titles.get("6", ""), titles.get("7", ""))
    if actual_title_pair not in expected_title_pairs:
        expected = " or ".join(
            f"'{morning}' / '{evening}'" for morning, evening in sorted(expected_title_pairs)
        )
        errors.append(f"{path}: expected news section titles {expected}, got '{actual_title_pair[0]}' / '{actual_title_pair[1]}'")
    for phrase in BAD_REPORT_PHRASES:
        if phrase in text:
            errors.append(f"{path}: unresolved fallback/error phrase exists: {phrase}")
    errors.extend(validate_news_quality(path, date_text, news_body, "morning"))
    errors.extend(validate_news_quality(path, date_text, afternoon_news_body, "evening"))

    return errors


def validate_index(path: Path, since: str, allow_weekends: bool, target_date: str = "") -> list[str]:
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
        if target_date and date_text != target_date:
            continue
        if date_text < since:
            continue
        if is_weekend(date_text) and not allow_weekends:
            errors.append(f"{path}: weekend date is indexed: {date_text}")
        if is_holiday(date_text):
            errors.append(f"{path}: holiday date is indexed: {date_text}")
        url = str(item.get("url", ""))
        target = path.parent / url
        if not target.exists():
            errors.append(f"{path}: indexed file does not exist: {date_text} -> {url}")

    return errors


def expected_workdays(since: str, end: str, allow_weekends: bool) -> list[str]:
    if not end:
        return []
    start_dt = datetime.strptime(since, "%Y-%m-%d")
    end_dt = datetime.strptime(end, "%Y-%m-%d")
    dates: list[str] = []
    cur = start_dt
    while cur <= end_dt:
        date_text = cur.strftime("%Y-%m-%d")
        if (allow_weekends or not is_weekend(date_text)) and not is_holiday(date_text):
            dates.append(date_text)
        cur += timedelta(days=1)
    return dates


def main() -> int:
    args = parse_args()
    reports_dir = Path(args.reports_dir)
    index_path = Path(args.index)
    errors: list[str] = []

    if not reports_dir.exists():
        errors.append(f"{reports_dir}: reports directory is missing")
    else:
        paths = [reports_dir / f"{args.date}.html"] if args.date else sorted(reports_dir.glob("*.html"))
        for path in paths:
            if not path.exists():
                errors.append(f"{path}: report file is missing")
                continue
            errors.extend(validate_html_file(path, args.since, args.allow_weekends))
        for date_text in expected_workdays(args.since, args.end, args.allow_weekends):
            if not (reports_dir / f"{date_text}.html").exists():
                errors.append(f"{reports_dir}: expected workday report is missing: {date_text}")

    errors.extend(validate_index(index_path, args.since, args.allow_weekends, args.date))

    if errors:
        for error in errors:
            print(f"[ERROR] {error}")
        return 1

    print(f"[OK] report HTML validation passed: {reports_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
