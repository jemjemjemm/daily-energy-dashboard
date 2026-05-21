#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import re
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")
TITLE_RE = re.compile(r"<title>\s*(.*?)\s*</title>", re.I | re.S)
HEADER_DATE_RE = re.compile(r'<div class="header-date">\s*(.*?)\s*</div>', re.I | re.S)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="캘린더 대시보드용 report-index.json 생성")
    p.add_argument("--reports-dir", default="public/reports")
    p.add_argument("--out", default="public/report-index.json")
    return p.parse_args()


def strip_tags(v: str) -> str:
    v = re.sub(r"<[^>]*>", "", v or "")
    v = v.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"').replace("&#39;", "'")
    return re.sub(r"\s+", " ", v).strip()


def atomic_write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=str(path.parent), delete=False,
                                     prefix=f".{path.name}.", suffix=".tmp") as tmp:
        tmp.write(text)
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)


def main() -> int:
    args = parse_args()
    reports_dir = Path(args.reports_dir)
    if not reports_dir.exists():
        print(f"[ERROR] reports 폴더가 없습니다: {reports_dir}")
        return 1

    reports: List[Dict[str, Any]] = []
    for html_path in sorted(reports_dir.glob("*.html")):
        m = DATE_RE.search(html_path.name)
        if not m:
            continue
        date = m.group(1)
        text = html_path.read_text(encoding="utf-8", errors="ignore")
        tm = TITLE_RE.search(text)
        dm = HEADER_DATE_RE.search(text)
        reports.append({
            "date": date,
            "displayDate": strip_tags(dm.group(1)) if dm else date,
            "title": strip_tags(tm.group(1)) if tm else f"Daily 유가 동향 — {date}",
            "url": f"reports/{html_path.name}",
            "status": "초안",
            "fileName": html_path.name,
            "exists": True,
        })

    reports.sort(key=lambda x: x["date"], reverse=True)
    payload = {
        "schemaVersion": "1.0",
        "generatedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S KST"),
        "count": len(reports),
        "latestDate": reports[0]["date"] if reports else "",
        "availableDates": sorted([r["date"] for r in reports]),
        "warnings": [],
        "reports": reports,
    }
    atomic_write_json(Path(args.out), payload)
    print(f"[OK] report-index.json 생성 완료: {args.out}")
    print(f"[OK] 리포트 수: {len(reports)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
