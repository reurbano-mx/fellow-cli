"""Parse user-supplied --since/--until values into ISO-8601 UTC strings."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

_RELATIVE = re.compile(r"^(\d+)([hdw])$")
_UNIT_TO_TIMEDELTA = {
    "h": lambda n: timedelta(hours=n),
    "d": lambda n: timedelta(days=n),
    "w": lambda n: timedelta(weeks=n),
}


def parse_since(value: str, *, now: datetime | None = None) -> str:
    """Convert a user-supplied date into an ISO-8601 UTC string."""
    now = now or datetime.now(timezone.utc)

    m = _RELATIVE.match(value)
    if m:
        n, unit = int(m.group(1)), m.group(2)
        dt = now - _UNIT_TO_TIMEDELTA[unit](n)
        if unit in ("d", "w"):
            dt = dt.replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            dt = dt.replace(minute=0, second=0, microsecond=0)
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
            return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            continue

    raise ValueError(f"Unrecognized date: {value!r}. Use e.g. '7d', '2w', '2026-04-01'.")
