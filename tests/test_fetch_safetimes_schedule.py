#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import unittest
import json
import tempfile
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts import fetch_safetimes_schedule as safetimes


class SafeTimesScheduleFetchTest(unittest.TestCase):
    def test_reuses_incomplete_previous_source_without_fetching(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "2026-07-15.json"
            output.write_text(json.dumps({
                "success": True,
                "date": "2026-07-15",
                "article_url": "https://www.safetimes.co.kr/news/articleView.html?idxno=244257",
                "raw_text": "분야별 세부 섹션이 부족하지만 파서가 활용할 수 있는 원문" * 30,
            }, ensure_ascii=False), encoding="utf-8")
            args = SimpleNamespace(
                date="2026-07-15",
                out_dir=directory,
                force_refresh=False,
                reuse_incomplete=True,
                max_retries=3,
                retry_delay=20,
                max_pages=80,
                soft_fail=True,
            )
            with (
                patch.object(safetimes, "parse_args", return_value=args),
                patch.object(safetimes, "collect") as collect_mock,
            ):
                self.assertEqual(safetimes.main(), 0)
            collect_mock.assert_not_called()

    def test_soft_fail_returns_success_and_records_warning_payload(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            args = SimpleNamespace(
                date="2026-07-15",
                out_dir=directory,
                force_refresh=False,
                max_retries=1,
                retry_delay=0,
                max_pages=1,
                soft_fail=True,
                reuse_incomplete=False,
            )
            with (
                patch.object(safetimes, "parse_args", return_value=args),
                patch.object(safetimes, "collect", side_effect=safetimes.SafeTimesError("partial body")),
            ):
                self.assertEqual(safetimes.main(), 0)

            payload = json.loads(
                (Path(directory) / "2026-07-15.error.json").read_text(encoding="utf-8")
            )
            self.assertFalse(payload["success"])
            self.assertEqual(payload["error"], "partial body")

    def test_rejects_partial_article_body(self) -> None:
        self.assertFalse(safetimes.has_complete_schedule_body("photo lead only"))
        complete = "■ 분야별\n[산업]\n산업부 일정\n[국제]\n국제 일정\n" + ("10:00 회의\n" * 50)
        self.assertTrue(safetimes.has_complete_schedule_body(complete))

    def test_accepts_complete_article_without_decorative_section_heading(self) -> None:
        complete = "[정치]\n정부 일정\n[산업]\n산업부 일정\n" + ("10:00 회의\n" * 50)
        self.assertNotIn("■ 분야별", complete)
        self.assertTrue(safetimes.has_complete_schedule_body(complete))

    def test_rejects_long_article_with_only_one_schedule_section(self) -> None:
        incomplete = "[정치]\n" + ("10:00 회의\n" * 50)
        self.assertFalse(safetimes.has_complete_schedule_body(incomplete))

    def test_article_parser_prefers_source_heading_over_recovery_placeholder(self) -> None:
        source_title = "[오늘의 주요일정·14일] 실제 기사 제목"
        html = f"""
        <html><head><meta property="og:title" content="{source_title}"></head>
        <body><h3 class="heading">{source_title}</h3>
        <div id="article-view-content-div">본문</div><span>승인 2026.07.14 07:00</span></body></html>
        """
        with patch.object(safetimes, "fetch", return_value=html):
            article = safetimes.parse_article_candidate({
                "title": "주요일정 후보 244180",
                "url": "https://example.test/news/articleView.html?idxno=244180",
            })

        self.assertEqual(article["title"], source_title)
        self.assertEqual(article["article_title"], source_title)

    def test_schedule_title_accepts_current_and_legacy_names(self) -> None:
        self.assertTrue(safetimes.is_schedule_article_title("[주요일정·29일] 이 대통령, 일정"))
        self.assertTrue(safetimes.is_schedule_article_title("[오늘의 주요일정·29일] 주요 일정"))
        self.assertTrue(safetimes.is_schedule_article_title("[주요 일정·29일] 공백 포함 제목"))
        self.assertFalse(safetimes.is_schedule_article_title("[인사] 산업부"))

    def test_title_matches_target_day_variants(self) -> None:
        target = datetime(2026, 6, 26)

        self.assertTrue(safetimes.title_matches_target_day("[주요일정·26일] 보건의료산업 AX 간담회", target))
        self.assertTrue(safetimes.title_matches_target_day("[주요일정ㆍ26일] 보건의료산업 AX 간담회", target))
        self.assertTrue(safetimes.title_matches_target_day("[주요일정・26일] 보건의료산업 AX 간담회", target))
        self.assertTrue(safetimes.title_matches_target_day("[주요일정] 6월 26일 보건의료산업 AX 간담회", target))
        self.assertFalse(safetimes.title_matches_target_day("[주요일정·29일] 이 대통령 일정", target))

    def test_select_article_for_date_uses_plain_major_schedule_title(self) -> None:
        candidates = [
            {"title": "[주요일정·29일] 이 대통령, 일정", "url": "https://example.test/29"},
            {"title": "[주요일정·26일] 보건의료산업 AX 간담회", "url": "https://example.test/26"},
        ]

        def fake_parse(candidate: dict[str, str]) -> dict[str, str]:
            return {
                "title": candidate["title"],
                "article_title": candidate["title"],
                "article_url": candidate["url"],
                "approved_date": "2026-06-26" if candidate["url"].endswith("/26") else "2026-06-29",
                "raw_text": "본문",
                "full_text": "승인 2026.06.26 07:00" if candidate["url"].endswith("/26") else "승인 2026.06.29 07:00",
            }

        with patch.object(safetimes, "parse_article_candidate", side_effect=fake_parse):
            article = safetimes.select_article_for_date(candidates, "2026-06-26")

        self.assertEqual(article["article_url"], "https://example.test/26")

    def test_collect_search_candidates_continues_after_sparse_empty_pages(self) -> None:
        pages: dict[tuple[str, int], str] = {
            ("주요일정", 1): '<a href="/news/articleView.html?idxno=1">[주요일정·29일] 최신 일정</a>',
            ("주요일정", 7): '<a href="/news/articleView.html?idxno=2">[주요일정·26일] 목표 일정</a>',
        }

        def fake_fetch(_url: str, params: dict[str, object] | None = None) -> str:
            params = params or {}
            page = int(params.get("page", 1))
            word = str(params.get("sc_word", ""))
            return pages.get((word, page), "<html></html>")

        with (
            patch.object(safetimes, "fetch", side_effect=fake_fetch),
            patch.object(safetimes.time, "sleep", return_value=None),
        ):
            candidates = safetimes.collect_search_candidates(max_pages=8)

        titles = [item["title"] for item in candidates]
        self.assertIn("[주요일정·29일] 최신 일정", titles)
        self.assertIn("[주요일정·26일] 목표 일정", titles)

    def test_collect_search_candidates_keeps_general_article_anchor_and_stops_repeated_page(self) -> None:
        page_html = '<a href="/news/articleView.html?idxno=244257">일반 최신 기사</a>'
        calls: list[int] = []

        def fake_fetch(_url: str, params: dict[str, object] | None = None) -> str:
            calls.append(int((params or {}).get("page", 1)))
            return page_html

        with (
            patch.object(safetimes, "SCHEDULE_SEARCH_TERMS", ("주요일정",)),
            patch.object(safetimes, "fetch", side_effect=fake_fetch),
            patch.object(safetimes.time, "sleep", return_value=None),
        ):
            candidates = safetimes.collect_search_candidates(max_pages=80)

        self.assertEqual([item["title"] for item in candidates], ["일반 최신 기사"])
        self.assertEqual(calls, [1, 2])

    def test_collect_falls_back_to_nearby_article_ids(self) -> None:
        candidates = [
            {"title": "[주요일정·3일] 최신 일정", "url": "https://example.test/news/articleView.html?idxno=100"},
        ]

        def fake_parse(candidate: dict[str, str]) -> dict[str, str]:
            idx = safetimes.article_idx_from_url(candidate["url"])
            if idx == 98:
                return {
                    "title": "[주요일정·1일] 목표 일정",
                    "article_title": "[주요일정·1일] 목표 일정",
                    "article_url": candidate["url"],
                    "approved_date": "2026-07-01",
                    "raw_text": "■ 분야별\n[산업]\n[국제]\n" + ("10:00 회의\n" * 50),
                    "full_text": "승인 2026.07.01 07:00",
                }
            return {
                "title": "[일반기사] 다른 기사",
                "article_title": "[일반기사] 다른 기사",
                "article_url": candidate["url"],
                "approved_date": "2026-07-03",
                "raw_text": "본문",
                "full_text": "승인 2026.07.03 07:00",
            }

        with (
            patch.object(safetimes, "KNOWN_IDX_BY_DATE", {}),
            patch.object(safetimes, "NEARBY_ARTICLE_SCAN_LIMIT", 5),
            patch.object(safetimes, "collect_search_candidates", return_value=candidates),
            patch.object(safetimes, "parse_article_candidate", side_effect=fake_parse),
            patch.object(safetimes.time, "sleep", return_value=None),
        ):
            payload = safetimes.collect("2026-07-01", max_pages=8)

        self.assertEqual(payload["article_url"], "https://www.safetimes.co.kr/news/articleView.html?idxno=98")
        self.assertEqual(payload["category"], "주요일정")

    def test_nearby_article_ids_scans_newer_articles_before_older_ones(self) -> None:
        self.assertEqual(
            safetimes.nearby_article_ids(100, 3),
            [100, 101, 99, 102, 98, 103, 97],
        )

    def test_collect_finds_newer_article_when_search_index_lags(self) -> None:
        candidates = [
            {"title": "[주요일정·10일] 이전 일정", "url": "https://example.test/news/articleView.html?idxno=100"},
        ]

        def fake_parse(candidate: dict[str, str]) -> dict[str, str]:
            idx = safetimes.article_idx_from_url(candidate["url"])
            if idx == 102:
                return {
                    "title": "[오늘의 주요일정·13일] 목표 일정",
                    "article_title": "[오늘의 주요일정·13일] 목표 일정",
                    "article_url": candidate["url"],
                    "approved_date": "2026-07-13",
                    "raw_text": "■ 분야별\n[산업]\n[국제]\n" + ("10:00 회의\n" * 50),
                    "full_text": "승인 2026.07.13 07:00",
                }
            return {
                "title": "[일반기사] 다른 기사",
                "article_title": "[일반기사] 다른 기사",
                "article_url": candidate["url"],
                "approved_date": "2026-07-10",
                "raw_text": "본문",
                "full_text": "승인 2026.07.10 07:00",
            }

        with (
            patch.object(safetimes, "KNOWN_IDX_BY_DATE", {}),
            patch.object(safetimes, "NEARBY_ARTICLE_SCAN_LIMIT", 3),
            patch.object(safetimes, "collect_search_candidates", return_value=candidates),
            patch.object(safetimes, "parse_article_candidate", side_effect=fake_parse),
            patch.object(safetimes.time, "sleep", return_value=None),
        ):
            payload = safetimes.collect("2026-07-13", max_pages=8)

        self.assertEqual(payload["article_url"], "https://www.safetimes.co.kr/news/articleView.html?idxno=102")


if __name__ == "__main__":
    unittest.main()
