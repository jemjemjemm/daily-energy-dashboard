import json
import tempfile
import unittest
from pathlib import Path

from scripts.generate_reports_range import valid_schedule_file


class SchedulePublicationValidationTests(unittest.TestCase):
    def write_payload(self, directory: str, payload: dict) -> str:
        path = Path(directory) / "schedule.json"
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return str(path)

    def test_rejects_success_placeholder_without_source_or_body(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_payload(directory, {
                "success": True,
                "date": "2026-07-10",
                "article_url": "",
                "raw_text": "",
                "items": [],
            })
            self.assertFalse(valid_schedule_file(path, "2026-07-10"))

    def test_accepts_source_backed_schedule(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_payload(directory, {
                "success": True,
                "date": "2026-07-10",
                "article_url": "https://www.safetimes.co.kr/news/articleView.html?idxno=244094",
                "raw_text": "▲ IEA, 월간 석유리포트",
            })
            self.assertTrue(valid_schedule_file(path, "2026-07-10"))


if __name__ == "__main__":
    unittest.main()
