from __future__ import annotations

import unittest
import json
from pathlib import Path
import requests

from datetime import date

from scripts.fetch_assembly_schedule import (
    ROW_FIELDS,
    AssemblyAPIError,
    decode_response,
    fetch_month,
    parse_date,
    should_refresh_month,
)


class AssemblyScheduleResponseTest(unittest.TestCase):
    def test_current_and_future_month_caches_are_always_refreshed(self) -> None:
        today = date(2026, 7, 22)

        self.assertFalse(should_refresh_month("2026-06", today=today))
        self.assertTrue(should_refresh_month("2026-07", today=today))
        self.assertTrue(should_refresh_month("2026-08", today=today))

    def test_daily_workflow_explicitly_forces_assembly_refresh(self) -> None:
        workflow = Path(".github/workflows/fetch_safetimes_schedule.yml").read_text(encoding="utf-8")
        self.assertIn(
            'python scripts/fetch_assembly_schedule.py --date "$TARGET_DATE" --force-refresh',
            workflow,
        )

    def test_decodes_actual_allschedule_shape(self) -> None:
        payload = {
            "ALLSCHEDULE": [
                {"head": [{"list_total_count": 1}, {"RESULT": {"CODE": "INFO-000", "MESSAGE": "정상 처리되었습니다."}}]},
                {"row": [{field: None for field in ROW_FIELDS}]},
            ]
        }
        total, rows = decode_response(payload)
        self.assertEqual(total, 1)
        self.assertEqual(len(rows), 1)
        self.assertEqual(tuple(rows[0]), ROW_FIELDS)

    def test_no_data_result_is_not_an_error(self) -> None:
        self.assertEqual(decode_response({"RESULT": {"CODE": "INFO-200", "MESSAGE": "해당하는 데이터가 없습니다."}}), (0, []))

    def test_authentication_error_is_rejected(self) -> None:
        with self.assertRaises(AssemblyAPIError):
            decode_response({"RESULT": {"CODE": "ERROR-300", "MESSAGE": "인증키가 유효하지 않습니다."}})

    def test_dashboard_does_not_load_assembly_calendar_decorations(self) -> None:
        for html_path in (Path("public/index.html"), Path("docs/index.html")):
            html = html_path.read_text(encoding="utf-8")
            self.assertNotIn("assets/assembly-calendar.css", html)
            self.assertNotIn("assets/assembly-calendar.js", html)
            self.assertIn("dataset.date", html)

    def test_form_encoded_date_separator_is_normalized(self) -> None:
        self.assertEqual(parse_date("2026+07-13").isoformat(), "2026-07-13")
        self.assertEqual(parse_date("2026 / 07 / 15").isoformat(), "2026-07-15")

    def test_generated_schedule_contains_no_api_key_field(self) -> None:
        path = Path("data/assembly/2026-07-15.json")
        if not path.exists():
            self.skipTest("실응답 파일이 없는 환경")
        payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertNotIn("KEY", json.dumps(payload, ensure_ascii=False))
        self.assertNotIn("ASSEMBLY_API_KEY", json.dumps(payload, ensure_ascii=False))

    def test_request_failure_does_not_expose_key(self) -> None:
        class FailingSession:
            def get(self, *_args, **_kwargs):
                raise requests.ConnectionError("request URL contained secret-value")

        with self.assertRaises(AssemblyAPIError) as caught:
            fetch_month(FailingSession(), "secret-value", "2026-07", 1)
        self.assertNotIn("secret-value", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
