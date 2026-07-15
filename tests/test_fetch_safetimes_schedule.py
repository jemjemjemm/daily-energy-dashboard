#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import unittest
from datetime import datetime
from unittest.mock import patch

from scripts import fetch_safetimes_schedule as safetimes


class SafeTimesScheduleFetchTest(unittest.TestCase):
    def test_rejects_partial_article_body(self) -> None:
        self.assertFalse(safetimes.has_complete_schedule_body("photo lead only"))
        self.assertTrue(safetimes.has_complete_schedule_body("■ 분야별\n[정치]\n대통령 일정"))

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
                    "raw_text": "\n".join(safetimes.SCHEDULE_SECTION_MARKERS),
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
                    "raw_text": "\n".join(safetimes.SCHEDULE_SECTION_MARKERS),
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
