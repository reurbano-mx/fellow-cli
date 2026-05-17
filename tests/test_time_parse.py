from datetime import datetime, timezone

import pytest

from fellowai.time_parse import parse_since


def test_parse_relative_days():
    now = datetime(2026, 5, 16, tzinfo=timezone.utc)
    assert parse_since("7d", now=now) == "2026-05-09T00:00:00Z"


def test_parse_relative_weeks():
    now = datetime(2026, 5, 16, tzinfo=timezone.utc)
    assert parse_since("2w", now=now) == "2026-05-02T00:00:00Z"


def test_parse_relative_hours():
    now = datetime(2026, 5, 16, 12, 0, tzinfo=timezone.utc)
    assert parse_since("3h", now=now) == "2026-05-16T09:00:00Z"


def test_parse_absolute_date():
    assert parse_since("2026-04-01") == "2026-04-01T00:00:00Z"


def test_parse_absolute_datetime():
    assert parse_since("2026-04-01T15:30:00Z") == "2026-04-01T15:30:00Z"


def test_invalid_format_raises():
    with pytest.raises(ValueError, match="Unrecognized date"):
        parse_since("not-a-date")


def test_unknown_unit_raises():
    with pytest.raises(ValueError, match="Unrecognized date"):
        parse_since("7x")
