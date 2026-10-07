import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from collect_news import collect_naver_public, collect_daum_public, parse_daum_results
from build_report import build_report
from enrich_news import parse_article_html
from collect_news import PartialCollectionError
import requests


class MonitoringCoverageTests(unittest.TestCase):
    def test_same_story_keeps_each_publisher_and_real_raw_count(self):
        base = dict(title='SK에너지 정유사 유가 담합 심의', snippet='공정위 심사보고서',
                    published_at='2026-10-07T12:00:00+09:00', url='https://press.test/a', verified=False)
        items = [dict(base, source='연합뉴스', portal='naver'), dict(base, source='뉴스1', portal='google'),
                 dict(base, source='지역신문', portal='daum'), dict(base, source='연합뉴스', portal='google')]
        report = build_report(dict(items=items, collection_total_raw_count=200), '2026-10-07', 'evening')
        self.assertEqual(report['total_raw_count'], 200)
        self.assertEqual(report['total_deduped_count'], 3)
        self.assertEqual(report['total_review_count'], 3)
        self.assertEqual(report['total_ok_count'], 0)

    def test_naver_accessibility_label_is_not_a_publisher_or_title(self):
        markup = '''<div class="card"><a data-heatmap-target=".prof"><img><span>새 창 열림</span></a>
        <span class="sds-comps-profile-info-title-text"><a data-heatmap-target=".prof">뉴스1<span>새 창 열림</span></a></span>
        <div><a data-heatmap-target=".tit" href="https://press.test/a">SK에너지 유가 담합<span>새 창 열림</span></a>
        <a data-heatmap-target=".body">공정위 심의</a>1시간 전</div></div>'''
        response = Mock(text=markup)
        with patch('collect_news.requests.get', return_value=response):
            rows = collect_naver_public('SK에너지 담합')
        self.assertEqual(rows[0]['source'], '뉴스1')
        self.assertEqual(rows[0]['title'], 'SK에너지 유가 담합')

    def page(self, page):
        return '<ul class="c-list-basic">' + ''.join(f'''<li><a class="item-writer" href="https://v.daum.net/channel/1/home"><strong class="tit_item">지역신문</strong></a>
        <div class="item-title"><a href="https://v.daum.net/v/{page}{i}">SK에너지 담합 보도 {page}-{i}</a></div><span class="gem-subinfo">1시간 전</span></li>''' for i in range(10)) + '</ul>'

    def test_daum_uses_article_title_and_follows_pages_until_repeat(self):
        pages = [self.page(1), self.page(2), self.page(2)]
        responses = [Mock(content=page.encode()) for page in pages]
        with patch('collect_news.requests.get', side_effect=responses) as get:
            rows = collect_daum_public('SK에너지 담합')
        self.assertEqual(len(rows), 20)
        self.assertEqual([call.kwargs['params']['p'] for call in get.call_args_list], [1, 2, 3])
        self.assertTrue(all('/v/' in row['url'] for row in rows))
        self.assertEqual(rows[0]['source'], '지역신문')

    def test_original_registration_precedes_newsis_modified_metadata(self):
        markup = '<meta property="article:published_time" content="2026-10-07T16:16:23+09:00"><meta property="og:title" content="SK에너지 담합">등록 2026.10.07 14:22:34 수정 2026.10.07 16:16:23<article>' + ('공정위 심사보고서 가격정보 담합 조사 문맥. ' * 35) + '</article>'
        row = parse_article_html(markup, 'https://www.newsis.com/view/example', '뉴시스')
        self.assertEqual(row['published_at'], '2026-10-07T14:22:34+09:00')
        self.assertTrue(row['verified'])

    def test_later_page_failure_keeps_collected_articles(self):
        with patch('collect_news.requests.get', side_effect=[Mock(content=self.page(1).encode()), requests.Timeout('page two')]):
            with self.assertRaises(PartialCollectionError) as raised:
                collect_daum_public('SK에너지 담합')
        self.assertEqual(len(raised.exception.items), 10)

    def test_unknown_and_outside_times_are_counted_separately(self):
        base = dict(title='정유사 유가 담합 심의', source='연합뉴스', url='https://press.test/a')
        report = build_report(dict(items=[dict(base, published_at=''), dict(base, title='다른 정유사 담합', published_at='2026-10-07T17:01:00+09:00')]), '2026-10-07', 'evening')
        self.assertEqual(report['total_unknown_time_count'], 1)
        self.assertEqual(report['total_outside_period_count'], 1)
        self.assertEqual(report['total_deduped_count'], 0)
