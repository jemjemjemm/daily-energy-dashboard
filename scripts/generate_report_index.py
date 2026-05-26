#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_report_index.py

Build docs/report-index.json from docs/reports/*.html for the dashboard.
This file is intentionally tolerant of both the old report template
("Daily Issue Report") and the new report template ("Daily 유가 동향").

Required compatibility:
  python scripts/generate_report_index.py --reports-dir docs/reports --out docs/report-index.json
"""
from __future__ import annotations

import argparse
import json
import re
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")
TITLE_RE = re.compile(r"<title[^>]*>\s*(.*?)\s*</title>", re.I | re.S)
HEADER_DATE_RE = re.compile(r"class=[\"'][^\"']*header-date[^\"']*[\"'][^>]*>\s*(.*?)\s*</", re.I | re.S)

BAD_HTML_PHRASES = [
    "자동 추출된 일정 항목이 없습니다",
    "본문 구조 확인 및 수동 검수가 필요합니다",
    "원문 자동 매칭 실패",
    "주요일정 원문 데이터 미확보",
    "원문 데이터 없음",
    "가격 데이터 중심 리포트",
    "가격 중심 자동생성",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="캘린더 대시보드용 report-index.json 생성",
        allow_abbrev=False,
    )
    parser.add_argument("--reports-dir", default="docs/reports", help="HTML 리포트 폴더")
    parser.add_argument("--out", default="docs/report-index.json", help="출력 JSON 파일")
    parser.add_argument("--strict-json", action="store_true", help="data/reports JSON 검증까지 수행")
    return parser.parse_args()


def strip_tags(value: str) -> str:
    value = re.sub(r"<[^>]*>", "", value or "")
    value = (
        value.replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
        .replace("&#39;", "'")
    )
    return re.sub(r"\s+", " ", value).strip()


def now_kst_text() -> str:
    kst = timezone(timedelta(hours=9))
    return datetime.now(kst).strftime("%Y-%m-%d %H:%M:%S KST")


def atomic_write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=str(path.parent),
        delete=False,
        prefix=f".{path.name}.",
        suffix=".tmp",
    ) as tmp:
        tmp.write(text)
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)


def has_bad_phrase(text: str) -> bool:
    return any(phrase in text for phrase in BAD_HTML_PHRASES)


def has_required_structure(text: str) -> bool:
    if not text:
        return False
    has_title = (
        "Daily 유가 동향" in text
        or "Daily Issue Report" in text
        or "Daily_유가_동향" in text
    )
    has_summary = "Summary" in text
    has_price = "유가 동향" in text or "원유 가격" in text or "석유제품" in text
    has_news = "조간 신문 트렌드" in text or "조간 보도" in text or "대표 기사" in text
    has_layout = "section" in text or "container" in text or "report-section" in text
    return has_title and has_summary and has_price and has_news and has_layout


def has_article_block(text: str) -> bool:
    # The new template uses news-link; older versions use news-item/article cards.
    if "news-link" in text or "news-item" in text or "대표 기사" in text:
        return True
    return bool(re.search(r"<a[^>]+href=[\"']https?://", text, re.I | re.S))


def infer_report_json_path(html_path: Path) -> Path:
    date_match = DATE_RE.search(html_path.name)
    date = date_match.group(1) if date_match else html_path.stem
    return Path("data/reports") / f"{date}.report.json"


def report_json_allows_index(html_path: Path) -> bool:
    json_path = infer_report_json_path(html_path)
    if not json_path.exists():
        return False
    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
    except Exception:
        return False
    date_match = DATE_RE.search(html_path.name)
    target = date_match.group(1) if date_match else ""
    if not target:
        return False
    auto = data.get("automation") if isinstance(data.get("automation"), dict) else {}
    safe = auto.get("safetimes") if isinstance(auto.get("safetimes"), dict) else {}
    today_src = safe.get("today_source_file_date")
    prev_src = safe.get("previous_source_file_date")
    if today_src and today_src != target:
        return False
    if today_src and prev_src and today_src == prev_src:
        return False
    news = data.get("news_trend") if isinstance(data.get("news_trend"), dict) else {}
    articles = news.get("articles") if isinstance(news.get("articles"), list) else []
    valid_articles = [a for a in articles if isinstance(a, dict) and a.get("title") and a.get("url")]
    issues = data.get("issues") if isinstance(data.get("issues"), list) else []
    schedules = data.get("schedules") if isinstance(data.get("schedules"), list) else []
    return bool(valid_articles or issues or schedules)


def is_valid_report_html(text: str) -> Tuple[bool, str]:
    if not text:
        return False, "empty_html"
    if has_bad_phrase(text):
        return False, "bad_phrase"
    if not has_required_structure(text):
        return False, "missing_required_structure"
    if not has_article_block(text):
        return False, "missing_article_block"
    return True, "ok"


def read_report_meta(html_path: Path, *, strict_json: bool = False) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    date_match = DATE_RE.search(html_path.name)
    if not date_match:
        return None, "missing_date_in_filename"
    date = date_match.group(1)
    text = html_path.read_text(encoding="utf-8", errors="ignore")
    ok, reason = is_valid_report_html(text)
    if not ok:
        return None, reason
    if strict_json and not report_json_allows_index(html_path):
        return None, "report_json_validation_failed"
    title_match = TITLE_RE.search(text)
    header_date_match = HEADER_DATE_RE.search(text)
    title = strip_tags(title_match.group(1)) if title_match else f"Daily 유가 동향 — {date}"
    display_date = strip_tags(header_date_match.group(1)) if header_date_match else date
    return {
        "date": date,
        "displayDate": display_date,
        "title": title,
        "url": f"reports/{html_path.name}",
        "status": "발간",
        "fileName": html_path.name,
        "exists": True,
    }, None


def mirror_to_public_if_needed(out_path: Path, payload: Dict[str, Any]) -> None:
    # Some older dashboard variants probe public/report-index.json. Keep it in sync
    # only when the canonical output is docs/report-index.json.
    normalized = out_path.as_posix().replace("\\", "/")
    if normalized == "docs/report-index.json":
        public_path = Path("public/report-index.json")
        try:
            atomic_write_json(public_path, payload)
            print(f"[OK] public index 동기화 완료: {public_path}")
        except Exception as exc:
            print(f"[WARN] public index 동기화 실패: {exc}")


def main() -> int:
    args = parse_args()
    reports_dir = Path(args.reports_dir)
    out_path = Path(args.out)
    if not reports_dir.exists():
        print(f"[ERROR] reports 폴더가 없습니다: {reports_dir}")
        return 1

    reports: List[Dict[str, Any]] = []
    warnings: List[Dict[str, str]] = []
    for html_path in sorted(reports_dir.glob("*.html")):
        item, reason = read_report_meta(html_path, strict_json=args.strict_json)
        if item:
            reports.append(item)
        else:
            warnings.append({"fileName": html_path.name, "reason": reason or "unknown"})

    reports.sort(key=lambda item: item["date"], reverse=True)
    payload = {
        "schemaVersion": "1.1",
        "generatedAt": now_kst_text(),
        "count": len(reports),
        "latestDate": reports[0]["date"] if reports else "",
        "availableDates": sorted([item["date"] for item in reports]),
        "warnings": warnings,
        "reports": reports,
    }
    atomic_write_json(out_path, payload)
    mirror_to_public_if_needed(out_path, payload)
    print(f"[OK] report-index.json 생성 완료: {out_path}")
    print(f"[OK] 리포트 수: {len(reports)}")
    if warnings:
        print(f"[WARN] 제외 HTML 수: {len(warnings)}")
        for warning in warnings[:20]:
            print(f" - {warning['fileName']}: {warning['reason']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
