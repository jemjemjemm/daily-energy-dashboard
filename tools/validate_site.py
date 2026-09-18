"""Verify the published views and lossless migration, without network calls."""
from __future__ import annotations

import argparse
import re
from pathlib import Path

from tools.assemble_site import ROOT, split_report


def validate_site(site: Path) -> None:
    daily_index = (site / 'index.html').read_text(encoding='utf-8')
    assembly_index = (site / 'assembly/index.html').read_text(encoding='utf-8')
    assert '>유가</a>' not in daily_index
    assert 'href="assembly/"' in daily_index
    assert '7. Oil Price Issue Report' in daily_index
    assert 'oilViewer' not in assembly_index
    assert 'assembly/reports/${date}.html' in assembly_index
    assert '<base href="../">' in assembly_index
    count = 0
    for source in (ROOT / 'docs/reports').glob('*.html'):
        expected_daily, expected_assembly = split_report(source.read_text(encoding='utf-8'))
        daily = (site / 'reports' / source.name).read_text(encoding='utf-8')
        assembly = (site / 'assembly/reports' / source.name).read_text(encoding='utf-8')
        assert daily == expected_daily, source
        assert assembly == expected_assembly, source
        assert re.findall(r'class="section-num">(\d+)', daily) == list('123456'), source
        assert re.findall(r'class="section-num">(\d+)', assembly) == ['1', '2', '3'], source
        assert '../../assembly-content/monitoring/index.html' in assembly, source
        assert 'class="section-title">금일 주요 일정' not in daily, source
        assert 'class="section-title">News Trend' not in assembly, source
        count += 1
    oil_count = 0
    for directory in ('data/reports', 'reports'):
        for source in (ROOT / 'oil' / directory).iterdir():
            if source.is_file():
                assert source.read_bytes() == (site / 'oil' / directory / source.name).read_bytes(), source
                oil_count += 1
    assert (ROOT / 'oil/data/report-index.json').read_bytes() == (site / 'oil/data/report-index.json').read_bytes()
    embed = (site / 'oil/embed.html').read_text(encoding='utf-8')
    monitoring = (site / 'assembly-content/monitoring/index.html').read_text(encoding='utf-8')
    assert 'id="panel-done"' in monitoring and 'id="modalOverlay"' in monitoring
    assert 'id="panel-schedule"' not in monitoring
    for marker in ('id="report-root"', 'id="calendar-root"', 'id="refresh-button"'):
        assert marker in embed
    print(f'[OK] Daily/assembly dates: {count}; oil files preserved byte-for-byte: {oil_count}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--site', default='_site')
    validate_site(Path(parser.parse_args().site))
