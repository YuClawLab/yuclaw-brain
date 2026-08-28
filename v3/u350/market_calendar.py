"""
U350 shadow-side registered NYSE session calendar (Order 2026-08-28C FIX 3).

No market calendar existed in the repo before this order (the Phase-A
calendar step only counted distinct snapshot dates), so the calendar is
REGISTERED here, shadow-side: the NYSE full-day holiday list for 2026-2027
plus the weekend rule and the 16:00 America/New_York close. It is a data
table, not weekday arithmetic on its own — a date is a session iff it is a
weekday AND not in HOLIDAYS. Extend HOLIDAYS before 2028.

latest_completed_session(now) = the most recent session whose close
(16:00 ET) is <= now. Same-day re-runs therefore map to the same session
date, which is the idempotency key for shadow snapshot ids.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
CLOSE = time(16, 0)

# NYSE full-day closures (registered; source: NYSE holiday schedule).
HOLIDAYS: frozenset[date] = frozenset({
    # 2026
    date(2026, 1, 1), date(2026, 1, 19), date(2026, 2, 16), date(2026, 4, 3),
    date(2026, 5, 25), date(2026, 6, 19), date(2026, 7, 3), date(2026, 9, 7),
    date(2026, 11, 26), date(2026, 12, 25),
    # 2027
    date(2027, 1, 1), date(2027, 1, 18), date(2027, 2, 15), date(2027, 3, 26),
    date(2027, 5, 31), date(2027, 6, 18), date(2027, 7, 5), date(2027, 9, 6),
    date(2027, 11, 25), date(2027, 12, 24),
})
CALENDAR_RANGE = (date(2026, 1, 1), date(2027, 12, 31))


def is_session(d: date) -> bool:
    if not (CALENDAR_RANGE[0] <= d <= CALENDAR_RANGE[1]):
        raise ValueError(f"{d} outside registered calendar range "
                         f"{CALENDAR_RANGE}; extend HOLIDAYS")
    return d.weekday() < 5 and d not in HOLIDAYS


def close_utc(d: date) -> datetime:
    return datetime.combine(d, CLOSE, tzinfo=NY).astimezone(timezone.utc)


def latest_completed_session(now: datetime | None = None) -> date:
    now = (now or datetime.now(timezone.utc)).astimezone(NY)
    d = now.date()
    while not (is_session(d) and now >= close_utc(d).astimezone(NY)):
        d -= timedelta(days=1)
    return d


def next_session(d: date) -> date:
    d += timedelta(days=1)
    while not is_session(d):
        d += timedelta(days=1)
    return d


def session_window_utc(d: date) -> tuple[datetime, datetime]:
    """[close of session d, close of the following session): rows whose
    signal_time falls in this window were scored against session d."""
    return close_utc(d), close_utc(next_session(d))


def session_of(ts: datetime) -> date:
    return latest_completed_session(ts)
