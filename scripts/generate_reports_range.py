#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
generate_reports_range.py v1.1

지정 기간의 평일 리포트를 일괄 생성합니다.
기존 fallback 리포트는 보강된 형식으로 갱신합니다.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description="기간별 평일 리포트 일괄 생성")
    parser.add_argument("--start", required=True, help="시작일 YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="종료일 YYYY-MM-DD")
    parser.add_argument("--skip-weekends", action="store_true", default=True, help="토/일 제외")
    parser.add_argument("--report-dir", default="data/reports")
    parser.add_argument("--price-dir", default="data/prices")
    parser.add_argument("--history", default="data/prices/history.json")
    parser.add_argument("--html-dir", default="docs/reports")
    parser.add_argument("--index-out", default="docs/report-index.json")
    parser.add_argument("--base-report", default="report_sample.json")
    parser.add_argument("--chart-months", default="2")
    return parser.parse_args()


def date_range(start: str, end: str):
    s = datetime.strptime(start, "%Y-%m-%d").date()
    e = datetime.strptime(end, "%Y-%m-%d").date()
    if s > e:
        raise ValueError("--start가 --end보다 늦습니다.")
    cur = s
    while cur <= e:
        yield cur
        cur += timedelta(days=1)


def run(cmd):
    print("[RUN]", " ".join(cmd))
    completed = subprocess.run(cmd, text=True)
    if completed.returncode != 0:
        raise RuntimeError(f"명령 실패: {' '.join(cmd)}")


def main() -> int:
    args = parse_args()

    required_files = [
        "scripts/ensure_report_draft.py",
        "scripts/merge_prices_into_report.py",
        "scripts/generate_html_report.py",
        "scripts/generate_report_index.py",
        args.history,
    ]

    for file_name in required_files:
        if not Path(file_name).exists():
            print(f"[ERROR] 필수 파일이 없습니다: {file_name}")
            return 1

    generated_dates = []

    for d in date_range(args.start, args.end):
        if args.skip_weekends and d.weekday() >= 5:
            print(f"[SKIP] 주말 제외: {d.isoformat()}")
            continue

        date_text = d.isoformat()
        generated_dates.append(date_text)
        print(f"\n=== {date_text} 리포트 생성 ===")

        run([
            sys.executable,
            "scripts/ensure_report_draft.py",
            "--date", date_text,
            "--out-dir", args.report_dir,
            "--base-report", args.base_report,
            "--refresh-fallback",
        ])

        run([
            sys.executable,
            "scripts/merge_prices_into_report.py",
            "--date", date_text,
            "--report-dir", args.report_dir,
            "--price-dir", args.price_dir,
            "--history", args.history,
            "--chart-months", str(args.chart_months),
        ])

        run([
            sys.executable,
            "scripts/generate_html_report.py",
            "--date", date_text,
            "--report-dir", args.report_dir,
            "--out-dir", args.html_dir,
        ])

    run([
        sys.executable,
        "scripts/generate_report_index.py",
        "--reports-dir", args.html_dir,
        "--out", args.index_out,
    ])

    print("\n[OK] 기간 리포트 생성 완료")
    print("[OK] 생성 대상 날짜:", ", ".join(generated_dates))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
