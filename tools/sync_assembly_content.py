"""Refresh the published completed monitoring reports.

Fail before writing any files if the upstream source cannot be validated.
The Pages workflow then preserves the last successfully deployed site.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
MONITORING_URL = 'https://jemjemjemm.github.io/26GookGam/'


def download(url: str) -> bytes:
    for attempt in range(3):
        try:
            with urlopen(Request(url, headers={'User-Agent': 'Daily-Energy-Dashboard', 'Cache-Control': 'no-cache'}), timeout=25) as response:
                return response.read()
        except Exception:
            if attempt == 2:
                raise
            time.sleep(attempt + 1)
    raise RuntimeError('Download failed')


def monitoring_view(source: str) -> tuple[str, dict]:
    panel = re.search(r'<section\b[^>]*\bid="panel-done"[^>]*>.*?</section>', source, re.S)
    modal = re.search(r'<div class="modal-overlay"[^>]*>.*?(?=<script\b)', source, re.S)
    scripts = re.findall(r'<script\b[^>]*>(.*?)</script>', source, re.S)
    script = next((s for s in scripts if re.search(r'var REPORTS\s*=', s)), '')
    data = re.search(r'var REPORTS\s*=\s*({.*?});', script, re.S)
    styles = re.findall(r'<style\b[^>]*>.*?</style>', source, re.S)
    if not all((panel, modal, data, styles)):
        raise ValueError('Monitoring source structure changed; refusing an incomplete copy')
    reports = json.loads(data.group(1))
    keys = re.findall(r'data-target="([^"]+)"', panel.group())
    if not keys or any(not isinstance(reports.get(key), str) or not reports[key].strip() for key in keys):
        raise ValueError('Completed report buttons must all have nonempty report bodies')
    meetings = len(re.findall(r'<tr\b[^>]*class="done-row"', panel.group()))
    if meetings < len(keys):
        raise ValueError('Monitoring meeting/report counts are inconsistent')
    # Preserve the original table, month groups, report text and modal behavior.
    result = ('<!doctype html><html lang="ko"><head><meta charset="utf-8">'
              '<meta name="viewport" content="width=device-width,initial-scale=1">'
              '<title>Monitoring Report</title>' + ''.join(styles) +
              '<style>#panel-done{display:block}main{margin:0 auto;padding:10px}body{margin:0}</style>'
              '</head><body><main>' + panel.group() + '</main>' + modal.group() +
              '<script>' + script + '''
// Keep the original popup controls visible when embedded in the Daily viewer.
document.querySelectorAll('#panel-done .report-btn').forEach(function(button) {
  button.addEventListener('click', function() {
    if (window.frameElement) window.frameElement.scrollIntoView({block:'center', behavior:'instant'});
  });
});
</script></body></html>''')
    return result, {'meetings': meetings, 'reports': len(keys), 'reportIds': keys}


def sync(output: Path) -> dict:
    source = download(MONITORING_URL).decode('utf-8-sig')
    monitoring, counts = monitoring_view(source)
    manifest = {
        'checkedAt': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'monitoring': {'url': MONITORING_URL, 'sha256': hashlib.sha256(source.encode()).hexdigest(), **counts},
    }
    outputs = {'monitoring/index.html': monitoring.encode('utf-8'),
               'manifest.json': (json.dumps(manifest, ensure_ascii=False, indent=2) + '\n').encode('utf-8')}
    for name, content in outputs.items():
        path = output / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=ROOT / 'docs/assembly-content')
    args = parser.parse_args()
    metadata = sync(args.output)
    print(f"[OK] Monitoring: {metadata['monitoring']['meetings']} meetings / {metadata['monitoring']['reports']} reports")
