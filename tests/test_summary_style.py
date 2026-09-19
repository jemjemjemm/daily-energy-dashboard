import unittest
from scripts.summary_style import nominal_summary
from scripts.generate_html_report import render_summary


class SummaryStyleTest(unittest.TestCase):
    def test_bullet_actions_and_multiple_sentences(self):
        self.assertEqual(nominal_summary('△할인을 발표했다. △업계 수요를 점검했다.'), '△할인을 발표 △업계 수요를 점검')
        self.assertEqual(nominal_summary('구속심문이 진행됐다. 구속 여부는 결정되지 않았다.'), '구속심문이 진행 · 구속 여부는 미결정')
        self.assertEqual(nominal_summary('유가가 올랐다는 내용'), '유가가 상승')
        self.assertEqual(nominal_summary('WTI 101.91달러에 마감함'), 'WTI 101.91달러에 마감')

    def test_manual_summary_uses_same_style_at_render_boundary(self):
        result = render_summary({'summary':[{'type':'news_trend','text':'(Evening) △정책 발표했다. △수요 점검했다.'}]})
        self.assertIn('정책 발표 △수요 점검', result)
        self.assertNotIn('했다', result)
