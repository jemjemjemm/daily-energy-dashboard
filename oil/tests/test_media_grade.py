import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from media_grade import get_media_grade, normalize_media_name


class MediaGradeTests(unittest.TestCase):
    def test_grade_a_media_and_aliases(self):
        sources = [
            "조선일보", "중앙일보", "동아일보", "한국일보", "한겨레", "경향신문",
            "국민일보", "서울신문", "세계일보", "문화일보", "내일신문",
            "매일경제", "매경", "한국경제", "한경", "서울경제", "머니투데이",
            "이데일리", "파이낸셜 뉴스", "헤럴드 경제", "아시아경제", "전자신문",
            "디지털타임스", "연합뉴스", "뉴시스", "뉴스1", "news1",
        ]

        for source in sources:
            with self.subTest(source=source):
                self.assertEqual(get_media_grade(source), "A")

    def test_grade_b_media_and_aliases(self):
        sources = [
            "뉴스핌", "아시아투데이", "아주경제", "이투데이", "뉴스토마토",
            "KBS", "MBC", "SBS", "JTBC", "채널A", "TV조선", "MBN",
            "더벨", "인베스트조선", "연합인포맥스",
            "조선Biz", "조선비즈", "EBN", "뉴데일리", "데일리안",
            "YTN", "ytn", "연합뉴스TV", "연합뉴스 tv",
        ]

        for source in sources:
            with self.subTest(source=source):
                self.assertEqual(get_media_grade(source), "B")

    def test_grade_c_fallback(self):
        sources = [
            "매일경제TV", "한국경제TV", "MTN",
            "더구루", "신아일보", "한스경제", "매일일보", "비즈워치", "조세일보",
            "블로터", "미디어펜", "알 수 없는 매체",
        ]

        for source in sources:
            with self.subTest(source=source):
                self.assertEqual(get_media_grade(source), "C")

    def test_similar_names_are_not_partially_matched(self):
        self.assertEqual(get_media_grade("연합뉴스TV"), "B")
        self.assertEqual(get_media_grade("한국경제TV"), "C")
        self.assertEqual(get_media_grade("매일경제TV"), "C")
        self.assertEqual(get_media_grade("조선Biz"), "B")

    def test_normalization_keeps_news_agency_tv_distinct(self):
        self.assertEqual(normalize_media_name("연합뉴스 tv"), "연합뉴스TV")
        self.assertEqual(normalize_media_name("연합뉴스"), "연합뉴스")


if __name__ == "__main__":
    unittest.main()
