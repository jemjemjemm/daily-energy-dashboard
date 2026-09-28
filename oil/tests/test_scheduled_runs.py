import json
import sys
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_report import is_reviewed_report
from utils_time import KST, SCHEDULE_SLOTS, resolve_scheduled_target


class ScheduledTargetTests(unittest.TestCase):
    def at(self, text):
        return datetime.fromisoformat(text).replace(tzinfo=KST)

    def test_delayed_evening_run_after_midnight_keeps_previous_evening(self):
        # 2026-09-21 17:10 run actually started at 2026-09-22 00:03.
        self.assertEqual(
            resolve_scheduled_target("10 8 * * *", self.at("2026-09-22T00:03")),
            (date(2026, 9, 21), "evening"),
        )

    def test_delayed_evening_run_same_day(self):
        self.assertEqual(
            resolve_scheduled_target("10 8 * * *", self.at("2026-09-27T22:52")),
            (date(2026, 9, 27), "evening"),
        )

    def test_delayed_morning_run(self):
        self.assertEqual(
            resolve_scheduled_target("10 23 * * *", self.at("2026-09-28T10:35")),
            (date(2026, 9, 28), "morning"),
        )

    def test_crons_match_workflow(self):
        workflow = (ROOT.parent / ".github" / "workflows" / "oil-report.yml").read_text(encoding="utf-8")
        for cron in SCHEDULE_SLOTS:
            self.assertIn(f'cron: "{cron}"', workflow)


class ReviewedReportTests(unittest.TestCase):
    def write(self, payload):
        handle = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
        with handle:
            json.dump(payload, handle, ensure_ascii=False)
        self.addCleanup(Path(handle.name).unlink)
        return Path(handle.name)

    def test_generated_report_is_not_reviewed(self):
        self.assertFalse(is_reviewed_report(self.write({"articles": [{"id": "a"}]})))

    def test_report_summary_marks_reviewed(self):
        self.assertTrue(is_reviewed_report(self.write({"summary": ["요약"], "articles": []})))

    def test_verified_article_marks_reviewed(self):
        self.assertTrue(is_reviewed_report(self.write({"articles": [{"id": "a", "verified": True}]})))

    def test_missing_file_is_not_reviewed(self):
        self.assertFalse(is_reviewed_report(ROOT / "data" / "reports" / "1999-01-01-morning.json"))


if __name__ == "__main__":
    unittest.main()
