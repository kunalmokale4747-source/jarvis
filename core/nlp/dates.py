"""Small dependency-free natural-language date/time interpreter.

The interpreter is deliberately conservative. It returns ambiguity information so
callers can ask a follow-up question instead of silently inventing a time.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import re
from typing import Optional


WEEKDAYS = {
    "monday": 0,
    "mon": 0,
    "tuesday": 1,
    "tue": 1,
    "tues": 1,
    "wednesday": 2,
    "wed": 2,
    "thursday": 3,
    "thu": 3,
    "thur": 3,
    "thurs": 3,
    "friday": 4,
    "fri": 4,
    "saturday": 5,
    "sat": 5,
    "sunday": 6,
    "sun": 6,
}

HINGLISH_DATE_WORDS = {
    "aaj": "today",
    "today": "today",
    "kal": "tomorrow",
    "tomorrow": "tomorrow",
    "parso": "day_after_tomorrow",
    "parson": "day_after_tomorrow",
}

TIMEZONE_ALIASES = {
    "utc": "UTC",
    "gmt": "UTC",
    "ist": "Asia/Kolkata",
    "india": "Asia/Kolkata",
    "et": "America/New_York",
    "est": "America/New_York",
    "edt": "America/New_York",
    "pt": "America/Los_Angeles",
    "pst": "America/Los_Angeles",
    "pdt": "America/Los_Angeles",
    "cet": "Europe/Paris",
}


@dataclass
class DateTimeInterpretation:
    has_date: bool
    has_time: bool
    requires_time: bool
    when: Optional[datetime]
    date_value: Optional[date]
    time_value: Optional[time]
    timezone: str
    ambiguous: bool
    clarification: str | None
    matched: list[str]
    requires_confirmation: bool = False


def _zone(name: str | None) -> str:
    candidate = (name or "UTC").strip()
    alias = TIMEZONE_ALIASES.get(candidate.lower())
    if alias:
        candidate = alias
    try:
        ZoneInfo(candidate)
        return candidate
    except ZoneInfoNotFoundError:
        return "UTC"


def _next_weekday(now_date: date, weekday: int, *, allow_today: bool = False) -> date:
    days = (weekday - now_date.weekday()) % 7
    if days == 0 and not allow_today:
        days = 7
    return now_date + timedelta(days=days)


def _extract_time(text: str) -> tuple[Optional[time], bool, list[str]]:
    low = text.lower()
    matched: list[str] = []

    # 24-hour time
    for pattern in (r"\b(\d{1,2}):(\d{2})\b",):
        import re

        for m in re.finditer(pattern, low):
            hh = int(m.group(1))
            mm = int(m.group(2))
            if 0 <= hh <= 23 and 0 <= mm <= 59:
                t = time(hour=hh, minute=mm)
                matched.append(m.group(0))
                return t, True, matched

    # 12-hour time with optional minutes
    import re

    m = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b", low)
    if m:
        hour = int(m.group(1)) % 12
        minute = int(m.group(2) or 0)
        if m.group(3) == "pm":
            hour += 12
        if 0 <= minute <= 59:
            t = time(hour=hour, minute=minute)
            matched.append(m.group(0))
            return t, True, matched

    # Bare "at 7" is intentionally treated as ambiguous-ish but usable for date-only? For reminders, exact time required.
    m = re.search(r"\bat\s+(\d{1,2})\b", low)
    if m:
        hour = int(m.group(1))
        if 0 <= hour <= 23:
            t = time(hour=hour, minute=0)
            matched.append(m.group(0))
            return t, True, matched

    return None, False, matched


def interpret(
    text: str,
    *,
    now: Optional[datetime] = None,
    require_time: bool = False,
    default_timezone: str = "UTC",
    is_reminder: bool = False,
) -> DateTimeInterpretation:
    text = (text or "").strip()
    low = text.lower()
    now = now or datetime.now(timezone.utc)
    matched: list[str] = []
    tz = default_timezone

    # Timezone phrase
    for word, zone in TIMEZONE_ALIASES.items():
        if re.search(rf"\b{re.escape(word)}\b", low):
            tz = zone
            matched.append(word)
            break

    # If no explicit timezone in phrase but a profile-style "Asia/Kolkata" is present
    for zone_candidate in ["utc", "Asia/Kolkata", "America/New_York", "America/Los_Angeles", "Europe/Paris"]:
        if zone_candidate.lower() in low:
            tz = zone_candidate
            matched.append(zone_candidate)
            break

    zone = _zone(tz)
    local_now = now.astimezone(ZoneInfo(zone))

    # Date interpretation
    date_value = None
    date_matched = False
    for word, mapped in HINGLISH_DATE_WORDS.items():
        if re.search(rf"\b{re.escape(word)}\b", low):
            matched.append(word)
            date_matched = True
            if mapped == "today":
                date_value = local_now.date()
            elif mapped == "tomorrow":
                date_value = local_now.date() + timedelta(days=1)
            elif mapped == "day_after_tomorrow":
                date_value = local_now.date() + timedelta(days=2)
            break

    # next weekday
    if date_value is None:
        for word, weekday in WEEKDAYS.items():
            if re.search(rf"\b{word}\b", low):
                date_value = _next_weekday(local_now.date(), weekday)
                date_matched = True
                matched.append(word)
                break

    # ISO date
    if date_value is None:
        import re as _re

        m = _re.search(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", low)
        if m:
            try:
                date_value = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
                date_matched = True
                matched.append(m.group(0))
            except ValueError:
                pass

    # date part of datetime via phrase "on 5 July" is not supported without dateutil.

    time_value, has_time, time_matched = _extract_time(text)
    matched.extend(time_matched)

    has_date = date_value is not None
    ambiguous = False
    clarification = None
    when = None

    if has_date and has_time:
        dt = datetime.combine(date_value, time_value, tzinfo=ZoneInfo(zone))
        when = dt.astimezone(timezone.utc)
    elif has_date and not has_time and not require_time:
        dt = datetime.combine(date_value, time(23, 59), tzinfo=ZoneInfo(zone))
        when = dt.astimezone(timezone.utc)
    elif has_date and not has_time and require_time:
        ambiguous = True
        clarification = "What time should I use? Please include an hour, such as 7 PM."
    elif not has_date and has_time:
        # time without date could mean today, but keep ambiguity for consequential asks
        dt = datetime.combine(local_now.date(), time_value, tzinfo=ZoneInfo(zone))
        if dt <= local_now:
            dt = dt + timedelta(days=1)
        when = dt.astimezone(timezone.utc)
        ambiguous = True
        clarification = "Which date should I use for this time?"
    else:
        if is_reminder or require_time:
            ambiguous = True
            clarification = "I need both a date and time for this reminder."

    # Kal can mean today/yesterday/tomorrow in Hindi. Flag ambiguity.
    if re.search(r"\bkal\b", low) and "tomorrow" not in low:
        ambiguous = True
        if clarification is None:
            clarification = "'kal' can mean today, yesterday, or tomorrow. Please clarify the date."

    return DateTimeInterpretation(
        has_date=has_date,
        has_time=has_time,
        requires_time=require_time,
        when=when,
        date_value=date_value,
        time_value=time_value,
        timezone=zone,
        ambiguous=ambiguous,
        clarification=clarification,
        matched=matched,
    )


def interpret_datetime(*args, **kwargs):
    return interpret(*args, **kwargs)


def parse_natural_datetime(*args, **kwargs):
    return interpret(*args, **kwargs)


def extract_datetime(*args, **kwargs):
    return interpret(*args, **kwargs)


# Backwards-ish aliases
interpret_date = interpret
parse_date = interpret
