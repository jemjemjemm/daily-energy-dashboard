"""Replay saved editorial sources through the production bundle generators.

Run in a disposable checkout: outputs are regenerated but never committed or
published. This verifies reproducibility, not historical live-search coverage.
"""
import argparse
from datetime import date, timedelta
import json
from pathlib import Path

from tools.report_bundle import ROOT, generate, run, validate_bundle
from scripts.kr_holidays import is_business_day


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--start', required=True)
    p.add_argument('--end', required=True)
    p.add_argument('--output', default='.cache/pipeline-simulation')
    a = p.parse_args()
    start, end = date.fromisoformat(a.start), date.fromisoformat(a.end)
    if start > end:
        raise ValueError('start must not follow end')
    output = (ROOT / a.output).resolve()
    if ROOT not in output.parents or '.cache' not in output.relative_to(ROOT).parts:
        raise ValueError('Simulation evidence must be under repository .cache')
    results = []
    for offset in range((end-start).days + 1):
        day = start + timedelta(days=offset)
        if not is_business_day(day):
            continue
        for slot in ['morning', 'evening']:
            generate(day.isoformat(), slot, replay=True)
            results.append(validate_bundle(ROOT, day.isoformat(), slot))
            # Production runs the tests after generation. Exercise that same
            # ordering for every slot, not just once after the entire range.
            run(['-m', 'unittest', 'tests.test_report_bundle'])
    if not results:
        raise ValueError('No business days selected')
    run(['tools/sync_assembly_content.py'])
    run(['oil/scripts/validate_reports.py'])
    run(['tools/assemble_site.py', '--output', str(output.relative_to(ROOT) / 'site')])
    run(['-m', 'tools.validate_site', '--site', str(output / 'site')])
    run(['-m', 'unittest', 'tests.test_report_bundle', 'tests.test_committee_news',
         'tests.test_sync_assembly_content', 'tests.test_site_views', 'tests.test_generate_reports_range'])
    output.mkdir(parents=True, exist_ok=True)
    evidence = dict(mode='saved-source-replay', start=a.start, end=a.end, passed=len(results),
                    limitations=['Historical live search is not replayable; saved source reviews are preserved.',
                                 'Fresh committee collection and editorial API are tested separately.'], results=results)
    (output / 'result.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(evidence, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
