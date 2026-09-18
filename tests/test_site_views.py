import unittest

from scripts.generate_html_report import render
from tools.assemble_site import split_report


class SiteViewsTest(unittest.TestCase):
    def test_future_generated_reports_publish_both_views(self):
        data = {'schedules': [{'time': '09:00', 'title': '일정 보존 확인'}]}
        daily, assembly = split_report(render(data, '2026-09-18'))
        self.assertNotIn('일정 보존 확인', daily)
        self.assertIn('일정 보존 확인', assembly)
        self.assertIn('../../schedules/2026-09-18.html', assembly)
        self.assertIn('section-num">5</span><span class="section-title">News Trend - Morning', daily)
        self.assertIn('section-num">6</span><span class="section-title">News Trend - Evening', daily)
        self.assertIn('section-num">1</span><span class="section-title">금일 주요 일정', assembly)
        self.assertIn('data-slot="morning"', assembly)
        self.assertIn('data-slot="evening"', assembly)
        self.assertEqual(assembly.count('class="committee-news"'), 6)
        self.assertNotIn('committee-slot', daily)

    def test_missing_schedule_fails_build_instead_of_losing_data(self):
        with self.assertRaises(ValueError):
            split_report('<html><body>unexpected format</body></html>')
