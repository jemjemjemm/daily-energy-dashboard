import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts.generate_reports_range import fetch_schedule, valid_schedule_file


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
                "raw_text": "■ 분야별\n[정치]\n[산업]\n▲ IEA, 월간 석유리포트\n" + ("10:00 산업부 회의\n" * 30),
            })
            self.assertTrue(valid_schedule_file(path, "2026-07-10"))

    def test_rejects_partial_source_backed_schedule(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_payload(directory, {
                "success": True,
                "date": "2026-07-10",
                "article_url": "https://www.safetimes.co.kr/news/articleView.html?idxno=244094",
                "raw_text": "photo lead only",
            })
            self.assertFalse(valid_schedule_file(path, "2026-07-10"))

    def test_failed_fetch_keeps_existing_file_and_returns_false(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "2026-07-15.json"
            original = '{"success": false, "marker": "keep-me"}'
            path.write_text(original, encoding="utf-8")
            args = SimpleNamespace(schedule_dir=directory, max_pages="1")

            with patch("scripts.generate_reports_range.run", return_value=False):
                self.assertFalse(fetch_schedule(args, "2026-07-15", str(path)))

            self.assertEqual(path.read_text(encoding="utf-8"), original)


if __name__ == "__main__":
    unittest.main()
