import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "generate_report_index.py"


class GenerateReportIndexTests(unittest.TestCase):
    def test_data_reports_are_source_and_existing_metadata_is_preserved(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            work = Path(temp_dir)
            (work / "data/reports").mkdir(parents=True)
            (work / "docs/reports").mkdir(parents=True)
            for date_text in ("2026-03-02", "2026-05-04"):
                (work / "data/reports" / f"{date_text}.report.json").write_text("{}", encoding="utf-8")
                (work / "docs/reports" / f"{date_text}.html").write_text(
                    f"<!doctype html><html><head><title>Daily Issue Report — {date_text}</title></head>"
                    f"<body><section class='section'><h1>Daily Issue Report</h1><p>{date_text}</p>"
                    f"<p>{'검증용 보고서 본문입니다. ' * 15}</p></section></body></html>",
                    encoding="utf-8",
                )

            preserved = {
                "date": "2026-05-04",
                "displayDate": "기존 라벨",
                "title": "기존 제목",
                "url": "reports/2026-05-04.html",
                "status": "발간",
                "fileName": "2026-05-04.html",
                "exists": True,
            }
            (work / "docs/report-index.json").write_text(
                json.dumps({"reports": [preserved]}, ensure_ascii=False), encoding="utf-8"
            )

            subprocess.run([sys.executable, str(SCRIPT)], cwd=work, check=True)

            docs_index = json.loads((work / "docs/report-index.json").read_text(encoding="utf-8"))
            public_index = json.loads((work / "public/report-index.json").read_text(encoding="utf-8"))
            self.assertEqual(docs_index["count"], 2)
            self.assertEqual(docs_index["availableDates"], ["2026-03-02", "2026-05-04"])
            self.assertEqual(next(item for item in docs_index["reports"] if item["date"] == "2026-05-04"), preserved)
            self.assertEqual(public_index, docs_index)


if __name__ == "__main__":
    unittest.main()
