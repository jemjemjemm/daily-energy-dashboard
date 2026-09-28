"""Asia/Seoul report-slot and publication-time helpers."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")
VALID_SLOTS = {"morning", "evening", "night"}


def now_kst() -> datetime:
    return datetime.now(KST)


def resolve_base_date(value: str | None = None, now: datetime | None = None) -> date:
    if value and value.strip():
        return date.fromisoformat(value.strip())
    current = (now or now_kst()).astimezone(KST)
    return current.date()


def resolve_slot(value: str | None = None, now: datetime | None = None) -> str:
    slot = (value or "").strip().lower()
    if slot:
        if slot not in VALID_SLOTS:
            raise ValueError("report_slot must be morning, evening or night")
        return slot
    current = (now or now_kst()).astimezone(KST)
    # Scheduled runs are 08:10 and 17:10. For delayed runs, use the nearest
    # completed reporting boundary rather than silently choosing by UTC.
    return "morning" if current.hour < 17 else "evening"


# GitHub cron expressions (UTC) in .github/workflows/oil-report.yml -> slot.
SCHEDULE_SLOTS = {"10 23 * * *": "morning", "10 8 * * *": "evening"}
SLOT_END_HOUR = {"morning": 8, "evening": 17}


def resolve_scheduled_target(cron: str, now: datetime | None = None) -> tuple[date, str]:
    """Resolve the report a scheduled run was meant for, however late it starts.

    GitHub regularly starts scheduled runs hours late (e.g. the 17:10 evening
    run started at 00:03 the next day on 2026-09-22). Deciding by wall-clock
    time then produced a premature next-day morning report and skipped the
    evening report. The cron that fired tells us the slot; the report date is
    the most recent day whose slot window has already closed.
    """
    slot = SCHEDULE_SLOTS[cron.strip()]
    current = (now or now_kst()).astimezone(KST)
    day = current.date()
    if current.hour < SLOT_END_HOUR[slot]:
        day -= timedelta(days=1)
    return day, slot


def get_period(base_date: date | str, slot: str) -> tuple[datetime, datetime]:
    day = date.fromisoformat(base_date) if isinstance(base_date, str) else base_date
    slot = resolve_slot(slot)
    if slot == "morning":
        return (
            datetime.combine(day, time(0), KST),
            datetime.combine(day, time(8), KST),
        )
    if slot == "evening":
        return datetime.combine(day, time(8), KST), datetime.combine(day, time(17), KST)
    return datetime.combine(day, time(17), KST), datetime.combine(day + timedelta(days=1), time(0), KST)


def parse_datetime(value: str | datetime | None) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        from dateutil import parser

        try:
            parsed = parser.parse(value)
        except (ValueError, TypeError, OverflowError):
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=KST)
    return parsed.astimezone(KST)


def is_in_period(value: str | datetime | None, start: datetime, end: datetime) -> bool:
    parsed = parse_datetime(value)
    return parsed is not None and start <= parsed < end


def period_label(start: datetime, end: datetime) -> str:
    return f"{start:%Y-%m-%d %H:%M} ~ {end:%Y-%m-%d %H:%M}"
