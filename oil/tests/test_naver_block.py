import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import collect_news


def http_error(status):
    return requests.HTTPError(f'{status} Client Error', response=Mock(status_code=status))


class NaverBlockTests(unittest.TestCase):
    def test_blocked_naver_is_skipped_and_reported_once(self):
        naver = Mock(side_effect=http_error(403))
        daum = Mock(return_value=[])
        google = Mock(return_value=[])
        with patch.dict('os.environ', {}, clear=False), \
             patch.object(collect_news, 'collect_naver_public', naver), \
             patch.object(collect_news, 'collect_daum_public', daum), \
             patch.object(collect_news, 'collect_google_rss', google):
            _, warnings, _ = collect_news.collect_all(delay=0)
        queries = len(collect_news.KEYWORDS + collect_news.EVENT_KEYWORDS)
        self.assertEqual(naver.call_count, 1)
        self.assertEqual(daum.call_count, queries)
        self.assertEqual(google.call_count, queries)
        self.assertEqual([w['message'] for w in warnings], ['naver blocked'])
        self.assertEqual(len(warnings[0]['skipped_queries']), queries)
        self.assertIn('Daum', warnings[0]['user_message'])

    def test_other_failures_still_warn_per_query(self):
        naver = Mock(return_value=[])
        daum = Mock(side_effect=ValueError('selector'))
        with patch.object(collect_news, 'collect_naver_public', naver), \
             patch.object(collect_news, 'collect_daum_public', daum), \
             patch.object(collect_news, 'collect_google_rss', Mock(return_value=[])):
            _, warnings, _ = collect_news.collect_all(delay=0)
        queries = len(collect_news.KEYWORDS + collect_news.EVENT_KEYWORDS)
        self.assertEqual(naver.call_count, queries)
        self.assertEqual(sum(w['portal'] == 'daum' for w in warnings), queries)
        self.assertEqual(warnings[0]['message'], 'public search coverage limit')
        self.assertNotIn('다음 페이지', warnings[0]['user_message'])


if __name__ == '__main__':
    unittest.main()
