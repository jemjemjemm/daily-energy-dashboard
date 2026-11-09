"""Record automated original-source checks and every excluded raw candidate.

This audit does not claim human editorial review. Unconfirmed articles retain
verified=false with the reason shown; existing editorial reviews are preserved.
"""
from __future__ import annotations
import argparse
import json
from datetime import timedelta
from pathlib import Path
from utils_time import resolve_base_date, get_period, is_in_period, parse_datetime
from build_report import ROOT, update_index, write_report_html


def audit(day, slot):
    path = ROOT / f'data/reports/{day}-{slot}.json'
    report = json.loads(path.read_text(encoding='utf-8'))
    if report.get('editorial_audit') and report.get('summary'):
        return
    raw_path = ROOT / f'data/raw/{day}-{slot}-raw.json'
    raw = json.loads(raw_path.read_text(encoding='utf-8'))
    items = raw.get('items', [])
    if not items:
        raise ValueError(f'No search results; collection outage cannot be published as no news: {raw_path}')
    start, end = get_period(day, slot)
    exclusions = []
    included = {a['url'] for a in report['articles']}
    for item in report.get('source_review', items):
        reason = ('unknown_search_time' if not parse_datetime(item.get('published_at')) else
                  'outside_period' if not is_in_period(item.get('published_at'), start, end) else
                  'duplicate_or_quality_exclusion')
        if item.get('url') not in included:
            exclusions.append(dict(url=item.get('url'), title=item.get('title'), reason=reason))
    for article in report['articles']:
        article.setdefault('verified', False)
        article.setdefault('time_evidence', article.get('verification_reason') or '검색 결과시각 기준; 원문 최초시각 미확인')
    confirmed = sum(a['verified'] is True for a in report['articles'])
    report['summary'] = f"수집 기사 {len(report['articles'])}건, 발행사 본문·최초시각 확인 {confirmed}건, 미확인 {len(report['articles']) - confirmed}건 구분"
    report['editorial_audit'] = dict(method='automated-source-audit', raw_result_count=len(items),
                                     exclusions=exclusions, collection_warnings=raw.get('collection_warnings', []),
                                     limitations=['공개 검색 노출 한계; verified=false 기사는 원문·최초시각 검증 완료를 의미하지 않음'])
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    update_index(report)
    write_report_html(report)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--base-date', required=True)
    p.add_argument('--slot', required=True, choices=['morning', 'evening', 'night'])
    p.add_argument('--include-previous-night', default='false')
    a = p.parse_args()
    day = resolve_base_date(a.base_date)
    audit(day.isoformat(), a.slot)
    if a.slot == 'morning' and a.include_previous_night == 'true':
        audit((day - timedelta(days=1)).isoformat(), 'night')
