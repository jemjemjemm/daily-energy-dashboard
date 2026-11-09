"""Regenerate indexed HTML from source-reviewed snapshots without live searches."""
import argparse
import json
from datetime import timedelta
from build_report import ROOT, update_index, write_report_html
from utils_time import resolve_base_date

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--base-date', required=True)
    p.add_argument('--slot', choices=['morning', 'evening'], required=True)
    a = p.parse_args()
    day = resolve_base_date(a.base_date)
    targets = [(day, a.slot)]
    if a.slot == 'morning':
        targets.append((day - timedelta(days=1), 'night'))
    for day, slot in targets:
        report = json.loads((ROOT / f'data/reports/{day}-{slot}.json').read_text(encoding='utf-8'))
        if not report.get('editorial_audit'):
            raise ValueError('Historical replay requires reviewed source snapshots')
        update_index(report)
        write_report_html(report)
