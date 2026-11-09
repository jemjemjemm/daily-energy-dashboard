"""Run and gate the companion reports before a Daily slot can be marked done.

The same entry point is used by workflow_dispatch and historical replay. Replay
uses committed source snapshots, never live search results for historical dates.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.committee_news import COMMITTEES, KST, validate_report, window


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def oil_targets(day, slot):
    targets = [(day, slot)]
    if slot == 'morning':
        targets.append(((date.fromisoformat(day) - timedelta(days=1)).isoformat(), 'night'))
    return targets


def validate_bundle(root, day, slot, *, require_monitoring=True):
    """Raise on partial success, including legacy Daily-only completion files."""
    daily = root / f'docs/reports/{day}.html'
    if not daily.is_file() or day not in daily.read_text(encoding='utf-8'):
        raise ValueError(f'Daily HTML missing/wrong date: {day}')
    index = read(root / 'docs/report-index.json')
    if day not in index['availableDates']:
        raise ValueError(f'Daily index missing {day}')
    daily_data = read(root / f'data/reports/{day}.report.json')
    news_key = 'news_trend' if slot == 'morning' else 'news_trend_afternoon'
    news = daily_data.get(news_key, {})
    if not news.get('articles') or news.get('report_slot') != slot:
        raise ValueError(f'Daily {slot} news section missing or wrong slot')
    review = read(root / f'data/committee-news/{day}-{slot}.review.json')
    if review.get('date') != day or review.get('slot') != slot or not review.get('search_log'):
        raise ValueError('Committee source review missing or wrong target')
    committee = read(root / f'docs/assembly-content/issues/{day}-{slot}.json')
    if committee.get('date') != day or committee.get('slot') != slot:
        raise ValueError('Committee target mismatch')
    if [c['id'] for c in committee['committees']] != [c[0] for c in COMMITTEES]:
        raise ValueError('Three current committees required')
    validate_report(committee)
    oil_index = read(root / 'oil/data/report-index.json')
    result = dict(date=day, slot=slot, daily=True, committees={}, oil=[])
    for c in committee['committees']:
        result['committees'][c['id']] = len(c['all'])
    for oil_day, oil_slot in oil_targets(day, slot):
        report = read(root / f'oil/data/reports/{oil_day}-{oil_slot}.json')
        if (report.get('base_date'), report.get('slot')) != (oil_day, oil_slot):
            raise ValueError('Oil target mismatch')
        if not report.get('editorial_audit') or not report.get('summary'):
            raise ValueError(f'Oil review/audit missing: {oil_day} {oil_slot}')
        for article in report['articles']:
            if type(article.get('verified')) is not bool or not article.get('time_evidence'):
                raise ValueError(f'Oil article verification state/evidence missing: {oil_day} {oil_slot}')
        if not (root / f'oil/reports/{oil_day}-{oil_slot}.html').is_file():
            raise ValueError('Oil HTML missing')
        if not any((x.get('base_date'), x.get('slot')) == (oil_day, oil_slot) for x in oil_index):
            raise ValueError('Oil index target missing')
        result['oil'].append(dict(date=oil_day, slot=oil_slot, articles=len(report['articles'])))
    if require_monitoring:
        manifest = read(root / 'docs/assembly-content/manifest.json')
        if not manifest.get('monitoring', {}).get('reports') or not (root / 'docs/assembly-content/monitoring/index.html').is_file():
            raise ValueError('Completed monitoring report missing')
        result['monitoring'] = manifest['monitoring']['reports']
    return result


def run(command, *, oil=False):
    print('+ ' + ' '.join(command), flush=True)
    subprocess.run([sys.executable, *command], cwd=ROOT / 'oil' if oil else ROOT, check=True)


def generate(day, slot, *, replay=False):
    if datetime.now(KST) < window(day, slot)[1]:
        raise ValueError(f'{day} {slot}: reporting window has not closed')
    if replay:
        review_path = ROOT / f'data/committee-news/{day}-{slot}.review.json'
        if not review_path.is_file():
            raise ValueError(f'Replay requires a saved committee source review: {review_path}')
        for oil_day, oil_slot in oil_targets(day, slot):
            report_path = ROOT / f'oil/data/reports/{oil_day}-{oil_slot}.json'
            snapshot = read(report_path)
            if not snapshot.get('editorial_audit') or not snapshot.get('summary'):
                raise ValueError(f'Replay requires a reviewed oil snapshot: {report_path}')
        # Actual generators, isolated checkout; preserve curated source data.
        # Use the saved, source-reviewed Daily JSON. Reapplying today's body
        # fetches or LLM summaries would no longer be a historical replay.
        run(['scripts/validate_schedule_source.py', '--date', day])
        run(['scripts/validate_report_sources.py', '--date', day])
        run(['scripts/generate_schedule_detail_html.py', '--date', day])
        run(['scripts/generate_html_report.py', '--date', day, '--report-slot', slot])
        run(['scripts/generate_report_index.py'])
    run(['-m', 'tools.collect_committee_news', '--date', day, '--slot', slot])
    run(['-m', 'tools.committee_news', '--date', day, '--slot', slot,
         '--input', f'data/committee-news/{day}-{slot}.review.json'])
    if replay:
        for oil_day, oil_slot in oil_targets(day, slot):
            # No network fallbacks permitted in historical source replay.
            if not (ROOT / f'oil/data/reports/{oil_day}-{oil_slot}.json').is_file():
                raise ValueError('Replay requires saved oil report and original collection snapshots')
    else:
        run(['scripts/collect_news.py', '--base-date', day, '--slot', slot, '--include-previous-night', 'true'], oil=True)
    run(['scripts/build_report.py', '--base-date', day, '--slot', slot, '--include-previous-night', 'true'], oil=True)
    if replay:
        run(['scripts/replay_reviewed_report.py', '--base-date', day, '--slot', slot], oil=True)
    run(['scripts/audit_report.py', '--base-date', day, '--slot', slot, '--include-previous-night', 'true'], oil=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--date')
    parser.add_argument('--start')
    parser.add_argument('--end')
    parser.add_argument('--slot', choices=['morning', 'evening'], required=True)
    parser.add_argument('--replay', action='store_true')
    parser.add_argument('--validate-only', action='store_true')
    parser.add_argument('--result', type=Path)
    args = parser.parse_args()
    if args.date:
        days = [args.date]
    else:
        from scripts.kr_holidays import is_business_day
        start, end = date.fromisoformat(args.start), date.fromisoformat(args.end)
        days = [(start + timedelta(days=i)).isoformat() for i in range((end-start).days + 1)
                if is_business_day(start + timedelta(days=i))]
        if not days:
            raise ValueError('No business days in requested range')
    for day in days:
        if not args.validate_only:
            generate(day, args.slot, replay=args.replay)
    if not args.validate_only:
        run(['tools/sync_assembly_content.py'])
    results = [validate_bundle(ROOT, day, args.slot) for day in days]
    if args.result:
        args.result.parent.mkdir(parents=True, exist_ok=True)
        args.result.write_text(json.dumps(results, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
