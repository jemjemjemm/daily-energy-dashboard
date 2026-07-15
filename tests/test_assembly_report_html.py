from __future__ import annotations

import unittest

from scripts.generate_html_report import render


class AssemblyReportHtmlTest(unittest.TestCase):
    def test_assembly_sections_render_directly_below_daily_schedule(self) -> None:
        report = {
            "report": {"report_date": "2026-07-15"},
            "summary": [{"text": "요약"}],
            "schedules": [{"time": "09:00", "title": "기존 금일 일정", "attendees": "산업부"}],
            "news_trend": {"summary": "△정유 뉴스 요약", "articles": []},
            "prices": {},
        }
        assembly = {
            "month": "2026-07",
            "items": [
                {
                    "SCH_KIND": "위원회",
                    "SCH_CN": "산업통상자원중소벤처기업위원회 전체회의",
                    "SCH_DT": "2026-07-15",
                    "SCH_TM": "10:00",
                    "CMIT_NM": "산업통상자원중소벤처기업위원회",
                    "CONF_DIV": "전체회의",
                    "CONF_SESS": "1",
                    "CONF_DGR": "2",
                    "EV_INST_NM": None,
                    "EV_PLC": None,
                },
                {
                    "SCH_KIND": "국회행사",
                    "SCH_CN": "에너지 정책 토론회",
                    "SCH_DT": "2026-07-16",
                    "SCH_TM": "14:00",
                    "CMIT_NM": None,
                    "CONF_DIV": None,
                    "CONF_SESS": None,
                    "CONF_DGR": None,
                    "EV_INST_NM": "의원실",
                    "EV_PLC": "의원회관",
                },
            ],
        }

        html = render(report, "2026-07-15", assembly)

        schedule_pos = html.index("기존 금일 일정")
        assembly_pos = html.index("본회의 · 상임위 일정")
        news_pos = html.index("News Trend - Morning")
        self.assertLess(schedule_pos, assembly_pos)
        self.assertLess(assembly_pos, news_pos)
        self.assertIn("월간 국회 일정 캘린더", html)
        self.assertIn("data-assembly-report-date=\"2026-07-16\"", html)
        self.assertNotIn("assembly-report-count", html)
        self.assertIn('id="assemblyReportModal"', html)
        self.assertIn('class="assembly-report-modal"', html)
        self.assertIn('id="scheduleDetailModal"', html)
        self.assertNotEqual(html.index('id="assemblyReportModal"'), html.index('id="scheduleDetailModal"'))


if __name__ == "__main__":
    unittest.main()
