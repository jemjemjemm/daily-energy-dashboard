#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Single source of truth for Korean public holidays used by the Daily pipeline.

Every script and workflow step must import this module instead of keeping its
own copy. Separate copies drifted on 2026-09-28 (some listed 09-28 as a
holiday, others 09-26), which made the previous-business-day calculation
disagree between the workflow and validate_report_sources.py.
"""
from __future__ import annotations

from datetime import date, timedelta

KOREAN_HOLIDAYS_2026 = frozenset({
    "2026-01-01",
    "2026-02-16", "2026-02-17", "2026-02-18",
    "2026-03-02",
    "2026-05-01", "2026-05-05", "2026-05-25",
    "2026-06-03",
    "2026-08-17",
    "2026-09-24", "2026-09-25", "2026-09-26",
    "2026-10-05", "2026-10-09",
    "2026-12-25",
})

KOREAN_HOLIDAYS = KOREAN_HOLIDAYS_2026


def is_business_day(value: date) -> bool:
    return value.weekday() < 5 and value.isoformat() not in KOREAN_HOLIDAYS


def previous_business_day(value: date, max_days: int = 14) -> date:
    cur = value - timedelta(days=1)
    for _ in range(max_days):
        if is_business_day(cur):
            return cur
        cur -= timedelta(days=1)
    return value - timedelta(days=1)
