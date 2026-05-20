#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
fetch_opinet_international_prices.py

오피넷 국제유가 자동 수집 스크립트 v1.0

수집 대상
1) 국제유가 > 원유
   - Dubai
   - Brent
   - WTI

2) 국제유가 > 석유제품
   - 휘발유(92RON)
   - 경유(0.001%)
   - 나프타

저장 파일
- data/prices/YYYY-MM-DD.json
- data/prices/history.json

기본 사용법
    python scripts/fetch_opinet_international_prices.py

특정 날짜명으로 저장
    python scripts/fetch_opinet_international_prices.py --date 2026-05-20

주의
- 오피넷 국제유가 메뉴의 HTML 표를 읽어 $/Bbl 행만 추출합니다.
- 원화 환산 행도 같은 표에 포함되어 있으므로, 값의 크기를 기준으로 $/Bbl 행만 필터링합니다.
- API Key는 향후 API 연동 대비로 OPINET_API_KEY 환경변수에서 읽지만, 이 HTML 수집 방식에서는 필수값이 아닙니다.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import requests
from bs4 import BeautifulSoup


CRUDE_URL = "https://www.opinet.co.kr/gloptotSelect.do"
PRODUCT_URL = "https://www.opinet.co.kr/glopopdSelect.do"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)

TIMEOUT = 25

CRUDE_COLUMNS = ["Dubai", "Brent", "WTI"]
PRODUCT_COLUMNS = [
    "Gasoline_95RON",
    "Gasoline_92RON",
    "Kerosene",
    "Diesel_0.001",
    "Diesel_0.05",
    "HSFO_180cst_3.5",
    "Naphtha",
]

REPORT_PRODUCT_ALIASES = {
    "휘발유": "Gasoline_92RON",
    "경유": "Diesel_0.001",
    "나프타": "Naphtha",
}


class OpinetPriceError(RuntimeError):
    """유가 데이터 수집 오류."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="오피넷 국제유가 원유/석유제품 자동 수집")
    parser.add_argument("--date", default="", help="저장 기준일 YYYY-MM-DD. 미지정 시 실행일")
    parser.add_argument("--out-dir", default="data/prices", help="저장 폴더. 기본값 data/prices")
    parser.add_argument("--no-history", action="store_true", help="history.json 갱신하지 않음")
    return parser.parse_args()


def today_string() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def normalize_target_date(value: str) -> str:
    if not value:
        return today_string()
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise OpinetPriceError("--date는 YYYY-MM-DD 형식이어야 합니다.") from exc
    return value


def fetch_html(url: str) -> str:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://www.opinet.co.kr/",
    }
    response = requests.get(url, headers=headers, timeout=TIMEOUT)
    response.raise_for_status()

    if not response.encoding or response.encoding.lower() == "iso-8859-1":
        response.encoding = response.apparent_encoding or "utf-8"

    return response.text


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def parse_korean_short_date(value: str) -> str:
    """
    26년05월19일 -> 2026-05-19
    2026년05월19일 -> 2026-05-19
    """
    match = re.search(r"(?P<year>\d{2,4})년\s*(?P<month>\d{1,2})월\s*(?P<day>\d{1,2})일", value)
    if not match:
        raise OpinetPriceError(f"날짜 형식을 읽을 수 없습니다: {value}")

    year = int(match.group("year"))
    if year < 100:
        year += 2000

    month = int(match.group("month"))
    day = int(match.group("day"))

    return f"{year:04d}-{month:02d}-{day:02d}"


def extract_price_rows(html: str, expected_values: int) -> List[Dict[str, Any]]:
    """
    오피넷 페이지의 텍스트에서 날짜 + 숫자열을 추출한다.

    원유 페이지 예:
      26년05월19일 1009.93 1052.29 1019.10  # 원화
      26년05월19일 106.80 111.28 107.77     # $/Bbl

    석유제품 페이지 예:
      26년05월19일 1336.74 ... 1050.12      # 원화
      26년05월19일 141.36 137.87 ... 111.05 # $/Bbl

    여기서는 expected_values 개수만큼 숫자가 있는 줄을 찾고,
    max(value) < 400 기준으로 $/Bbl 행을 선택한다.
    """
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text("\n", strip=True)
    lines = [normalize_text(line) for line in text.split("\n")]
    lines = [line for line in lines if line]

    rows: List[Dict[str, Any]] = []

    # 날짜로 시작하는 라인 또는 날짜가 포함된 라인에서 숫자 추출
    date_re = re.compile(r"\d{2,4}년\s*\d{1,2}월\s*\d{1,2}일")
    number_re = re.compile(r"-?\d+(?:\.\d+)?")

    for line in lines:
        date_match = date_re.search(line)
        if not date_match:
            continue

        date_text = date_match.group(0)
        numbers = [float(x) for x in number_re.findall(line[date_match.end():])]

        if len(numbers) != expected_values:
            continue

        # $/Bbl 행만 사용. 원화 행은 보통 1,000원대 이상.
        if numbers and max(numbers) >= 400:
            continue

        rows.append({
            "date": parse_korean_short_date(date_text),
            "values": numbers,
            "raw": line,
        })

    # 같은 날짜가 중복되면 뒤쪽 행 우선
    dedup: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        dedup[row["date"]] = row

    return sorted(dedup.values(), key=lambda item: item["date"])


def rows_to_series(rows: Sequence[Mapping[str, Any]], columns: Sequence[str]) -> Dict[str, List[Dict[str, Any]]]:
    series: Dict[str, List[Dict[str, Any]]] = {column: [] for column in columns}

    for row in rows:
        date = row["date"]
        values = row["values"]

        for column, value in zip(columns, values):
            if value is None:
                continue
            try:
                number = float(value)
            except (TypeError, ValueError):
                continue
            if not math.isfinite(number) or number == 0:
                continue

            series[column].append({
                "date": date,
                "label": f"{int(date[5:7])}/{int(date[8:10])}",
                "value": round(number, 2),
            })

    return series


def latest_from_series(series: Mapping[str, Sequence[Mapping[str, Any]]], preferred_columns: Sequence[str]) -> Tuple[str, Dict[str, float]]:
    latest_date = ""
    latest_values: Dict[str, float] = {}

    for column in preferred_columns:
        points = list(series.get(column, []))
        if not points:
            continue
        point = sorted(points, key=lambda item: item["date"])[-1]
        if not latest_date or point["date"] > latest_date:
            latest_date = point["date"]

    if not latest_date:
        raise OpinetPriceError("최신 유가 날짜를 찾지 못했습니다.")

    for column in preferred_columns:
        points = list(series.get(column, []))
        match = [point for point in points if point["date"] == latest_date]
        if match:
            latest_values[column] = float(match[-1]["value"])

    return latest_date, latest_values


def calc_change(series: Mapping[str, Sequence[Mapping[str, Any]]], column: str, latest_date: str) -> Optional[float]:
    points = sorted(series.get(column, []), key=lambda item: item["date"])
    dates = [point["date"] for point in points]
    if latest_date not in dates:
        return None

    idx = dates.index(latest_date)
    if idx <= 0:
        return None

    latest = float(points[idx]["value"])
    prev = float(points[idx - 1]["value"])
    return round(latest - prev, 2)


def build_cards(series: Mapping[str, Sequence[Mapping[str, Any]]], latest_date: str, columns: Sequence[str]) -> List[Dict[str, Any]]:
    cards = []

    for column in columns:
        points = [point for point in series.get(column, []) if point["date"] == latest_date]
        if not points:
            continue

        value = float(points[-1]["value"])
        change = calc_change(series, column, latest_date)

        if change is None:
            direction = "flat"
            change_value = 0
        elif change > 0:
            direction = "up"
            change_value = change
        elif change < 0:
            direction = "down"
            change_value = change
        else:
            direction = "flat"
            change_value = 0

        cards.append({
            "label": column,
            "value": round(value, 2),
            "change": round(change_value, 2),
            "direction": direction,
            "unit": "$/Bbl",
        })

    return cards


def build_report_product_cards(series: Mapping[str, Sequence[Mapping[str, Any]]], latest_date: str) -> List[Dict[str, Any]]:
    cards = []
    for korean_label, column in REPORT_PRODUCT_ALIASES.items():
        points = [point for point in series.get(column, []) if point["date"] == latest_date]
        if not points:
            continue

        value = float(points[-1]["value"])
        change = calc_change(series, column, latest_date)

        if change is None:
            direction = "flat"
            change_value = 0
        elif change > 0:
            direction = "up"
            change_value = change
        elif change < 0:
            direction = "down"
            change_value = change
        else:
            direction = "flat"
            change_value = 0

        cards.append({
            "label": korean_label,
            "source_column": column,
            "value": round(value, 2),
            "change": round(change_value, 2),
            "direction": direction,
            "unit": "$/Bbl",
        })

    return cards


def build_payload(target_date: str) -> Dict[str, Any]:
    crude_html = fetch_html(CRUDE_URL)
    product_html = fetch_html(PRODUCT_URL)

    crude_rows = extract_price_rows(crude_html, expected_values=3)
    product_rows = extract_price_rows(product_html, expected_values=7)

    if not crude_rows:
        raise OpinetPriceError("원유 가격 행을 찾지 못했습니다.")
    if not product_rows:
        raise OpinetPriceError("석유제품 가격 행을 찾지 못했습니다.")

    crude_series = rows_to_series(crude_rows, CRUDE_COLUMNS)
    product_series = rows_to_series(product_rows, PRODUCT_COLUMNS)

    crude_latest_date, crude_latest_values = latest_from_series(crude_series, CRUDE_COLUMNS)
    product_latest_date, product_latest_values = latest_from_series(
        product_series,
        ["Gasoline_92RON", "Diesel_0.001", "Naphtha"],
    )

    api_key_exists = bool(os.environ.get("OPINET_API_KEY"))

    return {
        "schema_version": "1.0",
        "date": target_date,
        "source_site": "오피넷",
        "category": "국제유가",
        "unit": "$/Bbl",
        "collected_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S KST"),
        "source_urls": {
            "crude": CRUDE_URL,
            "products": PRODUCT_URL,
        },
        "api": {
            "opinet_api_key_env": "OPINET_API_KEY",
            "api_key_provided": api_key_exists,
            "note": "국제유가 메뉴 데이터는 현재 HTML 표에서 추출합니다. API Key는 향후 공식 국제유가 API 확인 시 사용합니다.",
        },
        "crude": {
            "latest_date": crude_latest_date,
            "latest": {
                "Dubai": crude_latest_values.get("Dubai"),
                "Brent": crude_latest_values.get("Brent"),
                "WTI": crude_latest_values.get("WTI"),
            },
            "cards": build_cards(crude_series, crude_latest_date, ["Brent", "WTI", "Dubai"]),
            "chart_series": {
                "Brent": crude_series.get("Brent", []),
                "WTI": crude_series.get("WTI", []),
                "Dubai": crude_series.get("Dubai", []),
            },
            "rows": crude_rows,
        },
        "products": {
            "latest_date": product_latest_date,
            "latest": {
                "Gasoline_92RON": product_latest_values.get("Gasoline_92RON"),
                "Diesel_0.001": product_latest_values.get("Diesel_0.001"),
                "Naphtha": product_latest_values.get("Naphtha"),
            },
            "cards": build_report_product_cards(product_series, product_latest_date),
            "chart_series": {
                "Gasoline": product_series.get("Gasoline_92RON", []),
                "Diesel": product_series.get("Diesel_0.001", []),
                "Naphtha": product_series.get("Naphtha", []),
            },
            "rows": product_rows,
        },
        "quality": {
            "needs_review": False,
            "warnings": [],
            "notes": [
                "오피넷 국제유가 메뉴의 $/Bbl 행만 추출했습니다.",
                "원화 환산 행은 값의 크기 기준으로 제외했습니다.",
                "최신 일자는 원유와 석유제품 각각의 표에서 확인된 마지막 가격 일자입니다.",
            ],
        },
        "success": True,
    }


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


def update_history(history_path: Path, payload: Dict[str, Any]) -> None:
    """
    매일 수집한 가격을 history.json에 누적한다.
    같은 price date가 다시 들어오면 최신 값으로 덮어쓴다.
    """
    if history_path.exists():
        try:
            history = json.loads(history_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            history = {}
    else:
        history = {}

    history.setdefault("schema_version", "1.0")
    history.setdefault("updated_at", "")
    history.setdefault("unit", "$/Bbl")
    history.setdefault("crude", {})
    history.setdefault("products", {})

    for row in payload["crude"]["rows"]:
        history["crude"][row["date"]] = {
            "Dubai": row["values"][0],
            "Brent": row["values"][1],
            "WTI": row["values"][2],
        }

    for row in payload["products"]["rows"]:
        values = row["values"]
        history["products"][row["date"]] = {
            "Gasoline_92RON": values[1],
            "Diesel_0.001": values[3],
            "Naphtha": values[6],
        }

    history["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S KST")
    atomic_write_json(history_path, history)


def main() -> int:
    args = parse_args()
    target_date = normalize_target_date(args.date)
    out_dir = Path(args.out_dir)

    try:
        payload = build_payload(target_date)
        output_path = out_dir / f"{target_date}.json"
        atomic_write_json(output_path, payload)

        if not args.no_history:
            update_history(out_dir / "history.json", payload)

        print(f"[OK] 오피넷 국제유가 저장 완료: {output_path}")
        print(f"[OK] 원유 최신일: {payload['crude']['latest_date']} / {payload['crude']['latest']}")
        print(f"[OK] 제품 최신일: {payload['products']['latest_date']} / {payload['products']['latest']}")
        return 0

    except Exception as exc:
        error_path = out_dir / f"{target_date}.error.json"
        atomic_write_json(error_path, {
            "schema_version": "1.0",
            "date": target_date,
            "source_site": "오피넷",
            "category": "국제유가",
            "collected_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S KST"),
            "success": False,
            "error": str(exc),
            "quality": {
                "needs_review": True,
                "warnings": [
                    "오피넷 국제유가 수집 실패",
                    "사이트 구조 변경, 네트워크 오류, 표 형식 변경 여부 확인 필요",
                ],
            },
        })
        print(f"[ERROR] 오피넷 국제유가 수집 실패: {exc}")
        print(f"[ERROR] 실패 정보 저장: {error_path}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
