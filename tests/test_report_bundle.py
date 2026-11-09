import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.report_bundle import ROOT, oil_targets, validate_bundle


class ReportBundleTests(unittest.TestCase):
    def test_monday_morning_requires_sunday_night(self):
        self.assertEqual(oil_targets('2026-11-09', 'morning'),
                         [('2026-11-09', 'morning'), ('2026-11-08', 'night')])

    def test_evening_does_not_require_night(self):
        self.assertEqual(oil_targets('2026-11-06', 'evening'), [('2026-11-06', 'evening')])

    def test_replay_missing_saved_review_cannot_start_live_collection(self):
        from tools.report_bundle import generate
        with tempfile.TemporaryDirectory() as temp, patch('tools.report_bundle.ROOT', Path(temp)), \
             patch('tools.report_bundle.run') as execute:
            with self.assertRaisesRegex(ValueError, 'saved committee source review'):
                generate('2026-11-06', 'morning', replay=True)
            execute.assert_not_called()

    def test_reissue_preserves_only_the_existing_news_slot(self):
        from scripts.generate_reports_range import has_completed_news_slot
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'report.json'
            path.write_text(json.dumps({'news_trend': {
                'articles': [{'title': 'Morning source'}],
                'summary': 'Morning summary', 'report_slot': 'morning',
            }}), encoding='utf-8')
            self.assertTrue(has_completed_news_slot(path, 'morning'))
            self.assertFalse(has_completed_news_slot(path, 'evening'))

    def test_legacy_done_marker_does_not_skip_an_incomplete_bundle(self):
        from scripts.report_run_status import main
        with tempfile.TemporaryDirectory() as temp:
            marker = Path(temp) / '2026-11-09.morning.done.json'
            marker.write_text('{"status":"done"}', encoding='utf-8')
            with patch('sys.argv', ['status', 'check', '--date', '2026-11-09', '--report-slot', 'morning', '--status-dir', temp]), \
                 patch.dict('os.environ', {}, clear=True), \
                 patch('tools.report_bundle.validate_bundle', side_effect=ValueError('Missing committee')):
                self.assertEqual(main(), 0)

    def test_mark_cannot_create_done_marker_for_partial_bundle(self):
        from scripts.report_run_status import main
        with tempfile.TemporaryDirectory() as temp, \
             patch('sys.argv', ['status', 'mark', '--date', '2026-11-09', '--report-slot', 'morning', '--status-dir', temp]), \
             patch('tools.report_bundle.validate_bundle', side_effect=ValueError('Missing oil')):
            with self.assertRaisesRegex(ValueError, 'Missing oil'):
                main()
            self.assertFalse((Path(temp) / '2026-11-09.morning.done.json').exists())

    def copy_bundle(self, target):
        for relative in ['docs/reports/2026-11-09.html', 'docs/report-index.json',
                         'data/reports/2026-11-09.report.json',
                         'data/committee-news/2026-11-09-morning.review.json',
                         'docs/assembly-content/issues/2026-11-09-morning.json',
                         'docs/assembly-content/manifest.json', 'docs/assembly-content/monitoring/index.html',
                         'oil/data/report-index.json', *[f'oil/{directory}/{stem}.{extension}'
                           for stem in ['2026-11-09-morning', '2026-11-08-night']
                           for directory, extension in [('data/reports', 'json'), ('reports', 'html')]]]:
            path = target / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, path)

    def test_partial_bundles_are_not_success(self):
        cases = ['oil/data/reports/2026-11-09-morning.json',
                 'oil/data/reports/2026-11-08-night.json',
                 'docs/assembly-content/issues/2026-11-09-morning.json',
                 'docs/assembly-content/monitoring/index.html']
        for missing in cases:
            with self.subTest(missing=missing), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                self.copy_bundle(root)
                (root / missing).unlink()
                with self.assertRaises((OSError, ValueError)):
                    validate_bundle(root, '2026-11-09', 'morning')

    def test_incorrect_committee_slot_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.copy_bundle(root)
            path = root / 'docs/assembly-content/issues/2026-11-09-morning.json'
            data = json.loads(path.read_text(encoding='utf-8'))
            data['slot'] = 'evening'
            path.write_text(json.dumps(data), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'target mismatch'):
                validate_bundle(root, '2026-11-09', 'morning')

    def test_fallback_requires_member_role_and_actual_context(self):
        from tools.committee_editorial_rules import classify
        roster = [dict(name='홍길동', committee='industry')]
        ambiguous = dict(title='기업 실적 증가', body='홍길동은 기업 행사에 참석했다.')
        statement = dict(title='산중위 홍길동 의원, 산업 정책 지원 촉구', body='홍길동 의원은 산업 정책 지원을 촉구했다.')
        decisions = classify([ambiguous, statement], roster)['decisions']
        self.assertFalse(decisions[0]['include'])
        self.assertTrue(decisions[1]['include'])
        self.assertEqual(decisions[1]['members'], ['홍길동'])
        self.assertEqual(decisions[1]['committees'], ['industry'])

    def test_workflow_waits_for_bundle_before_mark_and_commit(self):
        workflow = (ROOT / '.github/workflows/fetch_safetimes_schedule.yml').read_text(encoding='utf-8')
        self.assertLess(workflow.index('Generate and validate the complete report bundle'), workflow.index('Mark report slot done'))
        self.assertLess(workflow.index('Mark report slot done'), workflow.index('Commit collected data'))
        self.assertNotIn('gh workflow run oil-report.yml', workflow)
        self.assertIn('git add data/committee-news/ docs/assembly-content/ oil/data/ oil/reports/', workflow)
        self.assertEqual(workflow.count("env.PRESERVE_DAILY_NEWS != 'true'"), 2)

    def test_fresh_collection_checks_source_body_and_keeps_exclusions(self):
        from tools import collect_committee_news as collector
        html = ('<html><head><meta property="og:title" content="산업부 정책 발표">'
                '<meta property="og:site_name" content="연합뉴스">'
                '<meta property="article:published_time" content="2026-11-09T07:00:00+09:00">'
                '</head><body><article>' + '산업부가 산업 정책 지원 계획을 발표하고 제도 개선을 논의했다. ' * 15 + '</article></body></html>')
        response = unittest.mock.Mock(content=html.encode(), url='https://www.yna.co.kr/view/example')
        found = [{'title': '산업부 정책 발표', 'source': '연합뉴스', 'url': response.url},
                 {'title': '포털', 'source': '연합뉴스', 'url': 'https://v.daum.net/v/123'}]
        decision = dict(index=0, include=True, summary='산업부 산업 정책 지원 및 제도 개선 논의', event_id='policy',
                        committees=['industry'], members=[], speaker_role='policy', committee_reason='산업부 산업 정책 소관',
                        categories=[], category_reason='', importance=dict(legislation=0, impact=2, speaker=1))
        with tempfile.TemporaryDirectory() as temp, patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test'}), \
             patch.object(collector, 'TOPICS', {'industry': ['산업부']}), \
             patch.object(collector, 'collect_naver_public', return_value=found), \
             patch.object(collector, 'collect_daum_public', return_value=[]), \
             patch.object(collector, 'collect_google_rss', return_value=[]), \
             patch.object(collector.requests, 'get', return_value=response), \
             patch.object(collector, '_call_claude', return_value=json.dumps({'decisions': [decision]})):
            target = Path(temp) / 'review.json'
            collector.collect('2026-11-09', 'morning', target)
            review = json.loads(target.read_text(encoding='utf-8'))
            self.assertEqual(len(review['articles']), 1)
            self.assertTrue(review['articles'][0]['verified'])
            self.assertEqual(len(review['search_log']), 3)
            self.assertIn('Publisher original URL unresolved', review['exclusions'][0]['reason'])

    def test_search_outage_does_not_become_no_news(self):
        from tools import collect_committee_news as collector
        with tempfile.TemporaryDirectory() as temp, patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test'}), \
             patch.object(collector, 'TOPICS', {'industry': ['산업부']}), \
             patch.object(collector, 'collect_naver_public', side_effect=ValueError('blocked')), \
             patch.object(collector, 'collect_daum_public', side_effect=ValueError('blocked')), \
             patch.object(collector, 'collect_google_rss', side_effect=ValueError('blocked')):
            target = Path(temp) / 'review.json'
            with self.assertRaisesRegex(RuntimeError, 'All search providers failed'):
                collector.collect('2026-11-09', 'morning', target)
            self.assertFalse(target.exists())
            self.assertTrue(target.with_suffix('.collection.json').exists())


if __name__ == '__main__':
    unittest.main()
