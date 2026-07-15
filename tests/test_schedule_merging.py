#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import unittest
from pathlib import Path

from datetime import datetime

from scripts.build_report_draft_from_schedule import (
    refresh_report_schedule_sections,
    schedule_items_from_json_or_body,
)
from scripts.generate_schedule_detail_html import parse_schedule, split_actor_event


class ScheduleMergingTest(unittest.TestCase):
    def test_2026_06_04_merges_repeated_events_and_prefers_named_attendees(self) -> None:
        schedule_data = json.loads(Path("data/schedules/2026-06-04.json").read_text(encoding="utf-8"))

        rows = schedule_items_from_json_or_body(schedule_data, max_items=20)
        by_title = {row["title"]: row for row in rows}

        emergency = by_title["비상경제본부회의"]
        self.assertEqual(emergency["time"], "09:00")
        self.assertIn("김민석 국무총리", emergency["attendees"])
        self.assertIn("구윤철 부총리 겸 재정경제부 장관", emergency["attendees"])
        self.assertIn("박윤주 외교부 1차관", emergency["attendees"])
        self.assertIn("오유경 식약처장", emergency["attendees"])
        self.assertEqual(emergency["attendees"].count("김영훈 노동부 장관"), 1)

        price_tf = by_title["민생물가 특별관리 관계장관 TF 회의"]
        self.assertEqual(price_tf["time"], "14:00")
        self.assertIn("남동일 공정위 부위원장", price_tf["attendees"])
        self.assertIn("김용재 식약차장", price_tf["attendees"])
        self.assertIn("이병권 중기부 2차관", price_tf["attendees"])

        defense = by_title["제12회 방위산업발전협의회"]
        self.assertEqual(defense["attendees"], "안규백 국방부 장관, 김정관 산업통상부 장관")

        drone = by_title["정부 드론·대드론 통합 TF 최종보고 회의"]
        self.assertEqual(drone["attendees"], "이두희 국방부 차관, 류제명 과기정통부 2차관")

        seminar = by_title["한미 관계 전망 세미나"]
        self.assertEqual(seminar["time"], "10:00 현지시간")
        self.assertEqual(seminar["attendees"], "KEI")

    def test_2026_06_23_items_only_schedule_is_parsed(self) -> None:
        schedule_data = json.loads(Path("data/schedules/2026-06-23.json").read_text(encoding="utf-8"))

        rows = schedule_items_from_json_or_body(schedule_data, max_items=12)
        titles = {row["title"] for row in rows}

        self.assertGreaterEqual(len(rows), 8)
        self.assertIn("한미전략투자사업관리위원회", titles)
        self.assertIn("국무회의 겸 비상경제점검회의", titles)
        self.assertIn("중국 국제 공급망 박람회", titles)
        self.assertNotIn("베이징)", titles)
        self.assertNotIn("금일 주요 일정 수집 지연", titles)

    def test_schedule_repair_replaces_placeholder_without_dropping_news(self) -> None:
        schedule_data = json.loads(Path("data/schedules/2026-06-23.json").read_text(encoding="utf-8"))
        report = {
            "report": {"report_date": "2026-06-23"},
            "summary": [
                {"type": "price_only", "text": "일정 원문 수집이 지연되어 가격 및 뉴스 중심 리포트로 우선 발간."},
                {"type": "news_trend", "text": "(Morning) 뉴스 요약"},
            ],
            "schedules": [
                {
                    "time": "-",
                    "org": "데이터",
                    "title": "금일 주요 일정 수집 지연",
                    "relevance": "외부 일정 원문 수집이 복구되면 재실행 시 자동 반영.",
                }
            ],
            "news_trend": {
                "summary": "뉴스 요약",
                "articles": [{"title": "기사", "url": "https://example.test"}],
            },
        }

        refreshed = refresh_report_schedule_sections(
            report=report,
            schedule_data=schedule_data,
            target_dt=datetime(2026, 6, 23),
            max_items=12,
        )

        self.assertGreaterEqual(len(refreshed["schedules"]), 8)
        self.assertNotEqual(refreshed["schedules"][0]["title"], "금일 주요 일정 수집 지연")
        self.assertEqual(refreshed["news_trend"]["summary"], "뉴스 요약")
        self.assertTrue(any(item["type"] == "news_trend" for item in refreshed["summary"]))
        self.assertFalse(any("일정 원문 수집" in item.get("text", "") for item in refreshed["summary"]))

    def test_schedule_detail_actor_split_ignores_parenthesized_comma(self) -> None:
        actor, event = split_actor_event("중국 국제 공급망 박람회(∼26일, 베이징)")

        self.assertEqual(actor, "")
        self.assertEqual(event, "중국 국제 공급망 박람회(∼26일, 베이징)")

    def test_july_10_keeps_business_items_and_excludes_generic_ministry_events(self) -> None:
        schedule_data = json.loads(Path("data/schedules/2026-07-10.json").read_text(encoding="utf-8"))
        rows = schedule_items_from_json_or_body(schedule_data, max_items=12)
        titles = {row["title"] for row in rows}

        self.assertIn("월간 석유리포트", titles)
        self.assertIn("배전망 ESS 구축지원사업 협약식", titles)
        self.assertIn("홈플러스 관련 관계기관 전담반(TF) 회의", titles)
        self.assertNotIn("청년정책 전문가 간담회", titles)
        self.assertNotIn("국외 출장", titles)

    def test_july_15_full_source_keeps_real_events_and_detail_groups(self) -> None:
        schedule_data = json.loads(Path("data/schedules/2026-07-15.json").read_text(encoding="utf-8"))

        rows = schedule_items_from_json_or_body(schedule_data, max_items=12)
        titles = {row["title"] for row in rows}
        self.assertIn("AI 토론회", titles)
        self.assertIn("UAM·드론박람회", titles)
        self.assertIn("국외출장", titles)
        self.assertNotIn("산업부", titles)
        self.assertFalse(any(row["title"].endswith("통상교섭본부장") for row in rows))

        core, parties, ministers, _fields = parse_schedule(schedule_data)
        self.assertEqual(len(core["대통령"]), 1)
        self.assertEqual(len(core["국무총리"]), 1)
        self.assertGreaterEqual(len(parties["더불어민주당"]), 2)
        self.assertGreaterEqual(len(parties["국민의힘"]), 3)
        self.assertGreaterEqual(len(parties["개혁신당"]), 3)
        self.assertGreaterEqual(sum(len(events) for people in ministers.values() for events in people.values()), 30)


if __name__ == "__main__":
    unittest.main()
