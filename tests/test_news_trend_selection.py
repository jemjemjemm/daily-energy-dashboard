#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import unittest

from bs4 import BeautifulSoup

from scripts.apply_news_to_report import (
    build_news_summary,
    normalize_article,
    select_representative_articles,
    update_summary,
)
from scripts.fetch_news_candidates import PLAIN_QUERIES, daum_card_press, trusted_direct_count
from scripts.news_article_rules import is_forbidden_press, normalize_article_url, resolve_press


class NewsTrendSelectionTest(unittest.TestCase):
    def test_daum_press_falls_back_to_snippet_and_normalizes_portal_url(self) -> None:
        item = {
            "title": "미국산이 사우디 넘었다... 정유 업계 원유 조달 다변화",
            "press": "Daum News",
            "url": "http://v.daum.net/v/20260529060054788",
            "snippet": "파이낸셜뉴스 개별문서메뉴 톡으로 바로 공유 공유하기 기사 본문",
        }

        article = normalize_article(item)

        self.assertEqual(article["press"], "파이낸셜뉴스")
        self.assertEqual(article["press_grade"], "A")
        self.assertEqual(article["url"], "https://v.daum.net/v/20260529060054788")

    def test_daum_press_prefers_card_selector(self) -> None:
        soup = BeautifulSoup(
            '<li><span class="txt_info">연합뉴스 언론사 픽</span><a class="tit_main" href="#">국제유가 상승</a></li>',
            "html.parser",
        )

        press = daum_card_press(soup.li, "국제유가 상승", "https://v.daum.net/v/1", "")

        self.assertEqual(press, "연합뉴스")

    def test_original_url_query_is_unwrapped(self) -> None:
        link = "https://example.test/redirect?url=https%3A%2F%2Fwww.yna.co.kr%2Fview%2F1"

        self.assertEqual(normalize_article_url(link), "https://www.yna.co.kr/view/1")
        self.assertEqual(resolve_press({"url": normalize_article_url(link)}), "연합뉴스")

    def test_representatives_prioritize_trusted_press_and_limit_c_grade(self) -> None:
        candidates = [
            normalize_article({
                "title": "국제유가 급등과 원유 수급 경고",
                "press": "Daum News",
                "url": "https://v.daum.net/v/portal",
                "snippet": "국제유가 원유",
                "score": 99,
            }),
            normalize_article({
                "title": "국제유가 급등과 원유 수급 분석",
                "press": "연합뉴스",
                "url": "https://www.yna.co.kr/view/a",
                "snippet": "국제유가 원유",
                "score": 1,
            }),
            normalize_article({
                "title": "석유화학 나프타 공급망 진단",
                "press": "한스경제",
                "url": "https://www.hansbiz.co.kr/news/b",
                "snippet": "석유화학 나프타",
                "score": 1,
            }),
            normalize_article({
                "title": "LNG 수급 전망",
                "press": "지역매체A",
                "url": "https://local-a.test/c",
                "snippet": "LNG 수급",
                "score": 99,
            }),
            normalize_article({
                "title": "유류세 정책 변화",
                "press": "지역매체B",
                "url": "https://local-b.test/d",
                "snippet": "유류세",
                "score": 99,
            }),
        ]

        selected = select_representative_articles(candidates, max_articles=4, min_required=1)

        self.assertEqual([article["press"] for article in selected[:2]], ["연합뉴스", "한스경제"])
        self.assertLessEqual(sum(article["press_grade"] == "C" for article in selected), 1)
        self.assertNotIn("Daum News", {article["press"] for article in selected})

    def test_broad_single_queries_are_not_primary_queries(self) -> None:
        self.assertNotIn("에너지", PLAIN_QUERIES)
        self.assertNotIn("전력", PLAIN_QUERIES)
        self.assertNotIn("물가", PLAIN_QUERIES)

    def test_quality_count_only_accepts_direct_ab_press_candidates(self) -> None:
        candidates = [
            {"press": "연합뉴스", "title": "국제유가 급등", "snippet": ""},
            {"press": "지역매체", "title": "정유 업계 전망", "snippet": ""},
            {"press": "한국경제", "title": "물가 상승", "snippet": ""},
        ]

        self.assertEqual(trusted_direct_count(candidates), 1)
        self.assertTrue(is_forbidden_press("Naver News Search HTML + Google News RSS"))

    def test_representatives_fill_three_distinct_titles_after_topic_spread(self) -> None:
        candidates = [
            normalize_article({
                "title": title,
                "press": press,
                "url": f"https://example.test/{index}",
                "snippet": "국제유가 원유 수급",
            })
            for index, (press, title) in enumerate([
                ("연합뉴스", "호르무즈 봉쇄 뒤 원유 수급 경고"),
                ("한국경제", "중동산 원유 수입 감소, 공급선 다변화"),
                ("매일경제", "국제유가 상승에 정유업계 대응 확대"),
            ])
        ]

        selected = select_representative_articles(candidates, max_articles=3, min_required=1)

        self.assertEqual(len(selected), 3)

    def test_report_summary_is_rebuilt_from_representative_articles(self) -> None:
        articles = [
            {
                "title": "\uc77c\ubcf8, \ud638\ub974\ubb34\uc988 \ubd09\uc1c4 \uc18d \ubbf8 \uc54c\ub798\uc2a4\uce74\uc0b0 \uc6d0\uc720 \ud655\ubcf4",
                "summary": "\uc911\ub3d9 \ud574\ud611 \ub9ac\uc2a4\ud06c\ub85c \ub300\uccb4 \uc6d0\uc720 \uc870\ub2ec\uacfc \uc5d0\ub108\uc9c0 \uc548\ubcf4 \ubcc0\uc218\uac00 \ubd80\uac01",
                "press": "\ub274\uc2a41",
            },
            {
                "title": "\uace0\ud658\uc728\uc774 \uc815\uc720\u00b7\uc11d\uc720\ud654\ud559 \uc6d0\uac00 \ubd80\ub2f4\uc73c\ub85c \ud655\uc0b0",
                "summary": "\ub2ec\ub7ec \uac15\uc138\ub85c \uc6d0\uc720\uc640 \ub098\ud504\ud0c0 \ub3c4\uc785 \ube44\uc6a9\uc774 \uc0c1\uc2b9",
                "press": "\ub9e4\uc77c\uacbd\uc81c",
            },
        ]

        summary = build_news_summary(
            {"summary": "\uc218\uc9d1 \ud6c4\ubcf4 \uc804\uccb4\uc758 \uacf5\ud1b5 \uc694\uc57d"},
            articles,
        )

        self.assertNotIn("\uc218\uc9d1 \ud6c4\ubcf4 \uc804\uccb4", summary)
        self.assertNotRegex(summary, r"^△")
        self.assertNotIn("주요 매체가", summary)
        self.assertNotIn("등을 중심으로 보도", summary)
        self.assertIn("\ub300\uccb4 \uc6d0\uc720 \uc870\ub2ec", summary)
        self.assertIn("\uc6d0\uc720\uc640 \ub098\ud504\ud0c0 \ub3c4\uc785 \ube44\uc6a9", summary)
        self.assertNotIn("'", summary)
        self.assertNotIn("\ub274\uc2a41\uc740", summary)
        self.assertNotIn("\ub9e4\uc77c\uacbd\uc81c\ub294", summary)

    def test_generic_article_summary_falls_back_to_representative_title(self) -> None:
        articles = [
            {
                "title": "\uad6d\uc81c\uc720\uac00 5% \ud558\ub77d\u2026\"\uadf8\ub798\uc11c \uc8fc\uc720\uc18c \uae30\ub984\uac12\uc740 \uc5b8\uc81c \ub0b4\ub824\uac00\ub098\uc694?\"",
                "summary": "\uad6d\uc81c\uc720\uac00\uc640 \uc11d\uc720\uc2dc\uc7a5 \ubcc0\ub3d9 \uc694\uc778\uc744 \uc911\uc2ec\uc73c\ub85c \uc815\ub9ac",
                "press": "\uc774\ub370\uc77c\ub9ac",
            },
            {
                "title": "'\uc720\uac00 \ub2f4\ud569 \ud610\uc758' HD\ud604\ub300\uc624\uc77c\ubc45\ud06c \uc784\uc9c1\uc6d0 \uccab \uc601\uc7a5 \uccad\uad6c",
                "summary": "\uc815\uc720\uc5c5\uacc4 \uc218\uc775\uc131\u00b7\uc6d0\uac00\u00b7\uc2dc\uc7a5 \uc5ec\uac74 \ubcc0\ud654\ub97c \uc911\uc2ec\uc73c\ub85c \ubcf4\ub3c4",
                "press": "\ub274\uc2dc\uc2a4",
            },
        ]

        summary = build_news_summary({}, articles)

        self.assertIn("\uad6d\uc81c\uc720\uac00 5% \ud558\ub77d", summary)
        self.assertIn("HD\ud604\ub300\uc624\uc77c\ubc45\ud06c", summary)
        self.assertNotIn("\ubcc0\ub3d9 \uc694\uc778\uc744 \uc911\uc2ec\uc73c\ub85c \uc815\ub9ac", summary)
        self.assertNotIn("\uc2dc\uc7a5 \uc5ec\uac74 \ubcc0\ud654\ub97c \uc911\uc2ec\uc73c\ub85c \ubcf4\ub3c4", summary)

    def test_empty_article_summary_uses_no_report_fallback(self) -> None:
        summary = build_news_summary({}, [])

        self.assertEqual(summary, "\ud574\ub2f9 \uc2dc\uac04\ub300 \uc8fc\uc694 \ubcf4\ub3c4 \ud655\uc778 \uac74 \uc5c6\uc74c.")

    def test_617_articles_get_content_summaries_not_titles_or_review_notes(self) -> None:
        articles = [
            normalize_article({
                "title": "국제유가 많이 떨어졌는데…주유소 기름값은 언제쯤?",
                "press": "SBS",
                "url": "https://v.daum.net/v/20260617064205528",
                "snippet": "국제유가가 하락했지만 정유사 재고와 수요, 유류세 인하분 등으로 주유소 가격 반영에는 시간이 걸릴 전망이다.",
            }),
            normalize_article({
                "title": "차량 2부제 언제 풀리나… 정부, 호르무즈 상황 따라 결정 전망",
                "press": "국민일보",
                "url": "https://v.daum.net/v/20260617002203535",
                "snippet": "정부가 호르무즈 해협 상황을 보며 차량 2부제 등 비상 수급 조치 완화 여부를 검토한다.",
            }),
            normalize_article({
                "title": "나프타 수급 ‘숨통’ 텄지만…중국 저가공세 ‘숙제’ 남은 석화업계",
                "press": "경향신문",
                "url": "https://v.daum.net/v/20260616203521388",
                "snippet": "호르무즈 해협 봉쇄 우려가 완화되며 나프타 수급 부담은 줄었지만 중국발 공급과잉과 저가 공세는 남아 있다.",
            }),
        ]

        summary = build_news_summary({}, articles)

        self.assertIn("주유소 가격 반영", summary)
        self.assertIn("차량 2부제", summary)
        self.assertIn("나프타 수급", summary)
        self.assertNotIn("△국제유가 많이 떨어졌는데", summary)
        self.assertNotIn("국제유가와 석유시장 변동 요인을 중심으로 정리", summary)
        self.assertNotIn("해당 이슈의 업계 관련성을 원문 기준으로 확인 필요", summary)

    def test_evening_summary_appends_without_replacing_morning(self) -> None:
        report = {
            "summary": [
                {"type": "stakeholder", "text": "\uc804\uc77c \uc8fc\uc694 \uc774\uc288: \uc694\uc57d."},
                {"type": "today", "text": "\uae08\uc77c \uc8fc\uc694 \uc77c\uc815: \uc694\uc57d."},
            ],
            "news_trend": {"summary": "\uc624\uc804 \ub274\uc2a4 \uc694\uc57d."},
        }

        update_summary(report, "\uc624\uc804 \ub274\uc2a4 \uc694\uc57d.", "morning")
        morning_rows = list(report["summary"])
        morning_news = report["news_trend"]
        report["news_trend_afternoon"] = {"summary": "\uc624\ud6c4 \ub274\uc2a4 \uc694\uc57d."}
        update_summary(report, "\uc624\ud6c4 \ub274\uc2a4 \uc694\uc57d.", "evening")

        self.assertEqual(report["summary"][:2], morning_rows)
        self.assertIs(report["summary"][1], morning_rows[1])
        self.assertIs(report["news_trend"], morning_news)
        self.assertEqual(
            report["summary"][2],
            {"type": "news_trend_afternoon", "text": "(Evening) \uc624\ud6c4 \ub274\uc2a4 \uc694\uc57d."},
        )

    def test_summary_removes_previous_issue_row(self) -> None:
        report = {
            "summary": [
                {"type": "stakeholder", "text": "\uc804\uc77c \uc8fc\uc694 \uc774\uc288: \uc694\uc57d."},
                {"type": "today", "text": "\uae08\uc77c \uc8fc\uc694 \uc77c\uc815: \uc694\uc57d."},
            ],
        }

        update_summary(report, "\uc624\uc804 \ub274\uc2a4 \uc694\uc57d.", "morning")

        self.assertEqual(
            report["summary"],
            [
                {"type": "today", "text": "\uae08\uc77c \uc8fc\uc694 \uc77c\uc815: \uc694\uc57d."},
                {"type": "news_trend", "text": "(Morning) \uc624\uc804 \ub274\uc2a4 \uc694\uc57d."},
            ],
        )


if __name__ == "__main__":
    unittest.main()
