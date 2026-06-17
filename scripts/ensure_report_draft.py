#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ensure_report_draft.py v1.3

리포트 JSON이 없거나, 과거에 만들어진 빈 placeholder 리포트이면
가격 중심 기본 리포트로 보강합니다.

지원 인자:
- --date
- --out-dir
- --report-dir
- --base-report
- --refresh-fallback

핵심:
- 기존 파일이 있어도 issues/schedules/news_trend가 비어 있으면 갱신
- 기존 파일이 fallback 리포트이면 갱신
- 기존 파일이 5/19~5/21처럼 실제 일정/뉴스가 들어 있는 완성 리포트이면 보존
"""

from __future__ import annotations

import argparse
import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List


HOLIDAYS_2026 = {
    "2026-01-01", "2026-02-16", "2026-02-17", "2026-02-18",
    "2026-03-02", "2026-05-01", "2026-05-05", "2026-05-25",
    "2026-06-03", "2026-08-17", "2026-09-24", "2026-09-25", "2026-09-28",
    "2026-10-05", "2026-10-09", "2026-12-25",
}


def parse_args():
    parser = argparse.ArgumentParser(description="리포트 JSON 안전 생성/보강")
    parser.add_argument("--date", required=True, help="리포트 기준일 YYYY-MM-DD")
    parser.add_argument("--out-dir", default="", help="리포트 JSON 저장 폴더")
    parser.add_argument("--report-dir", default="", help="리포트 JSON 저장 폴더. --out-dir와 동일")
    parser.add_argument("--base-report", default="report_sample.json", help="기본 리포트 샘플 JSON")
    parser.add_argument("--refresh-fallback", action="store_true", help="빈 리포트/fallback 리포트를 보강")
    args = parser.parse_args()

    if not args.out_dir and args.report_dir:
        args.out_dir = args.report_dir
    if not args.out_dir:
        args.out_dir = "data/reports"
    return args


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


def read_json_optional(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def is_workday(value) -> bool:
    return value.weekday() < 5 and value.isoformat() not in HOLIDAYS_2026


def previous_workday(date_text: str):
    cur = datetime.strptime(date_text, "%Y-%m-%d").date() - timedelta(days=1)
    for _ in range(14):
        if is_workday(cur):
            return cur
        cur -= timedelta(days=1)
    return datetime.strptime(date_text, "%Y-%m-%d").date() - timedelta(days=1)


def source_url(data: Dict[str, Any]) -> str:
    return str(data.get("article_url") or data.get("url") or "")


def source_title(data: Dict[str, Any]) -> str:
    return str(data.get("title") or data.get("article_title") or "")


def schedule_candidate_count(data: Dict[str, Any]) -> int:
    items = data.get("items")
    if isinstance(items, list) and items:
        return len(items)

    body = str(data.get("raw_text") or data.get("body") or "")
    if not body.strip():
        return 0
    return len([line for line in body.splitlines() if line.strip()])


def set_if_missing(target: Dict[str, Any], key: str, value: Any) -> bool:
    if target.get(key) not in (None, ""):
        return False
    target[key] = value
    return True


def ensure_safetimes_metadata(report: Dict[str, Any], date_text: str, schedule_dir: Path = Path("data/schedules")) -> bool:
    previous_date_text = previous_workday(date_text).isoformat()
    today_schedule = read_json_optional(schedule_dir / f"{date_text}.json")
    previous_schedule = read_json_optional(schedule_dir / f"{previous_date_text}.json")

    report_meta = report.setdefault("report", {})
    automation = report.setdefault("automation", {})
    safetimes = automation.setdefault("safetimes", {})

    changed = False
    changed |= set_if_missing(report_meta, "report_date", date_text)
    changed |= set_if_missing(report_meta, "previous_source_date", previous_date_text)
    changed |= set_if_missing(safetimes, "today_source_file_date", date_text)
    changed |= set_if_missing(safetimes, "previous_source_file_date", previous_date_text)
    changed |= set_if_missing(safetimes, "today_source_schedule_candidate_count", schedule_candidate_count(today_schedule))
    changed |= set_if_missing(safetimes, "previous_source_schedule_candidate_count", schedule_candidate_count(previous_schedule))

    if today_schedule:
        changed |= set_if_missing(safetimes, "today_source_title", source_title(today_schedule))
        changed |= set_if_missing(safetimes, "today_source_url", source_url(today_schedule))
        changed |= set_if_missing(
            safetimes,
            "today_source_published_at",
            today_schedule.get("approved_date", "") or today_schedule.get("published_at", ""),
        )
    if previous_schedule:
        changed |= set_if_missing(safetimes, "previous_source_title", source_title(previous_schedule))
        changed |= set_if_missing(safetimes, "previous_source_url", source_url(previous_schedule))

    return changed


BAD_FALLBACK_PHRASES = [
    "원문 자동 매칭 실패",
    "가격 데이터 중심",
    "가격 중심 자동생성",
    "원문 데이터 없음",
    "데이터 없음",
    "일정 관련성 평가는",
    "후속 보완이 필요",
    "fallback",
]


def contains_bad_fallback_phrase(report: Dict[str, Any]) -> bool:
    try:
        text = json.dumps(report, ensure_ascii=False)
    except Exception:
        text = str(report)
    return any(phrase in text for phrase in BAD_FALLBACK_PHRASES)


def meaningful_text(value: Any) -> bool:
    if value is None:
        return False
    text = str(value).strip()
    return bool(text and text not in {"-", "없음", "None", "null"})


def has_meaningful_issues(report: Dict[str, Any]) -> bool:
    issues = report.get("issues", [])
    if not isinstance(issues, list) or not issues:
        return False
    for item in issues:
        if isinstance(item, dict) and (meaningful_text(item.get("title")) or meaningful_text(item.get("description"))):
            # 과거 fallback 안내 문구는 완성 이슈로 보지 않음
            title = str(item.get("title", ""))
            if "원문 데이터 없음" in title:
                return False
            return True
    return False


def has_meaningful_schedules(report: Dict[str, Any]) -> bool:
    schedules = report.get("schedules", [])
    if not isinstance(schedules, list) or not schedules:
        return False
    for item in schedules:
        if isinstance(item, dict) and meaningful_text(item.get("title")):
            title = str(item.get("title", ""))
            if "원문 데이터 없음" in title:
                return False
            return True
    return False


def has_meaningful_news(report: Dict[str, Any]) -> bool:
    news = report.get("news_trend", {})
    if not isinstance(news, dict):
        return False
    summary = str(news.get("summary", "") or news.get("summary_html", ""))
    articles = news.get("articles", [])
    if "원문 데이터" in summary or "아직" in summary:
        return False
    if meaningful_text(summary):
        return True
    if isinstance(articles, list):
        for article in articles:
            if isinstance(article, dict) and meaningful_text(article.get("title")):
                title = str(article.get("title", ""))
                if "데이터 없음" not in title:
                    return True
    return False


def is_fallback_or_empty_report(report: Dict[str, Any]) -> bool:
    if not report:
        return True

    if contains_bad_fallback_phrase(report):
        return True

    automation = report.get("automation", {}) if isinstance(report.get("automation"), dict) else {}
    report_meta = report.get("report", {}) if isinstance(report.get("report"), dict) else {}
    version = str(report_meta.get("report_version", ""))
    status = str(report_meta.get("review_status", ""))

    if automation.get("fallback_report") or "fallback" in version or "가격 중심" in status:
        return True

    # 실제 일정/뉴스가 하나라도 있으면 보존
    if has_meaningful_issues(report) or has_meaningful_schedules(report) or has_meaningful_news(report):
        return False

    # build_report_draft_from_schedule.py가 생성한 일정 기반 초안은
    # 기사 반영 전에 issues/schedules가 비어 있을 수 있다. 이 경우 가격 중심 fallback으로
    # 덮어쓰면 source metadata와 문체가 다시 깨지므로 보존한다.
    safetimes = automation.get("safetimes", {}) if isinstance(automation.get("safetimes"), dict) else {}
    if safetimes.get("today_source_file_date"):
        return False

    # issues/schedules/news가 모두 비어 있거나 placeholder이면 보강 대상
    return True


def date_labels(date_text: str):
    d = datetime.strptime(date_text, "%Y-%m-%d").date()
    prev = d - timedelta(days=1)
    weekdays = ["월", "화", "수", "목", "금", "토", "일"]
    display = f"{d.month}/{d.day}({weekdays[d.weekday()]})"
    prev_label = f"{prev.month}/{prev.day}({weekdays[prev.weekday()]})"
    today_label = display
    return display, prev_label, today_label


def build_minimal_report(date_text: str, base_report_path: Path) -> Dict[str, Any]:
    base = read_json_optional(base_report_path)
    display, prev_label, today_label = date_labels(date_text)

    report = base if isinstance(base, dict) and base else {}

    report["report"] = {
        **(report.get("report", {}) if isinstance(report.get("report"), dict) else {}),
        "report_title": "Daily Issue Report",
        "header_title": "Daily Issue Report",
        "report_badge": "정유 · 석유화학 · LNG",
        "report_date": date_text,
        "display_date": display,
        "previous_day_label": prev_label,
        "today_label": today_label,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S KST"),
        "report_version": "fallback-price-report-v1.3",
        "review_status": "가격 중심 자동생성 초안",
    }

    report["summary"] = [
        {
            "type": "price_only",
            "text": "해당 날짜의 일정·기사 원문 데이터가 없어 가격 데이터 중심 리포트로 생성."
        },
        {
            "type": "price_only",
            "text": "유가 및 석유제품 가격 카드는 기준일 전일 이하의 최신 history.json 데이터를 기준으로 반영합니다."
        },
        {
            "type": "review_note",
            "text": "정책·일정·기사 요약은 원문 데이터 확보 후 후속 보완 필요."
        }
    ]

    report["issues"] = [
        {
            "category": "데이터",
            "category_class": "data",
            "title": "전일 주요 이슈 원문 데이터 없음",
            "description": "주요 이슈 자동 작성에 필요한 일정·기사 데이터가 부족해 별도 이해관계자 동향을 작성하지 않음.",
            "grade": ""
        }
    ]

    report["schedules"] = [
        {
            "time": "-",
            "org": "데이터",
            "title": "금일 주요 일정 원문 데이터 없음",
            "relevance": "해당 날짜의 일정 원문을 확인하지 못해 일정 영향도 평가는 미작성."
        }
    ]

    report["news_trend"] = {
        "summary": "해당 날짜의 조간 신문 트렌드 원문 데이터가 없어 자동 요약 미작성. 가격 데이터 중심 리포트로 제공.",
        "articles": [
            {
                "title": "대표 기사 데이터 없음",
                "press": "자동 수집 미적용",
                "url": ""
            }
        ]
    }

    report["quality_control"] = {
        "quality_notes": [
            "일정 또는 기사 데이터 부족으로 기본 리포트 초안을 생성함.",
            "정책·일정·기사 관련 내용은 원문 확인 후 보완해야 합니다.",
            "가격 그래프와 가격 카드는 history.json 또는 오피넷 수집 데이터 기준으로 반영됩니다."
        ],
        "sources": [
            {
                "name": "장기 가격 이력 history.json",
                "type": "price-history",
                "url": ""
            },
            {
                "name": "오피넷 국제유가",
                "type": "price",
                "url": "https://www.opinet.co.kr/"
            }
        ]
    }

    report["automation"] = {
        **(report.get("automation", {}) if isinstance(report.get("automation"), dict) else {}),
        "fallback_report": {
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S KST"),
            "reason": "missing or empty schedule/news source data",
            "script": "ensure_report_draft.py v1.3",
            "scope": "price-centered report without fabricated issue/news content"
        }
    }

    return report


def main() -> int:
    args = parse_args()
    out_path = Path(args.out_dir) / f"{args.date}.report.json"

    existing = read_json_optional(out_path)

    if existing and not args.refresh_fallback:
        if ensure_safetimes_metadata(existing, args.date):
            atomic_write_json(out_path, existing)
            print(f"[OK] source metadata patched: {out_path}")
        print(f"[OK] 기존 리포트 JSON 사용: {out_path}")
        return 0

    if existing and args.refresh_fallback and not is_fallback_or_empty_report(existing):
        if ensure_safetimes_metadata(existing, args.date):
            atomic_write_json(out_path, existing)
            print(f"[OK] source metadata patched: {out_path}")
        print(f"[OK] 실제 이슈/일정/뉴스가 있는 기존 리포트 보존: {out_path}")
        return 0

    if existing and args.refresh_fallback:
        print(f"[INFO] 빈 리포트 또는 fallback 리포트를 보강합니다: {out_path}")

    report = build_minimal_report(args.date, Path(args.base_report))
    ensure_safetimes_metadata(report, args.date)
    atomic_write_json(out_path, report)

    print(f"[OK] 가격 중심 기본 리포트 JSON 생성/갱신: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
