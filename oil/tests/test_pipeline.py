import sys
import unittest
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from dedupe import canonicalize_url, deduplicate, normalize_title
from build_report import build_report, format_report_title, process_articles
from media_grade import get_media_grade, normalize_source
from quality_filter import assess_quality
from utils_time import KST, get_period, is_in_period
from collect_news import KEYWORDS


class TimeTests(unittest.TestCase):
    def test_morning_period_is_half_open(self):
        start, end = get_period(date(2026, 6, 19), "morning")
        self.assertEqual(start.isoformat(), "2026-06-19T00:00:00+09:00")
        self.assertEqual(end.isoformat(), "2026-06-19T08:00:00+09:00")
        self.assertTrue(is_in_period(start, start, end))
        self.assertFalse(is_in_period(end, start, end))

    def test_evening_period_is_half_open(self):
        start, end = get_period("2026-06-19", "evening")
        self.assertEqual(start.hour, 8)
        self.assertEqual(end.hour, 17)
        self.assertTrue(is_in_period(datetime(2026, 6, 19, 16, 59, tzinfo=KST), start, end))

    def test_night_period_is_half_open(self):
        start, end = get_period("2026-06-20", "night")
        self.assertEqual(start.isoformat(), "2026-06-20T17:00:00+09:00")
        self.assertEqual(end.isoformat(), "2026-06-21T00:00:00+09:00")
        self.assertTrue(is_in_period(datetime(2026, 6, 20, 23, 59, 59, tzinfo=KST), start, end))
        self.assertFalse(is_in_period(end, start, end))


class DedupeTests(unittest.TestCase):
    def item(self, portal, source="연합뉴스", title="[속보] 정유사 담합 조사", url="https://example.com/a"):
        return {"portal": portal, "query": "유가담합", "source": source, "title": title, "url": url, "published_at": "", "collected_at": "2026-06-19T08:00:00+09:00", "snippet": ""}

    def test_same_title_and_source_merge_portals(self):
        result = deduplicate([self.item("naver"), self.item("daum", title="정유사 담합 조사")])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["portals"], ["naver", "daum"])
        self.assertEqual(result[0]["duplicate_count"], 1)

    def test_same_title_different_source_is_retained(self):
        result = deduplicate([self.item("naver"), self.item("google", source="뉴스1")])
        self.assertEqual(len(result), 2)

    def test_title_decoration_removed_for_comparison(self):
        self.assertEqual(normalize_title(" [단독]  유가  담합 (종합) "), "유가 담합")

    def test_portal_redirect_url_is_unwrapped(self):
        url = "https://search.example/redirect?url=https%3A%2F%2Fpress.example%2Farticle"
        self.assertEqual(canonicalize_url(url), "https://press.example/article")


class ClassificationTests(unittest.TestCase):
    def test_media_grades_and_aliases(self):
        self.assertEqual(normalize_source("매경"), "매일경제")
        self.assertEqual(get_media_grade("연합뉴스"), "A")
        self.assertEqual(get_media_grade("YTN"), "B")
        self.assertEqual(get_media_grade("지역매체"), "C")

    def test_updated_media_grades(self):
        grade_a = [
            "조선일보", "중앙일보", "동아일보", "한국일보", "한겨레", "경향신문",
            "국민일보", "서울신문", "세계일보", "문화일보", "내일신문",
            "매일경제", "매경", "한국경제", "한경", "서울경제", "머니투데이",
            "이데일리", "파이낸셜 뉴스", "헤럴드 경제", "아시아경제", "전자신문",
            "디지털타임스", "연합뉴스", "뉴시스", "뉴스1", "news1",
        ]
        grade_b = [
            "뉴스핌", "아시아투데이", "아주경제", "이투데이", "뉴스토마토",
            "KBS", "MBC", "SBS", "JTBC", "채널A", "TV조선", "MBN",
            "더벨", "인베스트조선", "연합인포맥스", "조선Biz", "조선비즈",
            "EBN", "뉴데일리", "데일리안", "YTN", "ytn", "연합뉴스TV",
            "연합뉴스 tv",
        ]
        grade_c = [
            "매일경제TV", "한국경제TV", "MTN", "더구루", "신아일보", "한스경제",
            "매일일보", "비즈워치", "조세일보", "블로터", "미디어펜",
            "알 수 없는 매체",
        ]
        for source in grade_a:
            with self.subTest(source=source):
                self.assertEqual(get_media_grade(source), "A")
        for source in grade_b:
            with self.subTest(source=source):
                self.assertEqual(get_media_grade(source), "B")
        for source in grade_c:
            with self.subTest(source=source):
                self.assertEqual(get_media_grade(source), "C")

    def test_similar_media_names_are_not_partially_matched(self):
        self.assertEqual(get_media_grade("연합뉴스TV"), "B")
        self.assertEqual(get_media_grade("한국경제TV"), "C")
        self.assertEqual(get_media_grade("매일경제TV"), "C")
        self.assertEqual(get_media_grade("조선Biz"), "B")

    def test_excluded_and_review_status(self):
        excluded = assess_quality({"title": "오늘의 스포츠 유가 소식 담합", "snippet": "", "published_at": "x", "source": "YTN", "url": "https://x"})
        self.assertEqual(excluded[0], "excluded")
        review = assess_quality({"title": "정유사 담합 조사", "snippet": "", "published_at": "", "source": "연합뉴스", "url": "https://x"})
        self.assertEqual(review[0], "review")

    def test_food_price_article_is_excluded(self):
        item = {
            "title": "브라질산 계란 수입 돼지 닭고기 할당관세… 여름철 먹거리 물가 잡는다",
            "snippet": "정부가 여름철 장바구니 물가 안정을 위해 농축산물 할당관세를 추진한다.",
            "published_at": "2026-06-19T12:00:00+09:00", "source": "연합뉴스",
            "url": "https://example.com/food-price",
        }
        self.assertEqual(assess_quality(item)[0], "excluded")

    def test_all_required_queries_are_configured(self):
        self.assertEqual(len(KEYWORDS), 13)
        self.assertIn("공정거래위원회 정유사 담합", KEYWORDS)


class ReportTests(unittest.TestCase):
    def test_report_title_uses_short_date_and_slot(self):
        self.assertEqual(format_report_title("2026-06-19", "morning"), "'26.6.19. Morning Report")
        self.assertEqual(format_report_title("2026-07-03", "evening"), "'26.7.3. Evening Report")
        self.assertEqual(format_report_title("2026-06-20", "night"), "'26.6.20. Night Report")

    def test_unknown_publication_time_is_removed(self):
        start, end = get_period("2026-06-19", "morning")
        item = {
            "portal": "google", "query": "유가 담합", "title": "정유사 담합 조사",
            "url": "https://example.com/a", "source": "연합뉴스", "published_at": "",
            "collected_at": "2026-06-19T08:10:00+09:00", "snippet": "공정위가 유가 담합을 조사한다.",
        }
        articles = process_articles([item], start, end)
        self.assertEqual(articles, [])

    def test_previous_day_article_is_removed_from_morning_report(self):
        start, end = get_period("2026-06-19", "morning")
        item = {
            "portal": "google", "query": "유가 담합", "title": "정유사 담합 조사",
            "url": "https://example.com/previous-day", "source": "연합뉴스",
            "published_at": "2026-06-18T23:59:59+09:00",
            "collected_at": "2026-06-19T08:10:00+09:00", "snippet": "",
        }
        self.assertEqual(process_articles([item], start, end), [])

    def test_known_out_of_period_article_is_removed(self):
        start, end = get_period("2026-06-19", "morning")
        item = {
            "portal": "naver", "query": "유가 담합", "title": "정유사 담합 조사",
            "url": "https://example.com/a", "source": "연합뉴스",
            "published_at": "2026-06-19T08:00:00+09:00",
            "collected_at": "2026-06-19T08:10:00+09:00", "snippet": "",
        }
        self.assertEqual(process_articles([item], start, end), [])

    def test_excluded_article_is_not_exposed_but_relevant_article_is(self):
        start, end = get_period("2026-06-19", "evening")
        food_item = {
            "title": "브라질산 계란 수입 돼지 닭고기 할당관세… 여름철 먹거리 물가 잡는다",
            "snippet": "정부가 여름철 장바구니 물가 안정을 위해 농축산물 할당관세를 추진한다.",
            "published_at": "2026-06-19T12:00:00+09:00", "source": "연합뉴스",
            "url": "https://example.com/food-price",
        }
        relevant_item = {
            "title": "공정위, 정유사 유가 담합 의혹 조사 착수",
            "snippet": "휘발유와 경유 등 석유제품 가격 담합 여부를 들여다본다.",
            "published_at": "2026-06-19T12:00:00+09:00", "source": "연합뉴스",
            "url": "https://example.com/oil-collusion",
        }
        self.assertEqual(process_articles([food_item], start, end), [])
        self.assertNotEqual(assess_quality(relevant_item)[0], "excluded")
        articles = process_articles([relevant_item], start, end)
        self.assertEqual(len(articles), 1)
        self.assertEqual(articles[0]["url"], relevant_item["url"])

    def test_zero_result_report_is_still_complete(self):
        raw = {"items": [], "keywords": KEYWORDS, "portal_counts": {}, "collection_warnings": []}
        report = build_report(raw, "2026-06-19", "evening")
        self.assertEqual(report["total_deduped_count"], 0)
        self.assertEqual(report["articles"], [])
        self.assertEqual(report["grade_counts"], {"A": 0, "B": 0, "C": 0})


if __name__ == "__main__":
    unittest.main()
