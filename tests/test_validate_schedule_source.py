import unittest

from scripts.validate_schedule_source import validate_payload


class ValidateScheduleSourceTests(unittest.TestCase):
    def test_rejects_empty_success_placeholder(self):
        errors = validate_payload({
            "success": True,
            "date": "2026-07-10",
            "article_url": "",
            "raw_text": "",
        }, "2026-07-10")
        self.assertTrue(errors)

    def test_rejects_business_source_when_parser_returns_no_items(self):
        errors = validate_payload({
            "success": True,
            "date": "2026-07-10",
            "approved_date": "2026-07-10",
            "article_url": "https://www.safetimes.co.kr/news/articleView.html?idxno=1",
            "raw_text": "에너지와 석유 관련 안내문",
        }, "2026-07-10")
        self.assertTrue(any("사업 관련" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
