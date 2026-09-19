"""Validate, select and publish reviewed parliamentary news without inventing news."""
from __future__ import annotations

import argparse
import html
import json
from functools import lru_cache
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / 'docs/assembly-content/issues'
KST = timezone(timedelta(hours=9))
COMMITTEES = (
    ('industry', '산업통상자원중소벤처기업위원회', '산자위'),
    ('finance', '기획재정위원회', '기재위'),
    ('affairs', '정무위원회', '정무위'),
)
CATEGORIES = ('정유·유가/담합', '석유화학', '배터리', 'LNG·전력', '도시가스',
              '재생에너지·수소', 'E&P·해외자원개발', 'SMR·신재생 원전(신사업)')
MAJOR_PRESS = {'조선일보', '중앙일보', '동아일보', '한국경제', '매일경제', '서울경제',
               '한국일보', '서울신문', '세계일보', '한겨레', '경향신문', '국민일보',
               '머니투데이', '파이낸셜뉴스', '아시아경제', '아주경제', '이투데이', '조선비즈', '노컷뉴스'}
SPECIALIST_PRESS = {'전자신문', '이데일리', '헤럴드경제', '뉴스핌', '뉴스토마토',
                    '에너지경제', '에너지경제신문', '전기신문', '에너지신문', '아시아타임즈'}


@lru_cache(maxsize=1)
def committee_roster():
    return json.loads((ROOT / 'data/committee-news/roster.json').read_text(encoding='utf-8'))['members']


def window(date: str, slot: str) -> tuple[datetime, datetime]:
    day = datetime.strptime(date, '%Y-%m-%d').replace(tzinfo=KST)
    if slot == 'morning':
        return day - timedelta(days=1) + timedelta(hours=17), day + timedelta(hours=8)
    if slot == 'evening':
        return day + timedelta(hours=8), day + timedelta(hours=17)
    raise ValueError('slot must be morning or evening')


def period_label(date: str, slot: str) -> str:
    start, end = window(date, slot)
    return f'수집 기간: {start:%Y-%m-%d %H:%M} ~ {end:%Y-%m-%d %H:%M} (KST)'


def press_rank(press: str) -> int:
    if press == '연합뉴스':
        return 1
    if press in MAJOR_PRESS:
        return 2
    if press in {'뉴시스', '뉴스1'}:
        return 3
    if press in SPECIALIST_PRESS:
        return 4
    raise ValueError(f'Unreviewed publisher: {press}')


def validate_article(article: dict) -> datetime:
    for key in ('title', 'url', 'press', 'summary', 'event_id', 'committee_reason', 'time_evidence'):
        if not isinstance(article.get(key), str) or not article[key].strip():
            raise ValueError(f'Missing {key}')
    parsed = urlsplit(article['url'])
    if parsed.scheme != 'https' or not parsed.netloc or parsed.hostname in {'news.google.com', 'search.naver.com'}:
        raise ValueError('An original HTTPS article URL is required')
    if article.get('verified') is not True:
        raise ValueError('Article body and original publication time must be reviewed')
    press_rank(article['press'])
    committees = article.get('committees', [])
    if len(committees) != 1 or not set(committees) <= {c[0] for c in COMMITTEES}:
        raise ValueError('Unknown/missing committee')
    roster = committee_roster()
    for member in article.get('members', []):
        if not any(m['name'] == member and m['committee'] == committees[0] for m in roster):
            raise ValueError(f'Member/committee mismatch: {member}')
    if not set(article.get('categories', [])) <= set(CATEGORIES):
        raise ValueError('Unknown priority industry category')
    if article.get('categories') and not article.get('category_reason'):
        raise ValueError('Direct priority-industry relevance must be explained')
    scores = article.get('importance', {})
    if any(type(scores.get(key)) is not int or not 0 <= scores[key] <= 3
           for key in ('legislation', 'impact', 'speaker')):
        raise ValueError('Importance requires legislation/impact/speaker scores 0..3')
    published = datetime.fromisoformat(article['published_at'])
    if published.utcoffset() != timedelta(hours=9):
        raise ValueError('Publication timestamp must include +09:00')
    return published


def importance_key(article: dict) -> tuple:
    scores = article['importance']
    return (-scores['legislation'], -scores['impact'], -scores['speaker'], press_rank(article['press']), article['url'])


def select_articles(candidates: list[dict], date: str, slot: str) -> list[dict]:
    start, end = window(date, slot)
    eligible = []
    for article in candidates:
        published = validate_article(article)
        # Include the explicitly requested start and end timestamps.
        if start <= published <= end:
            eligible.append(article)
    # A story belongs to one committee; never repeat it across committees.
    winners = {}
    urls = set()
    for article in sorted(eligible, key=lambda a: (press_rank(a['press']), *importance_key(a), a['published_at'])):
        if article['event_id'] not in winners and article['url'] not in urls:
            winners[article['event_id']] = article
            urls.add(article['url'])
    result = []
    for committee, _, _ in COMMITTEES:
        articles = sorted((a for a in winners.values() if a['committees'] == [committee]), key=importance_key)
        result.append({'id': committee, 'priority': [a for a in articles if a.get('categories')][:10], 'all': articles[:10]})
    return result


def validate_report(report: dict) -> None:
    start, end = window(report['date'], report['slot'])
    if report.get('period') != period_label(report['date'], report['slot']) or report.get('status') != 'published':
        raise ValueError('Invalid report metadata')
    if [c['id'] for c in report['committees']] != [c[0] for c in COMMITTEES]:
        raise ValueError('Committee order changed')
    owners = {}
    for committee in report['committees']:
        for kind in ('priority', 'all'):
            articles = committee[kind]
            if len(articles) > 10 or len({a['event_id'] for a in articles}) != len(articles):
                raise ValueError('Duplicate event or more than 10 articles')
            for article in articles:
                for identity in (('event', article['event_id']), ('url', article['url'])):
                    if owners.setdefault(identity, committee['id']) != committee['id']:
                        raise ValueError('Article/event repeated across committees')
                if not start <= validate_article(article) <= end or committee['id'] not in article['committees']:
                    raise ValueError('Wrong time window or committee')
                if kind == 'priority' and not article.get('categories'):
                    raise ValueError('Priority article has no industry category')
            if articles != sorted(articles, key=importance_key):
                raise ValueError('Articles are not sorted by importance')


def publish(review: dict, date: str, slot: str, output_dir: Path = REPORT_DIR) -> Path:
    if review.get('date') != date or review.get('slot') != slot or not review.get('search_log'):
        raise ValueError('Review must match requested date/slot and include a search log')
    if datetime.now(KST) < window(date, slot)[1]:
        raise ValueError('Cannot publish a completed report before the window ends')
    report = {'date': date, 'slot': slot, 'status': 'published', 'period': period_label(date, slot),
              'published_at': datetime.now(KST).isoformat(timespec='seconds'),
              'committees': select_articles(review['articles'], date, slot)}
    validate_report(report)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f'{date}-{slot}.json'
    temporary = path.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)
    return path


STYLE = '''<style>
.committee-reports{padding:10px 12px}.committee-slot{margin:0 0 12px;border:1px solid #e1e7ef;border-radius:9px;overflow:hidden}
.committee-slot>summary{padding:12px;background:#edf3fb;font-size:14px;font-weight:800;cursor:pointer;color:#0a2444}
.committee-period{padding:10px 12px;margin:0;color:#576477;font-size:11px;overflow-wrap:anywhere}
.committee-news{padding:0 12px 12px}.committee-news h3{font-size:13px;margin:14px 0 8px;color:#0a2444}
.committee-news h4{font-size:12px;margin:12px 0 7px}.committee-article{padding:10px 0;border-bottom:1px solid #e5e7eb;font-size:12px;overflow-wrap:anywhere}
.committee-article p{margin:5px 0}.committee-article a,.committee-all a{color:#185fa5;text-decoration:underline}
.committee-all{padding-left:17px;font-size:12px}.committee-all li{padding:5px 0;overflow-wrap:anywhere}
.committee-empty,.committee-status{font-size:12px;color:#687386}.committee-status{padding:0 12px}.committee-tag{font-size:10px;background:#e6f1fb;color:#185fa5;padding:2px 4px;border-radius:3px}
</style>'''


def render(date: str, directory: Path = REPORT_DIR) -> str:
    esc = html.escape
    parts = [STYLE, '<div class="committee-reports">']
    published = {}
    for name in ('morning', 'evening'):
        path = directory / f'{date}-{name}.json'
        if path.exists():
            published[name] = json.loads(path.read_text(encoding='utf-8'))
    active_slot = max(published, key=lambda name: (published[name].get('published_at', ''), name == 'evening'), default='morning')
    for slot in ('morning', 'evening'):
        path = directory / f'{date}-{slot}.json'
        report = json.loads(path.read_text(encoding='utf-8')) if path.exists() else None
        if report:
            validate_report(report)
            if report['date'] != date or report['slot'] != slot:
                raise ValueError(f'Report/file mismatch: {path}')
        span = '전일 17:00 - 당일 08:00' if slot == 'morning' else '당일 08:00 - 17:00'
        expanded = ' open' if slot == active_slot else ''
        parts.append(f'<details class="committee-slot" data-slot="{slot}"{expanded}><summary>{slot.title()} ({span})</summary>')
        parts.append(f'<p class="committee-period">📋 {slot.title()} 국회 상임위 주요 이슈 리포트<br>{period_label(date, slot)}</p>')
        parts.append('<p class="committee-status">발간 완료 · 시간대·중복 조건을 충족한 확인 기사만 수록</p>' if report else '<p class="committee-status">미발간</p>')
        for i, (key, name, short) in enumerate(COMMITTEES, start=1 if slot == 'morning' else 4):
            group = next((c for c in report['committees'] if c['id'] == key), None) if report else None
            parts.append(f'<div class="committee-news" data-committee="{key}"><h3>{i}. {name}({short})</h3>')
            for kind, label in (('priority', '우선산업 관련'), ('all', '전체 뉴스')):
                parts.append(f'<h4>[{label}]</h4>')
                articles = group[kind] if group else []
                if not articles:
                    message = '해당 시간대 수집된 뉴스 없음' if report else '아직 발간되지 않은 리포트입니다.'
                    parts.append(f'<p class="committee-empty">{message}</p>')
                elif kind == 'priority':
                    for a in articles:
                        clock = datetime.fromisoformat(a['published_at']).strftime('%H:%M')
                        tags = ' '.join(f'<span class="committee-tag">[{esc(tag)}]</span>' for tag in a['categories'])
                        member_line = f'<p>관련 의원: {esc(", ".join(a["members"]))} ({short})</p>' if a.get('members') else ''
                        parts.append(f'<article class="committee-article">{tags}<br><strong>{esc(a["title"])}</strong><p>요약: {esc(a["summary"])}</p>{member_line}<p>출처: {esc(a["press"])} / {clock}</p><a href="{esc(a["url"], quote=True)}" target="_blank" rel="noopener">링크: {esc(a["url"])}</a></article>')
                else:
                    parts.append('<ul class="committee-all">')
                    for a in articles:
                        clock = datetime.fromisoformat(a['published_at']).strftime('%H:%M')
                        member_line = f' · 관련 의원: {esc(", ".join(a["members"]))} ({short})' if a.get('members') else ''
                        parts.append(f'<li>{esc(a["title"])} ({esc(a["press"])}, {clock}){member_line} — <a href="{esc(a["url"], quote=True)}" target="_blank" rel="noopener">링크</a></li>')
                    parts.append('</ul>')
            parts.append('</div>')
        parts.append('</details>')
    parts.append('</div>')
    return ''.join(parts)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--slot', choices=('morning', 'evening'), required=True)
    parser.add_argument('--date', default=datetime.now(KST).date().isoformat())
    parser.add_argument('--input', required=True, type=Path, help='Source-reviewed candidate JSON')
    args = parser.parse_args()
    print(publish(json.loads(args.input.read_text(encoding='utf-8-sig')), args.date, args.slot))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
