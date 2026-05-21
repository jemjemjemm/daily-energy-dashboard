#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ensure_report_draft.py

임의 날짜 리포트 JSON이 없을 때 안전하게 생성합니다.

우선순위
1. data/reports/YYYY-MM-DD.report.json이 이미 있으면 그대로 사용
2. data/schedules/YYYY-MM-DD.json이 있으면 build_report_draft_from_schedule.py가 만든 결과를 기대
3. 그래도 없으면 가격 중심 기본 리포트 JSON을 생성

목적
- 2026년 과거 어느 날짜를 선택해도 세이프타임즈 수집 실패 때문에 pipeline이 멈추지 않게 함
"""

from __future__ import annotations

import argparse
import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict


def parse_args():
    parser = argparse.ArgumentParser(description="리포트 JSON 안전 생성")
    parser.add_argument("--date", required=True)
    parser.add_argument("--out-dir", default="data/reports")
    parser.add_argument("--base-report", default="report_sample.json")
    return parser.parse_args()


def atomic_write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=str(path.parent), delete=False,
                                     prefix=f".{path.name}.", suffix=".tmp") as tmp:
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
        "report_version": "fallback-price-report-v1.0",
        "review_status": "가격 중심 자동생성 초안",
    }

    report["summary"] = [
        {
            "type": "price_only",
            "text": "해당 날짜의 세이프타임즈 일정 원문을 자동 확인하지 못해, 가격 데이터 중심 리포트로 생성했습니다."
        },
        {
            "type": "price_only",
            "text": "유가 및 석유제품 가격은 data/prices/history.json의 장기 이력을 기준으로 반영합니다."
        },
        {
            "type": "review_note",
            "text": "정책·일정·기사 요약은 원문 확인 후 보완이 필요합니다."
        }
    ]

    report["issues"] = []
    report["schedules"] = []
    report["news_trend"] = {
        "summary": "해당 날짜의 조간 신문 트렌드는 아직 자동 수집되지 않았습니다.",
        "articles": []
    }

    report["quality_control"] = {
        "quality_notes": [
            "세이프타임즈 일정 수집 실패 또는 일정 JSON 부재로 가격 중심 기본 리포트를 생성했습니다.",
            "정책·일정·기사 관련 내용은 원문 확인 후 보완해야 합니다.",
            "가격 그래프와 가격 카드는 history.json 또는 오피넷 수집 데이터 기준으로 후속 병합 단계에서 반영됩니다."
        ],
        "sources": []
    }

    report["automation"] = {
        "fallback_report": {
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S KST"),
            "reason": "missing schedule/report draft",
            "script": "ensure_report_draft.py"
        }
    }

    return report


def main() -> int:
    args = parse_args()
    out_path = Path(args.out_dir) / f"{args.date}.report.json"

    if out_path.exists():
        print(f"[OK] 기존 리포트 JSON 사용: {out_path}")
        return 0

    report = build_minimal_report(args.date, Path(args.base_report))
    atomic_write_json(out_path, report)

    print(f"[OK] 가격 중심 기본 리포트 JSON 생성: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
