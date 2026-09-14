"""
U350 shadow-side registered NYSE session calendar (Order 2026-08-28C FIX 3).

No market calendar existed in the repo before this order (the Phase-A
calendar step only counted distinct snapshot dates), so the calendar is
REGISTERED here, shadow-side: the NYSE full-day holiday list for 2026-2028
plus the weekend rule and the 16:00 America/New_York close. It is a data
table, not weekday arithmetic on its own — a date is a session iff it is a
weekday AND not in HOLIDAYS. Early closes (13:00 ET) are represented
separately and do not remove a session. Source attribution per year is
recorded in CALENDAR_SOURCES; this is the NYSE (cash equities) schedule
only — other exchanges/markets are not represented here.

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
    # 2028 — NYSE Group announcement of 23 December 2025 (2026, 2027 and 2028 holiday and early-closings
    # calendar), rechecked against the official page on 2026-09-14 (V7-005): New Year's Day is not observed
    # for Saturday 1 January 2028; full closures below.
    date(2028, 1, 17), date(2028, 2, 21), date(2028, 4, 14), date(2028, 5, 29), date(2028, 6, 19),
    date(2028, 7, 4), date(2028, 9, 4), date(2028, 11, 23), date(2028, 12, 25),
})
# Cash-equity early closes (13:00 America/New_York); the session exists, its close is EARLY_CLOSE.
EARLY_CLOSES: frozenset[date] = frozenset({
    date(2026, 11, 27), date(2026, 12, 24),          # 2026 (day after Thanksgiving; Christmas Eve)
    date(2027, 11, 26),                              # 2027 (day after Thanksgiving; 24 Dec 2027 is a full closure)
    date(2028, 7, 3), date(2028, 11, 24),            # 2028 (announcement: July 3 and November 24, 1:00 p.m.)
})
EARLY_CLOSE = time(13, 0)
CALENDAR_SOURCES = {
    2026: "NYSE holiday schedule (registered 2026-08-28C)",
    2027: "NYSE holiday schedule (registered 2026-08-28C)",
    2028: "NYSE Group announcement 2025-12-23 'NYSE Group Announces 2026, 2027 and 2028 Holiday and Early Closings Calendar' (ir.theice.com), rechecked 2026-09-14",
}
CALENDAR_RANGE = (date(2026, 1, 1), date(2028, 12, 31))


def is_early_close(d: date) -> bool:
    return is_session(d) and d in EARLY_CLOSES


def close_time(d: date) -> time:
    """Session close for a session date: 13:00 ET on early-close days, else 16:00 ET."""
    if not is_session(d):
        raise ValueError(f"{d} is not a session")
    return EARLY_CLOSE if d in EARLY_CLOSES else CLOSE


def is_session(d: date) -> bool:
    if not (CALENDAR_RANGE[0] <= d <= CALENDAR_RANGE[1]):
        raise ValueError(f"{d} outside registered calendar range "
                         f"{CALENDAR_RANGE}; extend HOLIDAYS")
    return d.weekday() < 5 and d not in HOLIDAYS


def close_utc(d: date) -> datetime:
    """UTC instant of the session close (honours early closes; a non-session date keeps the nominal 16:00 close)."""
    t = close_time(d) if (CALENDAR_RANGE[0] <= d <= CALENDAR_RANGE[1] and is_session(d)) else CLOSE
    return datetime.combine(d, t, tzinfo=NY).astimezone(timezone.utc)


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
