#!/usr/bin/env python3
"""Collect Korean National Assembly schedules without persisting the API key."""

from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests


API_NAME = "ALLSCHEDULE"
API_URL = f"https://open.assembly.go.kr/portal/openapi/{API_NAME}"
ROW_FIELDS = (
    "SCH_KIND", "SCH_CN", "SCH_DT", "SCH_TM", "CONF_DIV", "CMIT_NM",
    "CONF_SESS", "CONF_DGR", "EV_INST_NM", "EV_PLC",
)
KST = timezone(timedelta(hours=9))


class AssemblyAPIError(RuntimeError):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="열린국회정보 국회 일정 수집")
    dates = parser.add_mutually_exclusive_group(required=True)
    dates.add_argument("--date", help="수집일(YYYY-MM-DD)")
    dates.add_argument("--start", help="기간 시작일(YYYY-MM-DD)")
    parser.add_argument("--end", help="기간 종료일(YYYY-MM-DD, --start와 함께 사용)")
    parser.add_argument("--out-dir", default="data/assembly")
    parser.add_argument("--public-dir", default="public/assembly")
    parser.add_argument("--docs-dir", default="docs/assembly")
    parser.add_argument("--public-index", default="public/assembly-schedule-index.json")
    parser.add_argument("--docs-index", default="docs/assembly-schedule-index.json")
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--force-refresh", action="store_true", help="기존 월 캐시 무시")
    return parser.parse_args()


def parse_date(value: str) -> date:
    normalized = re.sub(r"[+\s./]+", "-", str(value or "").strip())
    try:
        return date.fromisoformat(normalized)
    except ValueError as exc:
        raise AssemblyAPIError(f"날짜는 YYYY-MM-DD 형식이어야 합니다: {value}") from exc


def requested_dates(args: argparse.Namespace) -> list[date]:
    if args.date:
        return [parse_date(args.date)]
    if not args.end:
        raise AssemblyAPIError("--start를 사용하면 --end도 필요합니다.")
    start, end = parse_date(args.start), parse_date(args.end)
    if start > end:
        raise AssemblyAPIError("--start는 --end보다 늦을 수 없습니다.")
    return [start + timedelta(days=offset) for offset in range((end - start).days + 1)]


def atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False
    ) as handle:
        handle.write(text)
        temp_path = Path(handle.name)
    temp_path.replace(path)


def decode_response(payload: dict[str, Any]) -> tuple[int, list[dict[str, Any]]]:
    if "RESULT" in payload:
        result = payload.get("RESULT") or {}
        if result.get("CODE") == "INFO-200":
            return 0, []
        raise AssemblyAPIError(f"국회 API 오류 {result.get('CODE', 'UNKNOWN')}: {result.get('MESSAGE', '')}")

    sections = payload.get(API_NAME)
    if not isinstance(sections, list):
        raise AssemblyAPIError(f"예상하지 못한 응답 구조: 최상위 {API_NAME} 배열 없음")

    total = 0
    rows: list[dict[str, Any]] = []
    for section in sections:
        if not isinstance(section, dict):
            continue
        head = section.get("head")
        if isinstance(head, list):
            for item in head:
                if isinstance(item, dict) and "list_total_count" in item:
                    total = int(item["list_total_count"] or 0)
                result = item.get("RESULT") if isinstance(item, dict) else None
                if isinstance(result, dict) and result.get("CODE") != "INFO-000":
                    raise AssemblyAPIError(
                        f"국회 API 오류 {result.get('CODE', 'UNKNOWN')}: {result.get('MESSAGE', '')}"
                    )
        if isinstance(section.get("row"), list):
            rows.extend(item for item in section["row"] if isinstance(item, dict))
    return total, rows


def fetch_month(session: requests.Session, api_key: str, month: str, timeout: int) -> dict[str, Any]:
    params = {
        "KEY": api_key,
        "Type": "json",
        "pIndex": 1,
        "pSize": 1000,
        "SCH_DT": month,
    }
    try:
        response = session.get(API_URL, params=params, timeout=timeout)
        response.raise_for_status()
        response_payload = response.json()
    except (requests.RequestException, ValueError):
        # requests 예외에는 인증키가 포함된 최종 URL이 들어갈 수 있으므로
        # 원래 예외를 연결하거나 출력하지 않는다.
        raise AssemblyAPIError("국회 API 요청 또는 응답 해석에 실패했습니다.") from None
    total, raw_rows = decode_response(response_payload)
    if total > len(raw_rows):
        raise AssemblyAPIError(f"월 일정이 API 단일 응답 한도({len(raw_rows)}건)를 초과했습니다.")
    rows = [{field: row.get(field) for field in ROW_FIELDS} for row in raw_rows]
    rows.sort(key=lambda item: (str(item.get("SCH_TM") or "99:99"), str(item.get("SCH_KIND") or ""), str(item.get("SCH_CN") or "")))
    return {
        "schemaVersion": "1.0",
        "source": "열린국회정보",
        "api": API_NAME,
        "month": month,
        "collectedAt": datetime.now(KST).isoformat(timespec="seconds"),
        "count": len(rows),
        "apiTotalCount": total,
        "fields": list(ROW_FIELDS),
        "items": rows,
    }


def valid_month_cache(path: Path, month: str) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if payload.get("month") != month or payload.get("api") != API_NAME or not isinstance(payload.get("items"), list):
        return None
    return payload


def should_refresh_month(month: str, today: date | None = None) -> bool:
    """Return whether a monthly cache can still change at the source.

    Committee meetings are often added only a few days—or hours—before they
    begin.  Reusing a cache for the current/future month therefore publishes a
    stale but apparently valid schedule.  Only completed past months are safe
    to reuse without an explicit refresh.
    """
    current_month = (today or datetime.now(KST).date()).strftime("%Y-%m")
    return month >= current_month


def daily_payload(month_payload: dict[str, Any], target: date) -> dict[str, Any]:
    date_text = target.isoformat()
    rows = [item for item in month_payload.get("items", []) if item.get("SCH_DT") == date_text]
    return {
        "schemaVersion": "1.0",
        "source": month_payload.get("source", "열린국회정보"),
        "api": API_NAME,
        "date": date_text,
        "monthCache": f"months/{date_text[:7]}.json",
        "collectedAt": month_payload.get("collectedAt", ""),
        "count": len(rows),
        "apiTotalCount": len(rows),
        "fields": list(ROW_FIELDS),
        "items": rows,
    }


def build_index(data_dir: Path) -> dict[str, Any]:
    schedules = []
    for path in sorted(data_dir.glob("????-??-??.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        date_text = str(payload.get("date") or path.stem)
        count = int(payload.get("count") or 0)
        if count <= 0:
            continue
        schedules.append({"date": date_text, "count": count, "url": f"assembly/{date_text}.json"})
    schedules.sort(key=lambda item: item["date"])
    return {
        "schemaVersion": "1.0",
        "generatedAt": datetime.now(KST).isoformat(timespec="seconds"),
        "count": sum(item["count"] for item in schedules),
        "availableDates": [item["date"] for item in schedules],
        "schedules": schedules,
    }


def main() -> int:
    args = parse_args()
    api_key = os.environ.get("ASSEMBLY_API_KEY", "").strip()
    if not api_key:
        raise AssemblyAPIError("ASSEMBLY_API_KEY 환경변수가 비어 있습니다.")

    dates = requested_dates(args)
    out_dir, public_dir, docs_dir = Path(args.out_dir), Path(args.public_dir), Path(args.docs_dir)
    months = sorted({target.strftime("%Y-%m") for target in dates})
    month_payloads: dict[str, dict[str, Any]] = {}
    with requests.Session() as session:
        for month in months:
            cache_path = out_dir / "months" / f"{month}.json"
            refresh = args.force_refresh or should_refresh_month(month)
            payload = None if refresh else valid_month_cache(cache_path, month)
            if payload is None:
                payload = fetch_month(session, api_key, month, args.timeout)
                atomic_write_json(cache_path, payload)
                print(f"[OK] 국회 월 캐시 수집 {month}: {payload['count']}건")
            else:
                print(f"[OK] 기존 국회 월 캐시 재사용 {month}: {payload['count']}건")
            month_payloads[month] = payload

    for target in dates:
        payload = daily_payload(month_payloads[target.strftime("%Y-%m")], target)
        filename = f"{target.isoformat()}.json"
        for directory in (out_dir, public_dir, docs_dir):
            atomic_write_json(directory / filename, payload)
        print(f"[OK] 국회 일정 {target.isoformat()}: {payload['count']}건")

    index = build_index(out_dir)
    atomic_write_json(Path(args.public_index), index)
    atomic_write_json(Path(args.docs_index), index)
    print(f"[OK] 국회 일정 인덱스: {len(index['availableDates'])}일 / {index['count']}건")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
