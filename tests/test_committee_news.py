import copy
import json
import tempfile
import unittest
from pathlib import Path

from tools.committee_news import (ROOT, REPORT_DIR, COMMITTEES, LEGACY_COMMITTEES, window, period_label,
                                 select_articles, validate_report, publish, render, report_committees)


def article(**changes):
    value = dict(title='검증 기사', url='https://www.yna.co.kr/view/test', press='연합뉴스',
                 summary='사실 요약', event_id='event', committee_reason='소관 정책',
                 category_reason='직접 관련', time_evidence='최초 입력 확인', verified=True,
                 committees=['industry'], categories=['배터리'],
                 importance={'legislation': 1, 'impact': 2, 'speaker': 1},
                 published_at='2026-09-17T18:00:00+09:00')
    value.update(changes)
    if 'url' not in changes and 'event_id' in changes:
        value['url'] += '/' + changes['event_id']
    return value


class CommitteeNewsTest(unittest.TestCase):
    def test_cross_committee_event_and_url_deduplication(self):
        first = article()
        second = article(committees=['finance'], press='뉴스1')
        selected = select_articles([first, second], '2026-09-18', 'morning')
        self.assertEqual(sum(len(g['all']) for g in selected), 1)
        second['event_id'] = 'different-id-same-url'
        self.assertEqual(sum(len(g['all']) for g in select_articles([first, second], '2026-09-18', 'morning')), 1)

    def test_roster_mismatch_and_multiple_committees_rejected(self):
        for change in ({'committees': ['industry', 'finance']}, {'members': ['배준영']}):
            with self.assertRaises(ValueError):
                select_articles([article(**change)], '2026-09-18', 'morning')
        chosen = select_articles([article(committees=['finance'], members=['배준영'])], '2026-09-18', 'morning')
        self.assertEqual(chosen[2]['all'][0]['members'], ['배준영'])

    def test_roster_counts_and_roles(self):
        from tools.committee_news import committee_roster
        members = committee_roster()
        self.assertEqual([sum(m['committee'] == c[0] for m in members) for c in LEGACY_COMMITTEES], [24, 22, 24])
        self.assertEqual({m['name'] for m in members if m['role'] == '위원장'}, {'김성원', '조승래', '유동수'})

    def test_kst_month_boundary_and_both_slots(self):
        self.assertEqual(period_label('2026-01-01', 'morning'),
                         '수집 기간: 2025-12-31 17:00 ~ 2026-01-01 08:00 (KST)')
        start, end = window('2026-09-18', 'evening')
        self.assertEqual((start.hour, end.hour), (8, 17))
        self.assertEqual(start.utcoffset().total_seconds(), 32400)

    def test_original_time_filter_includes_boundaries(self):
        stamps = ['2026-09-17T16:59:59', '2026-09-17T17:00:00',
                  '2026-09-18T08:00:00', '2026-09-18T08:00:01']
        candidates = [article(event_id=str(i), published_at=s+'+09:00') for i, s in enumerate(stamps)]
        chosen = select_articles(candidates, '2026-09-18', 'morning')[0]['all']
        self.assertEqual({a['event_id'] for a in chosen}, {'1', '2'})

    def test_publisher_priority_dedupe_and_outside_window(self):
        candidates = [article(press='한국경제', url='https://www.hankyung.com/article/test'),
                      article(press='뉴시스', url='https://newsis.com/view/test'), article()]
        self.assertEqual(select_articles(candidates, '2026-09-18', 'morning')[0]['all'], [candidates[2]])
        candidates[2]['published_at'] = '2026-09-17T16:00:00+09:00'
        self.assertEqual(select_articles(candidates, '2026-09-18', 'morning')[0]['all'], [candidates[0]])

    def test_priority_and_general_news_are_independent_and_capped(self):
        candidates = [article(event_id=str(i), categories=[] if i < 11 else ['배터리'],
                       importance={'legislation': 3 if i < 11 else 0, 'impact': 1, 'speaker': 0})
                      for i in range(15)]
        group = select_articles(candidates, '2026-09-18', 'morning')[0]
        self.assertEqual(len(group['all']), 10)
        self.assertEqual(len(group['priority']), 4)
        self.assertTrue(all(not a['categories'] for a in group['all']))

    def test_unverified_or_timezone_free_news_rejected(self):
        for change in ({'verified': False}, {'published_at': '2026-09-17T18:00:00'},
                       {'categories': ['무관한 업종']}, {'category_reason': ''}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                select_articles([article(**change)], '2026-09-18', 'morning')

    def test_publish_preserves_other_slot_and_distinguishes_unpublished(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            review = dict(date='2026-09-18', slot='morning', search_log=['reviewed'], articles=[])
            path = publish(review, review['date'], review['slot'], directory)
            before = path.read_bytes()
            text = render('2026-09-18', directory)
            self.assertEqual(text.count('해당 시간대 수집된 뉴스 없음'), 6)
            self.assertEqual(text.count('아직 발간되지 않은 리포트입니다.'), 6)
            review['slot'] = 'evening'
            # Use a fully elapsed historical window independent of current test time.
            review['date'] = '2026-09-17'
            publish(review, review['date'], review['slot'], directory)
            self.assertEqual(path.read_bytes(), before)
            self.assertNotIn('검증 기사', render('2026-09-16', directory))

    def test_html_escapes_untrusted_article_text(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            review = dict(date='2026-09-18', slot='morning', search_log=['reviewed'],
                          articles=[article(title='<script>alert(1)</script>')])
            publish(review, review['date'], review['slot'], directory)
            result = render(review['date'], directory)
            self.assertNotIn('<script>', result)
            self.assertIn('&lt;script&gt;', result)

    def test_checked_in_reports_match_reviewed_candidates(self):
        for path in REPORT_DIR.glob('*.json'):
            with self.subTest(path=path):
                report = json.loads(path.read_text(encoding='utf-8'))
                validate_report(report)
                review_path = ROOT / 'data/committee-news' / f'{path.stem}.review.json'
                review = json.loads(review_path.read_text(encoding='utf-8'))
                self.assertTrue(review['search_log'])
                self.assertEqual(report['committees'], select_articles(review['articles'], report['date'], report['slot'], committees=report_committees(report)))
                self.assertTrue((ROOT / 'docs/reports' / f'{report["date"]}.html').exists())

    def test_report_validation_rejects_wrong_committee_or_time(self):
        report = dict(date='2026-09-18', slot='morning', status='published',
                      period=period_label('2026-09-18', 'morning'),
                      committees=select_articles([article()], '2026-09-18', 'morning'))
        for key, value in [('committees', ['finance']), ('published_at', '2026-09-18T09:00:00+09:00')]:
            invalid = copy.deepcopy(report)
            invalid['committees'][0]['priority'][0][key] = value
            with self.assertRaises(ValueError):
                validate_report(invalid)

    def test_both_slots_restart_numbering_and_legacy_is_not_relabelled(self):
        import re
        text = render('2026-09-18')
        slots = text.split('<details class="committee-slot"')[1:]
        self.assertEqual(len(slots), 2)
        for slot in slots:
            self.assertEqual(re.findall(r'<h3>(.*?)</h3>', slot), [
                '1. 산업통상자원중소벤처기업위원회(산중위)',
                '2. 기후에너지환경노동위원회(기노위)',
                '3. 재정경제기획위원회(재경위)',
            ])
            climate = slot.split('data-committee="climate_labor"')[1].split('</div>')[0]
            self.assertIn('미수집', climate)
            self.assertNotIn('수집된 뉴스 없음', climate)
            self.assertNotIn('<a ', climate)
            self.assertIn('<a ', slot.split('class="committee-legacy"')[1])

    def test_new_publication_rejects_old_scope_and_unconfirmed_climate_member(self):
        for change in ({'committees': ['affairs']},
                       {'committees': ['climate_labor'], 'members': ['배준영']}):
            with self.assertRaises(ValueError):
                select_articles([article(**change)], '2026-09-18', 'morning')
        chosen = select_articles([article(committees=['climate_labor'])], '2026-09-18', 'morning')
        self.assertEqual(chosen[1]['all'][0]['committees'], ['climate_labor'])


if __name__ == '__main__':
    unittest.main()
