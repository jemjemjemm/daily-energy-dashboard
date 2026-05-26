#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_html_report.py

Daily Energy Dashboard report JSON을 모바일 HTML 리포트로 렌더링합니다.

중요 운영 원칙
- 뉴스 수집, 일정 파싱, 가격 병합, 백필 로직은 이 파일에서 변경하지 않습니다.
- 이 파일은 data/reports/YYYY-MM-DD.report.json -> docs/reports/YYYY-MM-DD.html 렌더링만 담당합니다.
- 기존 자동화 호출 방식(--date --report-dir --out-dir)과 단일 파일 호출 방식(--input --output)을 모두 지원합니다.
- HTML 생성 단계에서 인자 불일치로 전체 백필이 중단되지 않도록 CLI 호환성을 유지합니다.
"""
from __future__ import annotations

import argparse
import html
import json
import math
import re
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

CRUDE_KEYS = ["Brent", "WTI", "Dubai"]
PRODUCT_KEYS = ["Gasoline", "Diesel", "Naphtha"]
CRUDE_COLORS = {"Brent": "#1A6FD4", "WTI": "#E24B4A", "Dubai": "#1D9E75"}
PRODUCT_COLORS = {"Gasoline": "#1A6FD4", "Diesel": "#E24B4A", "Naphtha": "#1D9E75"}
PRODUCT_DISPLAY = {"Gasoline": "Gasoline", "Diesel": "Diesel", "Naphtha": "Naphtha"}

BAD_REPORT_PHRASES = [
    "자동 추출된 일정 항목이 없습니다",
    "본문 구조 확인 및 수동 검수가 필요합니다",
    "원문 자동 매칭 실패",
    "주요일정 원문 데이터 미확보",
    "원문 데이터 없음",
    "데이터 없음",
    "가격 데이터 중심 리포트",
    "가격 중심 자동생성",
    "Data 없음",
    "No data",
    "정유·석유화학·LNG 관련 조간 기사 후보를 찾지 못했습니다",
    "조간 기사 후보를 찾지 못했습니다",
    "자동 수집된 대표 기사 없음",
    "대표 기사 데이터가 아직 없습니다",
    "대표 기사 미확인",
    "기준일 조간 기준 주요 보도 없음",
    "기준일 조간 기준 정유·석유화학·LNG 관련 대표 기사 미확인",
    "A 직접",
    "B 간접",
    "C 참고",
]

REPORT_STYLE_REPLACEMENTS = [
    ("했습니다.", "함."),
    ("하였습니다.", "함."),
    ("되었습니다.", "됨."),
    ("됩니다.", "됨."),
    ("입니다.", "임."),
    ("필요합니다.", "필요."),
    ("가능합니다.", "가능."),
    ("확인됩니다.", "확인."),
    ("확인했습니다.", "확인."),
    ("보도했습니다.", "보도."),
    ("분석했습니다.", "분석."),
    ("전망했습니다.", "전망."),
    ("지적했습니다.", "지적."),
    ("강조했습니다.", "강조."),
    ("밝혔습니다.", "밝힘."),
    ("활용하시기 바랍니다.", "활용 필요."),
]

STYLE = r"""
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700&display=swap');
*{box-sizing:border-box}body{margin:0;padding:16px;background:#F4F5F7;color:#1A1A1A;font-family:'Noto Sans KR',sans-serif;font-size:14px;line-height:1.6}.container{max-width:480px;margin:0 auto}.header{background:#0A2444;color:#fff;padding:18px 16px 14px;border-radius:12px 12px 0 0}.header-top{display:flex;justify-content:space-between;gap:12px}.header-title{font-size:20px;font-weight:700}.header-date{font-size:12px;color:rgba(255,255,255,.58);margin-top:3px}.header-badge{font-size:11px;background:rgba(255,255,255,.12);border-radius:20px;padding:4px 10px;height:fit-content;white-space:nowrap}.section{background:#fff;border:1px solid #E5E7EB;border-radius:12px;margin:10px 0;overflow:hidden}.section-header{display:flex;align-items:center;gap:8px;padding:11px 16px;border-bottom:1px solid #E5E7EB;background:#F8F9FA}.section-num{font-size:11px;font-weight:700;color:#fff;background:#0A2444;border-radius:4px;padding:2px 7px;min-width:24px;text-align:center}.section-title{font-size:14px;font-weight:700}.summary-body,.news-body{padding:14px 16px}.summary-item{display:flex;gap:10px;padding:8px 0;border-bottom:1px solid #F0F0F0;font-size:13px;line-height:1.65}.summary-item:last-child{border-bottom:none}.summary-dot{flex:0 0 6px;width:6px;height:6px;border-radius:50%;background:#1A6FD4;margin-top:8px}.price-section-label{font-size:12px;font-weight:500;color:#666;padding:12px 16px 6px}.price-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;padding:0 16px 14px}.price-card{background:#F8F9FA;border-radius:8px;padding:10px 8px;text-align:center}.price-label{font-size:11px;color:#666;margin-bottom:4px}.price-value{font-size:18px;font-weight:700;line-height:1}.price-unit{font-size:10px;color:#999;margin-top:2px}.price-change{font-size:11px;margin-top:3px}.up{color:#C0392B}.down{color:#0A7B4E}.flat{color:#888}.divider{height:1px;background:#F0F0F0;margin:0 16px 4px}.chart-wrap{padding:12px 14px;position:relative}.chart-legend{display:flex;flex-wrap:wrap;gap:12px;margin-bottom:10px;font-size:12px;color:#666}.legend-item{display:flex;align-items:center;gap:5px}.legend-dot{width:12px;height:3px;border-radius:2px}.chart-box{position:relative;width:100%;min-height:245px;touch-action:pan-y;-webkit-user-select:none;user-select:none;overflow:visible}.chart-svg{width:100%;height:auto;display:block;overflow:visible}.tooltip{position:absolute;z-index:20;display:none;min-width:132px;max-width:215px;background:rgba(10,36,68,.96);color:#fff;border-radius:8px;padding:8px 10px;font-size:11px;line-height:1.45;pointer-events:none;box-shadow:0 6px 18px rgba(0,0,0,.18)}.tooltip .date{font-weight:700;margin-bottom:4px}.tooltip-row{display:flex;justify-content:space-between;gap:12px}.issue-list,.schedule-list{padding:10px 12px}.issue-card{background:#F8F9FA;border-radius:8px;padding:12px 14px;margin-bottom:8px;border-left:3px solid #1A6FD4}.issue-card:last-child{margin-bottom:0}.issue-tag{display:inline-block;font-size:10px;font-weight:700;background:#E6F1FB;color:#185FA5;border-radius:3px;padding:2px 6px;margin-bottom:6px}.issue-title{font-size:13px;font-weight:700;margin-bottom:5px;line-height:1.5}.issue-desc{font-size:12px;color:#444;line-height:1.65}.issue-links{margin-top:9px;display:flex;flex-direction:column;gap:4px;font-size:11px}.issue-links a{color:#0A2444;text-decoration:underline;word-break:break-all}.issue-links span{color:#777}.issue-links .link-note{color:#777;font-size:10.5px;line-height:1.45}.schedule-row{display:flex;align-items:flex-start;gap:8px;padding:9px 0;border-bottom:1px solid #F0F0F0}.schedule-row:last-child{border-bottom:none}.schedule-time{flex:0 0 38px;font-size:11px;font-weight:700;color:#185FA5;margin-top:1px}.schedule-org{flex:0 0 48px;font-size:10px;background:#F0F1F3;border:1px solid #E0E0E0;border-radius:3px;padding:1px 4px;color:#555;text-align:center}.schedule-main{flex:1;font-size:12px;line-height:1.5}.schedule-rel{font-size:11px;color:#777;margin-top:2px}.note{padding:0 16px 14px;font-size:11px;color:#999}.news-trend{font-size:13px;line-height:1.75;margin-bottom:14px}.news-trend strong{font-weight:700;color:#0A2444}.news-separator{height:1px;background:#F0F0F0;margin:12px 0}.news-links-title{font-size:11px;font-weight:700;color:#999;letter-spacing:.5px;margin-bottom:8px}.news-link{display:block;padding:9px 0;border-bottom:1px solid #F0F0F0;text-decoration:none;color:inherit}.news-link-title{font-size:13px;font-weight:600;color:#0A2444;line-height:1.45;text-decoration:underline}.news-link-press{font-size:11px;color:#888;margin:2px 0}.news-link-desc{font-size:11px;color:#555;line-height:1.55}.news-url{font-size:10px;color:#999;word-break:break-all;margin-top:4px}.fact-note{font-size:11px;color:#888;background:#F8F9FA;border-top:1px solid #E5E7EB;padding:10px 16px}.footer{text-align:center;padding:12px;font-size:11px;color:#aaa;border-top:1px solid #E5E7EB;margin-top:4px}@media(max-width:430px){body{padding:10px}.header-title{font-size:18px}.header-badge{font-size:10px;padding:4px 8px}.section-header{padding:10px 12px}.summary-body,.news-body{padding:12px}.price-grid{gap:6px;padding:0 12px 12px}.price-card{padding:9px 4px}.price-value{font-size:16px}.chart-wrap{padding:10px 8px}.chart-box{min-height:230px}.chart-legend{gap:8px;font-size:11px;margin-left:4px}.schedule-org{flex-basis:42px}.tooltip{font-size:10.5px;min-width:124px}}
""".strip()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Daily 유가 동향 HTML 리포트 생성")
    parser.add_argument("--date", help="기준일 YYYY-MM-DD")
    parser.add_argument("--report-dir", default="data/reports", help="리포트 JSON 디렉터리")
    parser.add_argument("--out-dir", default="docs/reports", help="HTML 출력 디렉터리")
    parser.add_argument("--input", help="입력 report.json 경로. 지정 시 --date/--report-dir보다 우선")
    parser.add_argument("--output", help="출력 html 경로. 지정 시 --date/--out-dir보다 우선")
    return parser.parse_args()


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def fmt(value: Any) -> str:
    try:
        n = float(value)
    except Exception:
        return "-"
    if not math.isfinite(n) or n == 0:
        return "-"
    return f"{n:.2f}"


def clean_text(value: Any, *, keep_html: bool = False) -> str:
    text = "" if value is None else str(value)
    if not keep_html:
        text = re.sub(r"<[^>]+>", " ", text)
    for phrase in BAD_REPORT_PHRASES:
        text = text.replace(phrase, "")
    text = re.sub(r"\s+", " ", text).strip()
    for old, new in REPORT_STYLE_REPLACEMENTS:
        text = text.replace(old, new)
    text = re.sub(r"\s+([.,])", r"\1", text)
    return text.strip()


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=str(path.parent), delete=False, prefix=f".{path.name}.", suffix=".tmp") as tmp:
        tmp.write(text)
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"입력 JSON을 찾을 수 없습니다: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_paths(args: argparse.Namespace) -> tuple[Path, Path, str]:
    if args.input:
        input_path = Path(args.input)
        date_text = args.date or input_path.name.split(".report.json")[0]
    else:
        if not args.date:
            raise SystemExit("--date 또는 --input 중 하나는 필요합니다.")
        date_text = args.date
        input_path = Path(args.report_dir) / f"{date_text}.report.json"

    if args.output:
        output_path = Path(args.output)
    else:
        output_path = Path(args.out_dir) / f"{date_text}.html"
    return input_path, output_path, date_text


def safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def report_date_for_title(report: Mapping[str, Any], fallback: str) -> str:
    meta = safe_dict(report.get("report"))
    return clean_text(meta.get("display_date")) or fallback


def weekday_ko(date_text: str) -> str:
    try:
        d = datetime.strptime(date_text, "%Y-%m-%d")
        return "월화수목금토일"[d.weekday()]
    except Exception:
        return ""


def compact_date(date_text: str) -> str:
    try:
        d = datetime.strptime(date_text, "%Y-%m-%d")
        return f"{d.year}년 {d.month}월 {d.day}일 ({weekday_ko(date_text)})"
    except Exception:
        return date_text


def section(num: int, title: str, body: str, extra: str = "") -> str:
    return f'''<div class="section"><div class="section-header"><span class="section-num">{num}</span><span class="section-title">{esc(title)}</span></div>{body}{extra}</div>'''


def item_blob(item: Mapping[str, Any]) -> str:
    return " ".join(str(v) for v in item.values())


def is_bad_item(item: Mapping[str, Any]) -> bool:
    blob = item_blob(item)
    return any(p in blob for p in BAD_REPORT_PHRASES)


def render_summary(report: Mapping[str, Any]) -> str:
    rows: list[str] = []
    for item in safe_list(report.get("summary")):
        if not isinstance(item, Mapping) or is_bad_item(item):
            continue
        text = clean_text(item.get("text") or item.get("summary") or item.get("description"))
        if text:
            rows.append(f'''<div class="summary-item"><div class="summary-dot"></div><div>{esc(text)}</div></div>''')
        if len(rows) >= 3:
            break
    if not rows:
        rows.append('''<div class="summary-item"><div class="summary-dot"></div><div>기준일 주요 요약 미확인</div></div>''')
    return '<div class="summary-body">' + "\n".join(rows) + '</div>'


def render_price_cards(cards: Sequence[Mapping[str, Any]]) -> str:
    rows: list[str] = []
    for c in cards:
        if not isinstance(c, Mapping):
            continue
        direction = str(c.get("direction") or "flat")
        cls = direction if direction in {"up", "down", "flat"} else "flat"
        symbol = {"up": "▲", "down": "▼", "flat": "－"}.get(cls, "－")
        value_text = fmt(c.get("value"))
        try:
            change = abs(float(c.get("change") or 0))
        except Exception:
            change = 0.0
        change_text = "-" if value_text == "-" else f"{symbol} {fmt(change)}"
        rows.append(f'''<div class="price-card"><div class="price-label">{esc(c.get("label"))}</div><div class="price-value">{value_text}</div><div class="price-unit">{esc(c.get("unit") or "$/Bbl")}</div><div class="price-change"><span class="{cls}">{esc(change_text)}</span></div></div>''')
    while len(rows) < 3:
        rows.append('''<div class="price-card"><div class="price-label">-</div><div class="price-value">-</div><div class="price-unit">$/Bbl</div><div class="price-change"><span class="flat">-</span></div></div>''')
    return '<div class="price-grid">' + "\n".join(rows[:3]) + '</div>'


def render_price_section(report: Mapping[str, Any]) -> str:
    prices = safe_dict(report.get("prices"))
    crude = safe_dict(prices.get("crude"))
    products = safe_dict(prices.get("products"))
    note = clean_text(prices.get("price_data_note"))
    body = []
    body.append(f'''<div class="price-section-label">원유 ($/Bbl) — {esc(crude.get("base_label") or "-")} 기준</div>''')
    body.append(render_price_cards(safe_list(crude.get("cards"))))
    body.append('<div class="divider"></div>')
    body.append(f'''<div class="price-section-label">석유제품 ($/Bbl) — {esc(products.get("base_label") or "-")} 기준</div>''')
    body.append(render_price_cards(safe_list(products.get("cards"))))
    if note:
        body.append(f'''<div class="note">{esc(note)}</div>''')
    return "\n".join(body)


def get_series_dates(series: Mapping[str, Sequence[Mapping[str, Any]]]) -> list[str]:
    dates = set()
    for points in series.values():
        for p in safe_list(points):
            if isinstance(p, Mapping) and p.get("date"):
                dates.add(str(p.get("date")))
    return sorted(dates)


def get_series_values(series: Mapping[str, Sequence[Mapping[str, Any]]]) -> list[float]:
    values: list[float] = []
    for points in series.values():
        for p in safe_list(points):
            if not isinstance(p, Mapping):
                continue
            try:
                v = float(p.get("value"))
            except Exception:
                continue
            if math.isfinite(v) and v != 0:
                values.append(v)
    return values


def date_label(date_text: str) -> str:
    try:
        d = datetime.strptime(date_text, "%Y-%m-%d")
        return f"{d.month}/{d.day}"
    except Exception:
        return date_text


def render_legend(keys: Sequence[str], colors: Mapping[str, str], display: Mapping[str, str] | None = None) -> str:
    rows = []
    for key in keys:
        rows.append(f'''<div class="legend-item"><div class="legend-dot" style="background:{esc(colors.get(key, '#777'))}"></div>{esc((display or {}).get(key, key))}</div>''')
    return '<div class="chart-legend">' + "".join(rows) + '</div>'


def chart_rows_for_js(series: Mapping[str, Sequence[Mapping[str, Any]]], keys: Sequence[str]) -> list[dict[str, Any]]:
    dates = get_series_dates(series)
    rows = {d: {"date": d, "label": date_label(d)} for d in dates}
    for key in keys:
        for p in safe_list(series.get(key)):
            if not isinstance(p, Mapping):
                continue
            d = str(p.get("date") or "")
            if d not in rows:
                continue
            try:
                v = float(p.get("value"))
            except Exception:
                v = None
            rows[d][key] = v if v is not None and math.isfinite(v) and v != 0 else None
    for d in dates:
        for key in keys:
            rows[d].setdefault(key, None)
    return [rows[d] for d in dates]


def render_chart_svg(series: Mapping[str, Sequence[Mapping[str, Any]]], keys: Sequence[str], colors: Mapping[str, str], line_id: str) -> str:
    dates = get_series_dates(series)
    values = get_series_values(series)
    if not dates or not values:
        return '<div class="note">표시 가능한 그래프 데이터 없음</div>'

    lo, hi = min(values), max(values)
    if lo == hi:
        lo -= 1
        hi += 1
    pad = max((hi - lo) * 0.12, 1)
    lo = max(0, lo - pad)
    hi += pad

    width, height = 440, 230
    left, right, top, bottom = 38, 430, 12, 198
    plot_w, plot_h = right - left, bottom - top
    idx_by_date = {d: i for i, d in enumerate(dates)}

    def x_at(idx: int) -> float:
        return left + (plot_w * idx / max(len(dates) - 1, 1))

    def y_at(v: float) -> float:
        return bottom - ((v - lo) / (hi - lo)) * plot_h

    parts: list[str] = [f'<svg aria-label="가격 추이 그래프" class="chart-svg" preserveAspectRatio="xMidYMid meet" role="img" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">']
    for i in range(6):
        yy = bottom - plot_h * i / 5
        label = lo + (hi - lo) * i / 5
        parts.append(f'<line stroke="rgba(0,0,0,0.07)" stroke-width="1" x1="{left}" x2="{right}" y1="{yy:.1f}" y2="{yy:.1f}"></line>')
        parts.append(f'<text fill="#888" font-size="9" text-anchor="end" x="34" y="{yy+3:.1f}">{label:.0f}</text>')

    tick_idxs = sorted({0, len(dates) - 1, max(0, len(dates) // 3), max(0, (len(dates) * 2) // 3)})
    for i in tick_idxs:
        parts.append(f'<text fill="#888" font-size="9" text-anchor="middle" x="{x_at(i):.1f}" y="221">{esc(date_label(dates[i]))}</text>')

    for key in keys:
        points = []
        for p in safe_list(series.get(key)):
            if not isinstance(p, Mapping):
                continue
            d = str(p.get("date") or "")
            if d not in idx_by_date:
                continue
            try:
                v = float(p.get("value"))
            except Exception:
                continue
            if not math.isfinite(v) or v == 0:
                continue
            points.append(f'{x_at(idx_by_date[d]):.1f},{y_at(v):.1f}')
        if points:
            parts.append(f'<polyline points="{" ".join(points)}" fill="none" stroke="{esc(colors.get(key, "#777"))}" stroke-linecap="round" stroke-linejoin="round" stroke-width="2"></polyline>')

    parts.append(f'<line id="{esc(line_id)}" opacity="0" stroke="#0A2444" stroke-width="1" x1="{left}" x2="{left}" y1="{top}" y2="{bottom}"></line>')
    parts.append(f'<rect fill="transparent" height="{plot_h}" width="{plot_w}" x="{left}" y="{top}"></rect>')
    parts.append('</svg>')
    return "\n".join(parts)


def chart_period_label(series: Mapping[str, Sequence[Mapping[str, Any]]], fallback: str = "") -> str:
    dates = get_series_dates(series)
    if len(dates) >= 2:
        return f"{date_label(dates[0])} ~ {date_label(dates[-1])}"
    return fallback


def render_chart_section(num: int, title_prefix: str, series: Mapping[str, Sequence[Mapping[str, Any]]], keys: Sequence[str], colors: Mapping[str, str], display: Mapping[str, str] | None, chart_id: str, tip_id: str, line_id: str, period_fallback: str = "") -> str:
    period = chart_period_label(series, period_fallback)
    title = f"{title_prefix} ({period})" if period else title_prefix
    body = (
        '<div class="chart-wrap">'
        + render_legend(keys, colors, display)
        + f'<div class="chart-box" id="{esc(chart_id)}">'
        + render_chart_svg(series, keys, colors, line_id)
        + f'<div class="tooltip" id="{esc(tip_id)}"></div></div></div>'
    )
    return section(num, title, body)


def normalize_links(item: Mapping[str, Any]) -> list[dict[str, str]]:
    raw = item.get("links") or item.get("related_links") or []
    rows: list[dict[str, str]] = []
    if isinstance(raw, list):
        for link in raw[:3]:
            if isinstance(link, Mapping):
                url = str(link.get("url") or "").strip()
                label = clean_text(link.get("label") or link.get("title") or "관련 자료")
                note = clean_text(link.get("note") or link.get("description") or "")
                if url and label:
                    rows.append({"url": url, "label": label, "note": note})
    return rows


def render_issues(report: Mapping[str, Any]) -> str:
    rows: list[str] = []
    for item in safe_list(report.get("issues")):
        if not isinstance(item, Mapping) or is_bad_item(item):
            continue
        title = clean_text(item.get("title"))
        desc = clean_text(item.get("description") or item.get("summary") or item.get("relevance"))
        category = clean_text(item.get("category") or item.get("tag") or "정책")
        if not title:
            continue
        link_html = ""
        links = normalize_links(item)
        if links:
            link_parts = ['<div class="issue-links"><span>관련 링크</span>']
            for link in links:
                link_parts.append(f'<a href="{esc(link["url"])}" rel="noopener" target="_blank">{esc(link["label"])}</a>')
                if link.get("note"):
                    link_parts.append(f'<div class="link-note">{esc(link["note"])}</div>')
            link_parts.append('</div>')
            link_html = "".join(link_parts)
        rows.append(f'''<div class="issue-card"><div class="issue-tag">{esc(category)}</div><div class="issue-title">{esc(title)}</div><div class="issue-desc">{esc(desc)}</div>{link_html}</div>''')
    if not rows:
        rows.append('''<div class="issue-card"><div class="issue-tag">확인</div><div class="issue-title">주요 이해관계자 동향 미확인</div><div class="issue-desc">전일 기준 정유·석유화학·LNG 업계 관련성이 높은 주요 동향 미확인</div></div>''')
    fact_note = '<div class="fact-note">※ 관련 링크가 없는 항목은 일정·보도자료 원문 확인 범위 내에서 작성. 업계 영향 평가는 작성자 해석</div>'
    return '<div class="issue-list">' + "\n".join(rows) + '</div>' + fact_note


def render_schedules(report: Mapping[str, Any], today_label: str) -> str:
    rows: list[str] = []
    for item in safe_list(report.get("schedules")):
        if not isinstance(item, Mapping) or is_bad_item(item):
            continue
        time = clean_text(item.get("time")) or "-"
        org = clean_text(item.get("org") or item.get("organization")) or "정부"
        title = clean_text(item.get("title") or item.get("event"))
        rel = clean_text(item.get("relevance") or item.get("description"))
        if not title:
            continue
        rows.append(f'''<div class="schedule-row"><div class="schedule-time">{esc(time)}</div><div class="schedule-org">{esc(org[:8])}</div><div class="schedule-main"><div>{esc(title)}</div>{f'<div class="schedule-rel">{esc(rel)}</div>' if rel else ''}</div></div>''')
    if not rows:
        rows.append('''<div class="schedule-row"><div class="schedule-time">-</div><div class="schedule-org">확인</div><div class="schedule-main"><div>금일 주요 일정 미확인</div><div class="schedule-rel">세부 일정 데이터 확인 필요</div></div></div>''')
    return '<div class="schedule-list">' + "\n".join(rows) + f'</div><div class="note">※ 위 일정은 제공된 일정 텍스트 기준. 영향도는 보고서 작성 목적의 해석</div>'


def render_news(report: Mapping[str, Any], today_label: str) -> str:
    news = safe_dict(report.get("news_trend"))
    articles: list[dict[str, str]] = []
    for item in safe_list(news.get("articles")):
        if not isinstance(item, Mapping) or is_bad_item(item):
            continue
        title = clean_text(item.get("title"))
        url = str(item.get("url") or "").strip()
        press = clean_text(item.get("press") or item.get("source") or item.get("media"))
        summary = clean_text(item.get("summary") or item.get("description"))
        published = clean_text(item.get("published_at_kst") or item.get("published_at") or item.get("date"))
        if title and url and "오늘의 주요일정" not in title:
            articles.append({"title": title, "url": url, "press": press, "summary": summary, "published": published})
        if len(articles) >= 3:
            break

    summary_html = news.get("summary_html")
    if summary_html:
        # 저장된 summary_html은 신뢰하되 위험 태그는 제거하고 br/strong만 의미 보존.
        raw = str(summary_html).replace("<br/>", "\n").replace("<br>", "\n")
        raw = re.sub(r"</?strong>", "**", raw)
        raw = clean_text(raw, keep_html=False)
    else:
        raw = clean_text(news.get("summary"))

    if not raw and articles:
        titles = " ".join(f"△{a['title']}" for a in articles)
        raw = f"주요 매체가 {titles} 등을 중심으로 보도."
    if not raw:
        raw = "기준일 조간 신문 트렌드 확인 필요."

    # **강조** 형태를 strong으로 변환
    escaped = esc(raw)
    escaped = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", escaped)
    escaped = escaped.replace("\n", "<br/><br/>")
    trend_html = f'<div class="news-trend">{escaped}</div>'

    trend_paragraphs = [clean_text(p) for p in safe_list(news.get("trend_paragraphs")) if clean_text(p)]
    if trend_paragraphs:
        extra = "<br/><br/>".join(esc(p) for p in trend_paragraphs[:3])
        trend_html = trend_html.replace('</div>', f'<br/><br/>{extra}</div>', 1)

    link_rows: list[str] = []
    for a in articles:
        desc = a.get("summary") or a.get("published") or ""
        link_rows.append(
            f'''<a class="news-link" href="{esc(a['url'])}" rel="noopener" target="_blank"><div class="news-link-title">{esc(a['title'])}</div><div class="news-link-press">{esc(a.get('press') or '-')}</div>{f'<div class="news-link-desc">{esc(desc)}</div>' if desc else ''}<div class="news-url">{esc(a['url'])}</div></a>'''
        )
    if not link_rows:
        link_rows.append('''<div class="news-link"><div class="news-link-title">대표 기사 미확인</div><div class="news-link-press">-</div><div class="news-link-desc">기준일 오전 보도 후보 확인 필요</div></div>''')

    body = (
        '<div class="news-body">'
        + trend_html
        + '<div class="news-separator"></div><div class="news-links-title">대표 기사</div>'
        + "\n".join(link_rows)
        + '</div><div class="fact-note">※ 조간 트렌드는 웹 확인 가능한 기준일 오전 보도 중 정유·석유화학·LNG 업계 관련성이 높은 기사 중심 작성. 기사 내용 밖의 업계 영향 평가는 작성자 해석</div>'
    )
    return body


def js_data(series: Mapping[str, Sequence[Mapping[str, Any]]], keys: Sequence[str]) -> str:
    return json.dumps(chart_rows_for_js(series, keys), ensure_ascii=False, separators=(",", ":"))


def render_script(crude_series: Mapping[str, Sequence[Mapping[str, Any]]], product_series: Mapping[str, Sequence[Mapping[str, Any]]]) -> str:
    crude_json = js_data(crude_series, CRUDE_KEYS)
    product_json = js_data(product_series, PRODUCT_KEYS)
    return f"""
<script>
const crudeData = {crude_json};
const productData = {product_json};
const chartConfigs = {{
  crude: {{ el:'crudeChart', tooltip:'crudeTip', line:'crudeLine', data: crudeData, keys:[['Brent','Brent'],['WTI','WTI'],['Dubai','Dubai']] }},
  product: {{ el:'productChart', tooltip:'productTip', line:'productLine', data: productData, keys:[['Gasoline','Gasoline'],['Diesel','Diesel'],['Naphtha','Naphtha']] }}
}};
(function(){{
  const W=440, ml=38, mr=10, pw=W-ml-mr;
  function attachTooltip(cfg){{
    const box=document.getElementById(cfg.el), tip=document.getElementById(cfg.tooltip), line=document.getElementById(cfg.line);
    if(!box || !tip) return;
    function showAt(clientX, clientY){{
      const rect=box.getBoundingClientRect(); if(!rect.width || !cfg.data.length) return;
      const relX=Math.max(ml, Math.min(W-mr, (clientX-rect.left)/rect.width*W));
      const idx=Math.max(0, Math.min(cfg.data.length-1, Math.round((relX-ml)/pw*(cfg.data.length-1))));
      const r=cfg.data[idx];
      const xx=ml + (cfg.data.length<=1 ? 0 : idx/(cfg.data.length-1)*pw);
      if(line){{ line.setAttribute('x1',xx); line.setAttribute('x2',xx); line.setAttribute('opacity','0.45'); }}
      let html='<div class="date">'+r.label+'</div>';
      cfg.keys.forEach(function(k){{ const v=r[k[0]]; html+='<div class="tooltip-row"><span>'+k[1]+'</span><b>'+((v===null||v===undefined||v===0)?'-':Number(v).toFixed(2))+'</b></div>'; }});
      tip.innerHTML=html; tip.style.display='block';
      let left=(clientX-rect.left)+12, top=(clientY-rect.top)-10;
      const tw=tip.offsetWidth||150, th=tip.offsetHeight||104;
      if(left+tw>rect.width) left=(clientX-rect.left)-tw-12; if(left<4) left=4;
      if(top+th>rect.height) top=rect.height-th-4; if(top<4) top=4;
      tip.style.left=left+'px'; tip.style.top=top+'px';
    }}
    function hide(){{ if(line) line.setAttribute('opacity','0'); tip.style.display='none'; }}
    box.addEventListener('mousemove', e=>showAt(e.clientX,e.clientY), {{passive:true}});
    box.addEventListener('mouseleave', hide, {{passive:true}});
    box.addEventListener('touchstart', e=>{{ if(e.touches&&e.touches[0]) showAt(e.touches[0].clientX,e.touches[0].clientY); }}, {{passive:true}});
    box.addEventListener('touchmove', e=>{{ if(e.touches&&e.touches[0]) showAt(e.touches[0].clientX,e.touches[0].clientY); }}, {{passive:true}});
  }}
  function init(){{ attachTooltip(chartConfigs.crude); attachTooltip(chartConfigs.product); }}
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded', init); else init();
}})();
</script>
""".strip()


def render_html(report: Mapping[str, Any], date_text: str) -> str:
    meta = safe_dict(report.get("report"))
    display_date = report_date_for_title(report, compact_date(date_text))
    today_label = clean_text(meta.get("today_label")) or date_label(date_text)
    title = "Daily 유가 동향"
    badge = clean_text(meta.get("report_badge")) or "정유 · 석유화학 · LNG"
    prices = safe_dict(report.get("prices"))
    crude = safe_dict(safe_dict(prices.get("crude")).get("chart_series"))
    products = safe_dict(safe_dict(prices.get("products")).get("chart_series"))

    parts = [
        '<!DOCTYPE html>',
        '<html lang="ko"><head><meta charset="utf-8"/>',
        '<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover"/>',
        f'<title>{esc(title)} — {esc(display_date)}</title>',
        f'<style>{STYLE}</style></head><body><div class="container">',
        f'<div class="header"><div class="header-top"><div><div class="header-title">{esc(title)}</div><div class="header-date">{esc(display_date)}</div></div><div class="header-badge">{esc(badge)}</div></div></div>',
        section(1, "Summary", render_summary(report)),
        section(2, "유가 동향", render_price_section(report)),
        render_chart_section(3, "원유 가격 추이", crude, CRUDE_KEYS, CRUDE_COLORS, None, "crudeChart", "crudeTip", "crudeLine", clean_text(safe_dict(prices.get("crude")).get("chart_period_label"))),
        render_chart_section(4, "석유제품 가격 추이", products, PRODUCT_KEYS, PRODUCT_COLORS, PRODUCT_DISPLAY, "productChart", "productTip", "productLine", clean_text(safe_dict(prices.get("products")).get("chart_period_label"))),
        section(5, "이해관계자·정책 주요 동향 (전일 기준)", render_issues(report)),
        section(6, f"금일 주요 일정 ({today_label})", render_schedules(report, today_label)),
        section(7, f"조간 신문 트렌드 ({today_label})", render_news(report, today_label)),
        f'<div class="footer">SK Innovation Communication Division · {esc(date_text.replace("-", "."))}</div>',
        '</div>',
        render_script(crude, products),
        '</body></html>',
    ]
    return "\n".join(parts)


def main() -> int:
    args = parse_args()
    input_path, output_path, date_text = resolve_paths(args)
    report = read_json(input_path)
    html_text = render_html(report, date_text)
    atomic_write(output_path, html_text)
    print(f"[OK] HTML 리포트 생성 완료: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
