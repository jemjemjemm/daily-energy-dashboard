import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.sync_assembly_content import monitoring_view, sync


SOURCE = '''<!doctype html><html><head><style>.panel{display:none}</style></head><body>
<section id="panel-plan">예정 일정</section>
<section class="panel" id="panel-done"><details open><summary>9월</summary>
<table><tr class="done-row"><td>회의 A</td><td><button class="report-btn" data-target="report-1">보기</button></td></tr>
<tr class="done-row"><td>취소 회의</td><td>취소</td></tr></table></details></section>
<div class="modal-overlay" id="modalOverlay"><div id="modalBody"></div></div>
<script>var REPORTS = {"report-1":"첫 줄\\n둘째 줄 · 원문 <보존>"};</script></body></html>'''


class MonitoringSyncTest(unittest.TestCase):
    def test_completed_rows_and_full_report_text_are_preserved(self):
        html, counts = monitoring_view(SOURCE)
        self.assertEqual(counts['meetings'], 2)
        self.assertEqual(counts['reports'], 1)
        self.assertNotIn('예정 일정', html)
        self.assertIn('취소 회의', html)
        self.assertIn('첫 줄\\n둘째 줄 · 원문 <보존>', html)
        self.assertIn('id="modalOverlay"', html)

    def test_missing_body_or_changed_source_fails_closed(self):
        for source in (SOURCE.replace('data-target="report-1"', 'data-target="missing"'), '<html>error</html>'):
            with self.subTest(source=source), self.assertRaises(ValueError):
                monitoring_view(source)

    def test_refresh_replaces_snapshot_only_after_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            with patch('tools.sync_assembly_content.download', return_value=SOURCE.encode()):
                sync(output)
            saved = (output / 'monitoring/index.html').read_bytes()
            with patch('tools.sync_assembly_content.download', return_value=b'<html>unavailable</html>'):
                with self.assertRaises(ValueError):
                    sync(output)
            self.assertEqual(saved, (output / 'monitoring/index.html').read_bytes())
            updated = SOURCE.replace('회의 A', '새 회의 B')
            with patch('tools.sync_assembly_content.download', return_value=updated.encode()):
                sync(output)
            self.assertIn('새 회의 B', (output / 'monitoring/index.html').read_text(encoding='utf-8'))
            manifest = json.loads((output / 'manifest.json').read_text(encoding='utf-8'))
            self.assertEqual(manifest['monitoring']['reports'], 1)


if __name__ == '__main__':
    unittest.main()
