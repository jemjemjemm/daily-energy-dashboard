#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def split_report(text: str) -> tuple[str, str]:
    """Publish the canonical pipeline report as Daily and parliamentary views.

    Keep the source report intact so historical content and pipeline quality
    validation use exactly the same data. Every deployment splits all dates.
    """
    sections = list(re.finditer(r'<section\b[^>]*>.*?</section>', text, re.S))
    schedule = [m for m in sections if re.search(
        r'class="section-title">금일 주요 일정', m.group())]
    if len(schedule) != 1:
        raise ValueError("Expected exactly one schedule section in source report")
    schedule_text = schedule[0].group().replace(
        '<span class="section-num">5</span>', '<span class="section-num">1</span>', 1)
    daily = text[:schedule[0].start()] + text[schedule[0].end():]
    for old, new in ((6, 5), (7, 6)):
        daily = daily.replace(f'<span class="section-num">{old}</span>',
                              f'<span class="section-num">{new}</span>')
    # Keep the original modal markup/scripts and embedded monthly data.
    start = sections[0].start()
    end = sections[-1].end()
    assembly = text[:start] + schedule_text + text[end:]
    assembly = assembly.replace('Daily Issue Report', '국감')
    assembly = assembly.replace('../schedules/', '../../schedules/')
    return daily, assembly


def publish_views(output: Path) -> None:
    assembly_dir = output / 'assembly/reports'
    assembly_dir.mkdir(parents=True, exist_ok=True)
    for path in sorted((output / 'reports').glob('*.html')):
        daily, assembly = split_report(path.read_text(encoding='utf-8'))
        path.write_text(daily, encoding='utf-8')
        (assembly_dir / path.name).write_text(assembly, encoding='utf-8')

    dashboard = (output / 'index.html').read_text(encoding='utf-8')
    assembly_dashboard = dashboard.replace('<head>', '<head>\n  <base href="../">', 1)
    assembly_dashboard = assembly_dashboard.replace('class="daily-dashboard"', 'class="assembly-dashboard"', 1)
    assembly_dashboard = assembly_dashboard.replace('Daily Issue Dashboard', '국감')
    assembly_dashboard = assembly_dashboard.replace('Daily Issue Report', '국감')
    assembly_dashboard = assembly_dashboard.replace('정유 · 석유화학 · LNG AI 리포트', '본회의 · 상임위 일정 + 월간 국회일정캘린더')
    assembly_dashboard = assembly_dashboard.replace('href="./" aria-current="page"', 'href="./"')
    assembly_dashboard = assembly_dashboard.replace('href="assembly/"', 'href="assembly/" aria-current="page"')
    assembly_dashboard = assembly_dashboard.replace('r.url || `reports/${r.date}.html`', '`assembly/reports/${r.date}.html`')
    assembly_dashboard = assembly_dashboard.replace('r.url || `reports/${date}.html`', '`assembly/reports/${date}.html`')
    assembly_dashboard = assembly_dashboard.replace(
        'state.reports=(data.reports||[]).slice()',
        "state.reports=(data.reports||[]).map(r=>({...r,title:String(r.title||'').replace('Daily Issue Report','국감')})).slice()")
    assembly_dashboard = re.sub(r'\s*<!-- OIL START -->.*?<!-- OIL END -->', '', assembly_dashboard, flags=re.S)
    (output / 'assembly/index.html').write_text(assembly_dashboard, encoding='utf-8')

    oil = (output / 'oil/index.html').read_text(encoding='utf-8')
    oil = re.sub(r'<nav\b.*?</nav>', '', oil, flags=re.S)
    oil = oil.replace('<h1>Oil Price Issue Report</h1>', '')
    oil = oil.replace('</head>', '<style>.header-inner{padding:10px 0}.page-shell{margin-top:14px}body{overflow:hidden}</style></head>')
    (output / 'oil/embed.html').write_text(oil, encoding='utf-8')
    # Preserve old bookmarks, including ?report= archive links.
    (output / 'oil/index.html').write_text('''<!doctype html><html lang="ko"><head>
<meta charset="utf-8"><title>Oil Price Issue Report</title></head><body>
<a href="../#oil-report">Daily · Oil Price Issue Report</a>
<script>location.replace('../'+location.search+'#oil-report');</script>
</body></html>''', encoding='utf-8')


def copy_tree(source: Path, destination: Path) -> None:
    if not source.exists():
        raise SystemExit(f"[ERROR] required source is missing: {source.relative_to(ROOT)}")
    shutil.copytree(source, destination, dirs_exist_ok=True)


def load_index(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_index(index_path: Path, report_dir: Path, suffix: str) -> None:
    index = load_index(index_path)
    if isinstance(index, list):
        files = sorted(report_dir.glob(f"*{suffix}"))
        if len(files) != len(index):
            raise SystemExit(
                f"[ERROR] index/file mismatch for {index_path}: index={len(index)}, files={len(files)}"
            )
        return
    reports = index.get("reports", [])
    dates = index.get("availableDates", [])
    files = sorted(report_dir.glob(f"*{suffix}"))
    if index.get("count") != len(reports) or len(dates) != len(reports):
        raise SystemExit(f"[ERROR] inconsistent index counts: {index_path}")
    if len(files) != len(reports):
        raise SystemExit(
            f"[ERROR] index/file mismatch for {index_path}: index={len(reports)}, files={len(files)}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Assemble the Daily and oil reports into one Pages artifact")
    parser.add_argument("--output", default="_site")
    args = parser.parse_args()

    output = (ROOT / args.output).resolve()
    if output == ROOT or ROOT not in output.parents:
        raise SystemExit("[ERROR] output must be a child directory of the repository")
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)

    docs = ROOT / "docs"
    for child in docs.iterdir():
        if child.name == "_site":
            continue
        target = output / child.name
        if child.is_dir():
            copy_tree(child, target)
        else:
            shutil.copy2(child, target)

    copy_tree(ROOT / "shared", output / "shared")
    oil_output = output / "oil"
    oil_output.mkdir()
    shutil.copy2(ROOT / "oil/index.html", oil_output / "index.html")
    copy_tree(ROOT / "oil/assets", oil_output / "assets")
    copy_tree(ROOT / "oil/reports", oil_output / "reports")
    (oil_output / "data/reports").mkdir(parents=True)
    shutil.copy2(ROOT / "oil/data/report-index.json", oil_output / "data/report-index.json")
    copy_tree(ROOT / "oil/data/reports", oil_output / "data/reports")
    publish_views(output)
    (output / ".nojekyll").touch()

    validate_index(output / "report-index.json", output / "reports", ".html")
    validate_index(oil_output / "data/report-index.json", oil_output / "data/reports", ".json")
    print("[OK] Pages artifact assembled")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
