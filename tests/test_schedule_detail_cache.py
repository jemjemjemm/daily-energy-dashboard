import unittest

from scripts.generate_html_report import SCHEDULE_DETAIL_SCRIPT


class ScheduleDetailCacheTest(unittest.TestCase):
    def test_modal_uses_unique_url_for_each_open(self) -> None:
        self.assertIn("Date.now()", SCHEDULE_DETAIL_SCRIPT)
        self.assertIn("frame.src = freshSrc", SCHEDULE_DETAIL_SCRIPT)
        self.assertIn("fetch(freshSrc", SCHEDULE_DETAIL_SCRIPT)


if __name__ == "__main__":
    unittest.main()
