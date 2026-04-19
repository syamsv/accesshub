"""Unit tests for the duration renderer. Bypass env init — no config needed."""

import pytest

from assets.tailscale import format_duration


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("60", "1 hour"),
        ("120", "2 hours"),
        ("90", "1 hour 30 min"),
        ("240", "4 hours"),
        ("30", "30 min"),
        ("1440", "1 day"),
        ("permanent", "Permanent"),
        ("PERMANENT", "Permanent"),
        (None, "—"),
        ("", "—"),
        ("0", "—"),
        ("-5", "—"),
        ("not a number", "not a number"),
    ],
)
def test_format_duration(raw, expected) -> None:
    assert format_duration(raw) == expected
