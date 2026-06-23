#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.validate_report_html import validate_html_file


def report_html(date_text: str, morning_title: str, evening_title: str) -> str:
    sections = []
    for num in range(1, 5):
        sections.append(
            f'<section><div class="section-header"><span class="section-num">{num}</span>'
            f'<span class="section-title">Section {num}</span></div><div>ok</div></section>'
        )
    sections.append(
        '<section><div class="section-header"><span class="section-num">5</span>'
        '<span class="section-title">Schedules</span></div>'
        '<div class="schedule-list"><div class="schedule-row">ok</div></div></section>'
    )
    sections.append(
        '<section><div class="section-header"><span class="section-num">6</span>'
        f'<span class="section-title">{morning_title}</span></div>'
        '<div class="news-body">ok</div></section>'
    )
    sections.append(
        '<section><div class="section-header"><span class="section-num">7</span>'
        f'<span class="section-title">{evening_title}</span></div>'
        '<div class="news-body">ok</div></section>'
    )
    return f"<!doctype html><html><body><h1>{date_text}</h1>{''.join(sections)}</body></html>"


def report_html_with_news(date_text: str, morning_news_body: str, evening_news_body: str = "") -> str:
    morning_title = "News Trend - Morning (6/16 17:00 - 6/17 08:00)"
    evening_title = "News Trend - Evening (6/17 08:00 - 17:00)"
    sections = []
    for num in range(1, 5):
        sections.append(
            f'<section><div class="section-header"><span class="section-num">{num}</span>'
            f'<span class="section-title">Section {num}</span></div><div>ok</div></section>'
        )
    sections.append(
        '<section><div class="section-header"><span class="section-num">5</span>'
        '<span class="section-title">Schedules</span></div>'
        '<div class="schedule-list"><div class="schedule-row">ok</div></div></section>'
    )
    sections.append(
        '<section><div class="section-header"><span class="section-num">6</span>'
        f'<span class="section-title">{morning_title}</span></div>{morning_news_body}</section>'
    )
    sections.append(
        '<section><div class="section-header"><span class="section-num">7</span>'
        f'<span class="section-title">{evening_title}</span></div>'
        f'{evening_news_body or "<div class=\"news-body\"><div class=\"news-trend\">17:30 업데이트 예정입니다.</div></div>"}</section>'
    )
    return f"<!doctype html><html><body><h1>{date_text}</h1>{''.join(sections)}</body></html>"


class ValidateReportHtmlTest(unittest.TestCase):
    def validate_text(self, date_text: str, morning_title: str, evening_title: str) -> list[str]:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / f"{date_text}.html"
            path.write_text(report_html(date_text, morning_title, evening_title), encoding="utf-8")
            return validate_html_file(path, "2026-05-01", False)

    def test_legacy_may_reports_allow_09_news_window(self) -> None:
        errors = self.validate_text(
            "2026-05-29",
            "News Trend - Morning (5/28 17:00 - 5/29 09:00)",
            "News Trend - Evening (5/29 09:00 - 17:00)",
        )

        self.assertEqual(errors, [])

    def test_june_reports_require_08_news_window(self) -> None:
        errors = self.validate_text(
            "2026-06-11",
            "News Trend - Morning (6/10 17:00 - 6/11 09:00)",
            "News Trend - Evening (6/11 09:00 - 17:00)",
        )

        self.assertTrue(any("expected news section titles" in error for error in errors))

    def test_june_reports_accept_08_news_window(self) -> None:
        errors = self.validate_text(
            "2026-06-11",
            "News Trend - Morning (6/10 17:00 - 6/11 08:00)",
            "News Trend - Evening (6/11 08:00 - 17:00)",
        )

        self.assertEqual(errors, [])

    def test_news_quality_requires_bulleted_content_summary_after_cutoff(self) -> None:
        body = (
            '<div class="news-body"><div class="news-trend">국제유가 하락에도 주유소 가격 반영 시차가 남아 있음</div>'
            '<a class="news-link"><div class="news-link-title">국제유가 많이 떨어졌는데…주유소 기름값은 언제쯤?</div>'
            '<div class="news-link-desc">국제유가 하락에도 국내 가격 반영 시차가 남아 있음</div></a></div>'
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "2026-06-17.html"
            path.write_text(report_html_with_news("2026-06-17", body), encoding="utf-8")
            errors = validate_html_file(path, "2026-05-01", False)

        self.assertTrue(any("missing per-item △ markers" in error for error in errors))

    def test_news_quality_rejects_title_list_after_cutoff(self) -> None:
        title = "국제유가 많이 떨어졌는데…주유소 기름값은 언제쯤?"
        body = (
            f'<div class="news-body"><div class="news-trend">△{title}</div>'
            f'<a class="news-link"><div class="news-link-title">{title}</div>'
            '<div class="news-link-desc">국제유가 하락에도 국내 가격 반영 시차가 남아 있음</div></a></div>'
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "2026-06-17.html"
            path.write_text(report_html_with_news("2026-06-17", body), encoding="utf-8")
            errors = validate_html_file(path, "2026-05-01", False)

        self.assertTrue(any("lists article title instead of content" in error for error in errors))

    def test_news_quality_rejects_generic_review_descriptions_after_cutoff(self) -> None:
        body = (
            '<div class="news-body"><div class="news-trend">△국제유가 하락에도 주유소 가격 반영 시차가 남아 있음</div>'
            '<a class="news-link"><div class="news-link-title">국제유가 많이 떨어졌는데…주유소 기름값은 언제쯤?</div>'
            '<div class="news-link-desc">해당 이슈의 업계 관련성을 원문 기준으로 확인 필요</div></a></div>'
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "2026-06-17.html"
            path.write_text(report_html_with_news("2026-06-17", body), encoding="utf-8")
            errors = validate_html_file(path, "2026-05-01", False)

        self.assertTrue(any("generic/review phrase" in error for error in errors))

    def test_news_quality_rejects_summary_that_does_not_match_article_title(self) -> None:
        body = (
            '<div class="news-body"><div class="news-trend">'
            '△국제유가와 원유 수급 변화가 국내 정유·석유제품 가격 반영 시차로 연결</div>'
            '<a class="news-link"><div class="news-link-title">'
            '석유 최고가격제 손실 보전도 정부 뜻대로? 정산위 회의 비공개 방침에 불안한 정유사들'
            '</div><div class="news-link-desc">'
            '국제유가와 원유 수급 변화가 국내 정유·석유제품 가격 반영 시차로 연결'
            '</div></a></div>'
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "2026-06-17.html"
            path.write_text(report_html_with_news("2026-06-17", body), encoding="utf-8")
            errors = validate_html_file(path, "2026-05-01", False)

        self.assertTrue(any("does not match article title" in error for error in errors))

    def test_news_quality_accepts_bulleted_content_summary_after_cutoff(self) -> None:
        body = (
            '<div class="news-body"><div class="news-trend">△국제유가 하락에도 국내 주유소 가격 반영에는 시차가 남아 있음 '
            '△나프타 수급 변화가 석유화학 원료 조달 변수로 부각</div>'
            '<a class="news-link"><div class="news-link-title">국제유가 많이 떨어졌는데…주유소 기름값은 언제쯤?</div>'
            '<div class="news-link-desc">국제유가 하락에도 국내 가격 반영 시차가 남아 있음</div></a></div>'
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "2026-06-17.html"
            path.write_text(report_html_with_news("2026-06-17", body), encoding="utf-8")
            errors = validate_html_file(path, "2026-05-01", False)

        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
