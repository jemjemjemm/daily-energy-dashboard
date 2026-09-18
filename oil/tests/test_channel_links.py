import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from quality_filter import assess_quality

class ChannelLinks(unittest.TestCase):
    def test_channel_with_article_snippet_is_excluded(self):
        item = dict(title='머니투데이', snippet='정유사 유가 담합 사건',
                    source='머니투데이', published_at='2026-09-18T12:00:00+09:00',
                    url='https://v.daum.net/channel/5/home')
        self.assertEqual(assess_quality(item)[0], 'excluded')
        item['url'] = 'https://v.daum.net/v/20260918115607738'
        self.assertEqual(assess_quality(item)[0], 'ok')
