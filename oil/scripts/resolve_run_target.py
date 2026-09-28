"""Print REPORT_SLOT / BASE_DATE / ALREADY_PUBLISHED lines for $GITHUB_ENV.

Scheduled runs take the slot from the cron that fired (not the delayed start
time) and never rebuild a report that is already published. Manual runs keep
their existing behaviour unless skip_if_published=true is requested.
"""
from __future__ import annotations

import os
from pathlib import Path

from utils_time import resolve_base_date, resolve_scheduled_target, resolve_slot

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    event = os.getenv("EVENT_NAME", "")
    if event == "schedule":
        day, slot = resolve_scheduled_target(os.getenv("SCHEDULE_CRON", ""))
        skip_if_published = True
    else:
        slot = resolve_slot(os.getenv("INPUT_SLOT", ""))
        day = resolve_base_date(os.getenv("INPUT_BASE_DATE", ""))
        skip_if_published = os.getenv("INPUT_SKIP_IF_PUBLISHED", "false").lower() == "true"
    published = (ROOT / "data" / "reports" / f"{day.isoformat()}-{slot}.json").exists()
    print(f"REPORT_SLOT={slot}")
    print(f"BASE_DATE={day.isoformat()}")
    print(f"ALREADY_PUBLISHED={'true' if skip_if_published and published else 'false'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
