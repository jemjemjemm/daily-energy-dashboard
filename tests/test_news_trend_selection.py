#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import unittest

from bs4 import BeautifulSoup

from scripts.apply_news_to_report import (
    build_news_summary,
    fallback_article_summary,
    normalize_article,
    select_representative_articles,
    specific_article_summary,
    update_summary,
    to_summary_clause,
)
from scripts.fetch_news_candidates import PLAIN_QUERIES, daum_card_press, trusted_direct_count
from scripts.generate_html_report import article_desc_for_display, fallback_article_desc
from scripts.news_article_rules import (
    has_dairy_raw_milk_context,
    has_strong_energy_context,
    industry_relevance_score,
    is_forbidden_press,
    is_non_energy_raw_milk_article,
    normalize_article_url,
    resolve_press,
)


class NewsTrendSelectionTest(unittest.TestCase):
    def test_declarative_news_summaries_become_nominalized_clauses(self) -> None:
        samples = {
            "홍해와 흑해가 전쟁 여파로 위태로운 상황에 처하면서다": "홍해와 흑해가 전쟁 여파로 위태로운 상황에 처함",
            "국내 정유사들이 수입선을 다변화해 수급불안은 피한 모습이다": "국내 정유사들이 수입선을 다변화해 수급불안은 피한 모습임",
            "바브엘만데브 통과 원유량은 호르무즈 해협의 1.8배다": "바브엘만데브 통과 원유량은 호르무즈 해협의 1.8배임",
        }

        for sentence, expected in samples.items():
            with self.subTest(sentence=sentence):
                clause = to_summary_clause(sentence)
                self.assertEqual(clause, expected)
                self.assertFalse(clause.endswith(("다", "요", ".")))

    RAW_MILK_TITLE = "[Why&Next]자유화되는 비싼 흰우유...'원유 쿼터' 치열한 입방아"

    def test_non_energy_raw_milk_article_is_excluded_and_not_broad_summarized(self) -> None:
        item = {
            "title": self.RAW_MILK_TITLE,
            "press": "한국경제",
            "url": "https://example.test/raw-milk",
            "snippet": "낙농진흥회와 유업계가 원유 쿼터와 raw milk 가격 연동제를 두고 논의했다.",
        }

        self.assertTrue(has_dairy_raw_milk_context(item))
        self.assertFalse(has_strong_energy_context(item))
        self.assertTrue(is_non_energy_raw_milk_article(item))
        self.assertLess(industry_relevance_score(item["title"], item["snippet"]), 0)

        broad = "국제유가와 원유 수급 변화"
        self.assertNotIn(broad, fallback_article_summary(item["title"], item["snippet"]))
        self.assertNotIn(broad, specific_article_summary(item["title"], item["snippet"]))
        self.assertNotIn(broad, fallback_article_desc(item["title"]))
        self.assertNotIn(broad, article_desc_for_display({**item, "summary": broad + "가 국내 정유·석유제품 가격 반영 시차로 연결"}))

        selected = select_representative_articles(
            [
                normalize_article(item),
                normalize_article({
                    "title": "국제유가 상승에 정유업계 대응 확대",
                    "press": "연합뉴스",
                    "url": "https://example.test/oil",
                    "snippet": "국제유가와 원유 수급 변동에 정유업계가 대응을 확대했다.",
                }),
            ],
            max_articles=3,
            min_required=1,
        )

        self.assertNotIn(self.RAW_MILK_TITLE, [article["title"] for article in selected])

    def test_energy_raw_milk_lookalike_with_strong_context_is_kept(self) -> None:
        item = {
            "title": "정유업계, 원유 도입선 다변화 추진",
            "snippet": "호르무즈 리스크와 국제유가 변동에 대응해 원유 수입선을 조정한다.",
        }

        self.assertTrue(has_strong_energy_context(item))
        self.assertFalse(is_non_energy_raw_milk_article(item))
        self.assertGreater(industry_relevance_score(item["title"], item["snippet"]), 0)

    def test_representative_summary_keeps_selected_article_order_and_count(self) -> None:
        articles = [
            {"title": "국제유가 상승에 정유업계 대응 확대", "summary": "국제유가 상승으로 정유업계가 원가와 수익성 대응을 확대", "press": "연합뉴스"},
            {"title": "브렌트유 80달러 밑으로 하락", "summary": "브렌트유가 배럴당 80달러 밑으로 내려가며 유가에 반영", "press": "한국경제"},
            {"title": "LNG 수급 전망과 발전 원가 변수", "summary": "LNG 수급 전망이 발전 원가 변수로 부각", "press": "매일경제"},
        ]

        summary = build_news_summary({}, articles)
        parts = [part.strip() for part in summary.split("△") if part.strip()]

        self.assertEqual(len(parts), 3)
        self.assertIn("국제유가", parts[0])
        self.assertIn("브렌트유", parts[1])
        self.assertIn("LNG", parts[2])

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

    def test_dairy_raw_milk_article_is_not_treated_as_crude_oil(self) -> None:
        dairy_title = "[Why&Next]남아도는 비싼 흰우유...' 원유 쿼터' 치열한 샅바싸움"
        energy_title = "국제유가 급등과 원유 수급 경고"

        self.assertLess(industry_relevance_score(dairy_title), 0)
        self.assertGreater(industry_relevance_score(energy_title), 0)

        selected = select_representative_articles(
            [
                normalize_article({
                    "title": dairy_title,
                    "press": "한국경제",
                    "url": "https://example.test/dairy",
                    "snippet": "흰우유 원유 쿼터를 둘러싼 낙농 업계 갈등",
                }),
                normalize_article({
                    "title": energy_title,
                    "press": "연합뉴스",
                    "url": "https://example.test/energy",
                    "snippet": "국제유가 원유 수급",
                }),
            ],
            max_articles=3,
            min_required=1,
        )

        self.assertEqual([article["title"] for article in selected], [energy_title])

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
        self.assertRegex(summary, r"^△")
        self.assertNotIn("주요 매체가", summary)
        self.assertNotIn("등을 중심으로 보도", summary)
        self.assertIn("\u25b3", summary)
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

    def test_refinery_keyword_does_not_collapse_distinct_articles(self) -> None:
        articles = [
            {
                "title": "중동 생산 차질에 윤활기유 몸값 상승… 정유사 실적 버팀목 될까",
                "summary": "정유업계 공급망 재편과 수익성 부담이 중동 리스크와 맞물린 흐름 조명",
                "press": "파이낸셜뉴스",
            },
            {
                "title": "러, 우크라 주유소 연일 맹폭… 정유 시설 피격에 맞보복",
                "summary": "정유업계 공급망 재편과 수익성 부담이 중동 리스크와 맞물린 흐름 조명",
                "press": "뉴스1",
            },
            {
                "title": "우크라 드론 정유시설 공격에 연료난…러, 인도서 휘발유 수입",
                "summary": "정유업계 공급망 재편과 수익성 부담이 중동 리스크와 맞물린 흐름 조명",
                "press": "연합뉴스",
            },
        ]

        summary = build_news_summary({}, articles)

        self.assertIn("윤활기유 가격", summary)
        self.assertIn("우크라이나 주유소 공격", summary)
        self.assertIn("인도산 휘발유 수입", summary)
        self.assertNotIn("정유업계 공급망 재편", summary)

    def test_mismatched_article_summary_falls_back_to_title_specific_summary(self) -> None:
        articles = [
            {
                "title": "석유 최고가격제 손실 보전도 정부 뜻대로? 정산위 회의 비공개 방침에 불안한 정유사들",
                "summary": "국제유가와 원유 수급 변화가 국내 정유·석유제품 가격 반영 시차로 연결",
                "press": "조선일보",
            },
        ]

        summary = build_news_summary({}, articles)

        self.assertIn("최고가격제 손실보전", summary)
        self.assertIn("정산위", summary)
        self.assertNotIn("가격 반영 시차", summary)

    def test_price_cap_cut_article_uses_title_specific_summary(self) -> None:
        articles = [
            {
                "title": "150원 내렸지만…석유 최고가격제 출구는 '안갯속'",
                "summary": "국제유가와 원유 수급 변화가 국내 정유·석유제품 가격 반영 시차로 연결",
                "press": "아시아경제",
            },
        ]

        summary = build_news_summary({}, articles)

        self.assertIn("석유 최고가격제", summary)
        self.assertIn("시장 불확실성", summary)
        self.assertNotIn("가격 반영 시차", summary)

    def test_ulsan_port_crude_volume_article_uses_title_specific_summary(self) -> None:
        articles = [
            {
                "title": "울산항 5월 물동량 전년 대비 22% 감소... 원유 수입 감소 등 영향",
                "summary": "국제유가와 원유 수급 변화가 국내 정유·석유제품 가격 반영 시차로 연결",
                "press": "파이낸셜뉴스",
            },
        ]

        summary = build_news_summary({}, articles)

        self.assertIn("울산항 물동량 감소", summary)
        self.assertIn("원유 수입 둔화", summary)
        self.assertNotIn("가격 반영 시차", summary)

    def test_lng_terminal_article_does_not_use_mismatched_broad_summary(self) -> None:
        title = "울산 북항 LNG터미널 3단계 준공…21.5만㎘ 저장용량 추가"
        broad = "LNG 수급·가격 변동이 에너지 시장에 미치는 영향 보도"
        articles = [{"title": title, "summary": broad, "press": "연합뉴스"}]

        summary = build_news_summary({}, articles)
        desc = article_desc_for_display(articles[0])

        self.assertIn("LNG터미널", summary)
        self.assertNotIn(broad, summary)
        self.assertNotEqual(desc, broad)

    def test_supply_price_article_does_not_get_collusion_summary_from_snippet(self) -> None:
        article = normalize_article({
            "title": "정유사 공급가격 체계 손질…사전고지 확대에 경유 할인 경쟁도",
            "press": "파이낸셜뉴스",
            "url": "https://v.daum.net/v/20260623142346694",
            "snippet": (
                "사후정산제 폐지를 공식화하면서 GS칼텍스와 HD현대오일뱅크 등 "
                "경쟁사들도 관련 제도 정비에 착수했다."
            ),
        })

        self.assertIn("공급가격 사전고지", article["summary"])
        self.assertNotIn("담합", article["summary"])

    def test_saved_collusion_summary_without_collusion_title_is_rebuilt(self) -> None:
        articles = [
            {
                "title": "정유사 공급가격 체계 손질…사전고지 확대에 경유 할인 경쟁도",
                "summary": "HD현대오일뱅크 유가 담합 혐의 수사가 정유업계 규제 리스크로 부상",
                "press": "파이낸셜뉴스",
            },
        ]

        summary = build_news_summary({}, articles)

        self.assertIn("공급가격 사전고지", summary)
        self.assertNotIn("담합", summary)

    def test_oil_price_transparency_title_replaces_broad_refinery_summary(self) -> None:
        articles = [
            {
                "title": "빨리 오르고 늦게 내리는 기름값?…투명성 강화에 나선 정유사들",
                "summary": "국제유가와 원유 수급 변화가 국내 정유·석유제품 가격 반영 시차로 연결",
                "press": "연합뉴스",
            },
        ]

        summary = build_news_summary({}, articles)

        self.assertIn("기름값 변동 반영 지연", summary)
        self.assertIn("투명성 강화", summary)
        self.assertNotIn("국제유가와 원유 수급 변화", summary)

    def test_empty_article_summary_uses_no_report_fallback(self) -> None:
        summary = build_news_summary({}, [])

        self.assertEqual(summary, "\ud574\ub2f9 \uc2dc\uac04\ub300 \uc8fc\uc694 \ubcf4\ub3c4 \ud655\uc778 \uac74 \uc5c6\uc74c.")

    def test_unknown_repeated_title_uses_publishable_content_summary(self) -> None:
        title = "새로운 에너지 업계 현안을 다룬 기사 제목"
        article = normalize_article({
            "title": title,
            "press": "연합뉴스",
            "url": "https://example.test/energy",
            "snippet": title,
        })

        summary = build_news_summary({}, [article])

        self.assertNotIn(title, summary)
        self.assertIn("정책·시장 동향", summary)

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
        self.assertRegex(summary, r"^△")
        self.assertNotIn("△국제유가 많이 떨어졌는데", summary)
        self.assertNotIn("국제유가와 석유시장 변동 요인을 중심으로 정리", summary)
        self.assertNotIn("해당 이슈의 업계 관련성을 원문 기준으로 확인 필요", summary)

    def test_evening_summary_appends_without_replacing_morning(self) -> None:
        report = {
            "summary": [
                {"type": "stakeholder", "text": "\uc804\uc77c \uc8fc\uc694 \uc774\uc288: \uc694\uc57d."},
                {"type": "today", "text": "\uae08\uc77c \uc8fc\uc694 \uc77c\uc815: \uc694\uc57d"},
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
                {"type": "today", "text": "\uae08\uc77c \uc8fc\uc694 \uc77c\uc815: \uc694\uc57d"},
                {"type": "news_trend", "text": "(Morning) \uc624\uc804 \ub274\uc2a4 \uc694\uc57d."},
            ],
        )


if __name__ == "__main__":
    unittest.main()
