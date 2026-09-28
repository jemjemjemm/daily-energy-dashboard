import re
import unittest
from datetime import date
from pathlib import Path

from scripts.kr_holidays import KOREAN_HOLIDAYS, is_business_day, previous_business_day

ROOT = Path(__file__).resolve().parents[1]


class KoreanHolidayTests(unittest.TestCase):
    def test_chuseok_2026(self):
        self.assertFalse(is_business_day(date(2026, 9, 25)))
        self.assertTrue(is_business_day(date(2026, 9, 28)))
        self.assertEqual(previous_business_day(date(2026, 9, 28)), date(2026, 9, 23))
        self.assertEqual(previous_business_day(date(2026, 9, 29)), date(2026, 9, 28))

    def test_no_other_holiday_copies(self):
        # Separate copies drifted apart on 2026-09-28; keep one source of truth.
        pattern = re.compile(r'"2026-10-09"')
        paths = [*ROOT.glob("scripts/*.py"), *ROOT.glob(".github/workflows/*.yml")]
        offenders = [
            p.relative_to(ROOT).as_posix()
            for p in paths
            if p.name != "kr_holidays.py" and pattern.search(p.read_text(encoding="utf-8"))
        ]
        self.assertEqual(offenders, [])

    def test_source_validator_agrees_with_workflow(self):
        from scripts import validate_report_sources, ensure_report_draft
        self.assertEqual(validate_report_sources.prev_workday(date(2026, 9, 29)), date(2026, 9, 28))
        self.assertEqual(ensure_report_draft.previous_workday("2026-09-29"), date(2026, 9, 28))
        self.assertIn("2026-09-26", KOREAN_HOLIDAYS)
        self.assertNotIn("2026-09-28", KOREAN_HOLIDAYS)


if __name__ == "__main__":
    unittest.main()
