#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
merge_prices_into_report.py

오피넷 국제유가 JSON과 장기 history.json을 리포트용 JSON 초안에 반영하는 스크립트 v1.1
- 가격 카드: 당일 수집 JSON 기준
- 가격 추이 그래프: history.json이 있으면 2026년 이후 장기 이력 기준
- 값이 0인 가격은 제외
"""

from __future__ import annotations

import argparse
import json
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional


class MergePriceError(RuntimeError):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="오피넷 가격 JSON을 리포트 JSON에 반영")
    parser.add_argument("--date", required=True, help="기준일 YYYY-MM-DD")
    parser.add_argument("--report-dir", default="data/reports", help="리포트 JSON 폴더")
    parser.add_argument("--price-dir", default="data/prices", help="오피넷 가격 JSON 폴더")
    parser.add_argument("--history", default="data/prices/history.json", help="장기 가격 이력 JSON")
    parser.add_argument("--out", default="", help="출력 파일 경로. 비우면 입력 report JSON을 덮어씀")
    return parser.parse_args()


def read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise MergePriceError(f"파일을 찾을 수 없습니다: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise MergePriceError(f"JSON 파일을 읽을 수 없습니다: {path} / {exc}") from exc


def read_json_optional(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def atomic_write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=str(path.parent), delete=False,
                                     prefix=f".{path.name}.", suffix=".tmp") as tmp:
        tmp.write(text)
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)


def validate_price_data(price_data: Mapping[str, Any]) -> None:
    if not price_data.get("success", True):
        raise MergePriceError("오피넷 가격 수집 실패 JSON입니다.")
    if not price_data.get("crude", {}).get("cards"):
        raise MergePriceError("원유 가격 카드 데이터가 없습니다.")
    if not price_data.get("products", {}).get("cards"):
        raise MergePriceError("석유제품 가격 카드 데이터가 없습니다.")


def short_date(date_text: str) -> str:
    try:
        return f"{int(date_text[5:7])}/{int(date_text[8:10])}"
    except Exception:
        return date_text or ""


def point(date: str, value: Any) -> Optional[Dict[str, Any]]:
    try:
        number = float(value)
    except Exception:
        return None
    if number == 0:
        return None
    return {"date": date, "label": short_date(date), "value": round(number, 2)}


def build_series_from_history(history: Optional[Mapping[str, Any]], section: str, mapping: Mapping[str, str]) -> Dict[str, List[Dict[str, Any]]]:
    series = {label: [] for label in mapping.keys()}
    if not history:
        return series
    rows = history.get(section, {}) or {}
    for date in sorted(rows.keys()):
        values = rows.get(date, {}) or {}
        for label, source_key in mapping.items():
            p = point(date, values.get(source_key))
            if p:
                series[label].append(p)
    return series


def clean_series(series: Mapping[str, List[Mapping[str, Any]]]) -> Dict[str, List[Dict[str, Any]]]:
    cleaned: Dict[str, List[Dict[str, Any]]] = {}
    for label, points in series.items():
        cleaned[label] = []
        for item in points:
            p = point(str(item.get("date", "")), item.get("value"))
            if p:
                cleaned[label].append(p)
    return cleaned


def choose_chart_series(price_data: Mapping[str, Any], history: Optional[Mapping[str, Any]]):
    crude_history_series = build_series_from_history(history, "crude", {"Brent": "Brent", "WTI": "WTI", "Dubai": "Dubai"})
    product_history_series = build_series_from_history(history, "products", {"Gasoline": "Gasoline_92RON", "Diesel": "Diesel_0.001", "Naphtha": "Naphtha"})

    if sum(len(v) for v in crude_history_series.values()) > 0:
        crude_series = crude_history_series
        crude_source = "history.json"
    else:
        crude_series = clean_series(price_data.get("crude", {}).get("chart_series", {}) or {})
        crude_source = "daily price json"

    if sum(len(v) for v in product_history_series.values()) > 0:
        product_series = product_history_series
        product_source = "history.json"
    else:
        product_series = clean_series(price_data.get("products", {}).get("chart_series", {}) or {})
        product_source = "daily price json"

    return crude_series, product_series, crude_source, product_source


def chart_period_label(series: Mapping[str, List[Mapping[str, Any]]]) -> str:
    dates = []
    for points in series.values():
        for point_item in points:
            if point_item.get("date"):
                dates.append(str(point_item["date"]))
    if not dates:
        return ""
    dates = sorted(set(dates))
    return f"{short_date(dates[0])}~{short_date(dates[-1])}"


def normalize_crude_cards(cards: List[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    order = ["Brent", "WTI", "Dubai"]
    by_label = {str(card.get("label")): dict(card) for card in cards}
    result = []
    for label in order:
        card = by_label.get(label)
        if not card:
            continue
        result.append({"label": label, "value": card.get("value"), "change": card.get("change", 0), "direction": card.get("direction", "flat"), "unit": card.get("unit", "$/Bbl")})
    return result


def normalize_product_cards(cards: List[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    order = ["휘발유", "경유", "나프타"]
    by_label = {str(card.get("label")): dict(card) for card in cards}
    result = []
    for label in order:
        card = by_label.get(label)
        if not card:
            continue
        result.append({"label": label, "value": card.get("value"), "change": card.get("change", 0), "direction": card.get("direction", "flat"), "unit": card.get("unit", "$/Bbl")})
    return result


def update_price_section(report: Dict[str, Any], price_data: Mapping[str, Any], history: Optional[Mapping[str, Any]]) -> Dict[str, str]:
    crude = price_data["crude"]
    products = price_data["products"]
    crude_series, product_series, crude_source, product_source = choose_chart_series(price_data, history)

    report["prices"] = {
        "unit": "$/Bbl",
        "price_data_note": (
            "※ 오피넷 국제유가 메뉴에서 수집한 $/Bbl 기준 가격입니다. "
            "가격 추이 그래프는 2026년 이후 장기 이력을 사용하며, 값이 0인 가격은 제외했습니다."
        ),
        "crude": {
            "base_label": short_date(crude.get("latest_date", "")),
            "cards": normalize_crude_cards(crude.get("cards", [])),
            "chart_period_label": chart_period_label(crude_series),
            "chart_series": crude_series,
        },
        "products": {
            "base_label": short_date(products.get("latest_date", "")),
            "cards": normalize_product_cards(products.get("cards", [])),
            "chart_period_label": chart_period_label(product_series),
            "chart_series": product_series,
        },
    }
    return {"crude_chart_source": crude_source, "products_chart_source": product_source}


def update_summary(report: Dict[str, Any], price_data: Mapping[str, Any]) -> None:
    summary = report.setdefault("summary", [])
    while len(summary) < 3:
        summary.append({"type": "auto", "text": ""})

    crude_date = price_data.get("crude", {}).get("latest_date", "")
    product_date = price_data.get("products", {}).get("latest_date", "")
    sentence = (
        f"오피넷 국제유가 기준 최신 가격은 원유 {short_date(crude_date)}, "
        f"석유제품 {short_date(product_date)} 기준으로 반영함. "
        "그래프는 2026년 이후 이력을 사용하며, 값이 0인 가격은 제외."
    )
    existing = summary[0].get("text", "")
    if "오피넷 국제유가 기준 최신 가격" not in existing:
        summary[0]["text"] = (existing.rstrip() + " " + sentence).strip()


def update_sources_and_quality(report: Dict[str, Any], price_data: Mapping[str, Any], history: Optional[Mapping[str, Any]]) -> None:
    quality = report.setdefault("quality_control", {})
    notes = quality.setdefault("quality_notes", [])
    sources = quality.setdefault("sources", [])

    for note in [
        "오피넷 국제유가 데이터는 원유·석유제품 표의 $/Bbl 행을 기준으로 자동 반영했습니다.",
        "가격 추이 그래프는 2026년 이후 장기 이력을 사용하며, 값이 0인 가격은 제외했습니다.",
        "가격 데이터는 원유와 석유제품 각각의 최신 가격 일자가 다를 수 있으므로 기준일 라벨을 별도 표시합니다.",
    ]:
        if note not in notes:
            notes.append(note)

    if history and history.get("source_files"):
        note = "장기 가격 이력 출처 파일: " + json.dumps(history.get("source_files"), ensure_ascii=False)
        if note not in notes:
            notes.append(note)

    urls = price_data.get("source_urls", {})
    sources = [s for s in sources if not (s.get("type") == "price" and "오피넷" in s.get("name", ""))]
    sources.extend([
        {"name": "오피넷 국제유가 > 원유", "type": "price", "url": urls.get("crude", "")},
        {"name": "오피넷 국제유가 > 석유제품", "type": "price", "url": urls.get("products", "")},
    ])
    quality["sources"] = sources


def update_automation(report: Dict[str, Any], price_data: Mapping[str, Any], history: Optional[Mapping[str, Any]], chart_sources: Mapping[str, str]) -> None:
    report.setdefault("automation", {})
    report["automation"]["opinet_prices"] = {
        "source_schema_version": price_data.get("schema_version", ""),
        "source_date": price_data.get("date", ""),
        "collected_at": price_data.get("collected_at", ""),
        "crude_latest_date": price_data.get("crude", {}).get("latest_date", ""),
        "products_latest_date": price_data.get("products", {}).get("latest_date", ""),
        "history_schema_version": history.get("schema_version", "") if history else "",
        "history_period": history.get("period", {}) if history else {},
        "crude_chart_source": chart_sources.get("crude_chart_source", ""),
        "products_chart_source": chart_sources.get("products_chart_source", ""),
        "merged_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S KST"),
        "merge_script": "merge_prices_into_report.py v1.1",
        "needs_review": True,
    }


def merge_prices(report: Dict[str, Any], price_data: Mapping[str, Any], history: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    validate_price_data(price_data)
    chart_sources = update_price_section(report, price_data, history)
    update_summary(report, price_data)
    update_sources_and_quality(report, price_data, history)
    update_automation(report, price_data, history, chart_sources)
    return report


def main() -> int:
    args = parse_args()
    report_path = Path(args.report_dir) / f"{args.date}.report.json"
    price_path = Path(args.price_dir) / f"{args.date}.json"
    history_path = Path(args.history)
    out_path = Path(args.out) if args.out else report_path

    try:
        report = read_json(report_path)
        price_data = read_json(price_path)
        history = read_json_optional(history_path)
        merged = merge_prices(report, price_data, history)
        atomic_write_json(out_path, merged)
        print(f"[OK] 오피넷 가격 데이터 반영 완료: {out_path}")
        print(f"[OK] 원유 그래프 기간: {merged.get('prices', {}).get('crude', {}).get('chart_period_label', '')}")
        print(f"[OK] 제품 그래프 기간: {merged.get('prices', {}).get('products', {}).get('chart_period_label', '')}")
        return 0

    except Exception as exc:
        print(f"[ERROR] 오피넷 가격 데이터 반영 실패: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
