"""Human-readable Telegram notifications for collection/build failures."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import requests

PAGE_URL = "https://jemjemjemm.github.io/F_issue/"


def format_report_message(report: dict) -> str:
    warnings = report.get("collection_warnings", [])
    zero = report.get("total_deduped_count", 0) == 0
    heading = "[F-Issue Report 확인 필요]" if zero else "[F-Issue Report 수집 알림]"
    lines = [
        heading, "", f"기준일: {report.get('base_date', '-')}",
        f"구분: {str(report.get('slot', '-')).title()}",
        f"수집 범위: {report.get('period_label', '-')}", "",
    ]
    if zero:
        lines += ["이번 리포트의 기사 수가 0건입니다.", ""]
    if warnings:
        lines += ["수집 중 아래 문제가 있었습니다."]
        for index, item in enumerate(warnings[:10], 1):
            query = f" ({item.get('query')})" if item.get("query") else ""
            lines.append(f"{index}) {item.get('portal', 'system')}{query}: {item.get('user_message') or item.get('message')}")
    else:
        lines.append("수집이 정상적으로 완료되었습니다.")
    lines += ["", "결과:", f"- 원본 수집: {report.get('total_raw_count', 0)}건", f"- 중복 제거 후: {report.get('total_deduped_count', 0)}건", f"- 정상: {report.get('total_ok_count', 0)}건", f"- 검토필요: {report.get('total_review_count', 0)}건", f"- 제외: {report.get('total_excluded_count', 0)}건", "", f"확인: {PAGE_URL}"]
    return "\n".join(lines)


def send_message(text: str) -> bool:
    token, chat_id = os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("Telegram credentials are not configured; notification skipped.")
        return False
    response = requests.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat_id, "text": text, "disable_web_page_preview": True}, timeout=20)
    response.raise_for_status()
    return True


def notify_for_report(report: dict) -> bool:
    should_notify = bool(report.get("collection_warnings")) or os.getenv("TELEGRAM_NOTIFY_ON_SUCCESS", "false").lower() == "true"
    return send_message(format_report_message(report)) if should_notify else False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report")
    parser.add_argument("--message")
    args = parser.parse_args()
    if args.report:
        report = json.loads(Path(args.report).read_text(encoding="utf-8"))
        send_message(format_report_message(report))
    elif args.message:
        send_message(f"[F-Issue Report 오류]\n\n{args.message}\n\n확인: {PAGE_URL}")
    else:
        parser.error("--report or --message is required")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
