"""The app's weekly plan: 7 days, Monday first, 24 one-hour slots per day.

A heater follows its plan only in mode AUTO. Each slot is off, comfort (the
setpoint) or eco.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta, tzinfo

# The app's day letters, Monday first (X is Wednesday), as in slot ids "L-08:00".
DAYS = "LMXJVSD"
OFF, COMFORT, ECO = "0", "1", "2"
MODES = {OFF: "off", COMFORT: "comfort", ECO: "eco"}

type Week = list[str]


def week_from_slots(slots: dict[str, str] | None) -> Week | None:
    """{"L-08:00": "1", ...} to 7 strings of 24 states. A missing slot is off, as in the app."""
    if slots is None:
        return None
    week = []
    for day in DAYS:
        states = (slots.get(f"{day}-{hour:02d}:00", OFF) for hour in range(24))
        week.append("".join(s if s in MODES else OFF for s in states))
    return week


def mode_at(week: Week, when: datetime) -> str:
    """Plan mode at a local time: "off", "comfort" or "eco"."""
    return MODES[week[when.weekday()][when.hour]]


def blocks(week: Week, start: datetime, end: datetime, tz: tzinfo) -> list[tuple[datetime, datetime, str]]:
    """Comfort and eco periods that overlap [start, end), merged across midnight.

    Starts a week early so a period that began before `start` keeps its real start.
    """
    day = start.astimezone(tz).date() - timedelta(days=7)
    last = end.astimezone(tz).date()
    found = []
    current: tuple[str, datetime] | None = None
    while day <= last:
        for hour, state in enumerate(week[day.weekday()]):
            if current and current[0] == state:
                continue
            at = datetime.combine(day, time(hour), tzinfo=tz)
            if current and current[0] != OFF:
                found.append((current[1], at, MODES[current[0]]))
            current = (state, at)
        day += timedelta(days=1)
    if current and current[0] != OFF:
        found.append((current[1], datetime.combine(day, time(0), tzinfo=tz), MODES[current[0]]))
    return [b for b in found if b[0] < b[1] and b[1] > start and b[0] < end]
