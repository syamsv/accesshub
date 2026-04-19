"""Unit tests for the .env value parser.

Regression coverage for the bug where ``KEY="val" # comment`` was leaving
the inline comment glued onto the value.
"""

import pytest

from config.config import Config


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("val", "val"),
        ('"val"', "val"),
        ("'val'", "val"),
        ('"val" # comment', "val"),
        ('"tag:prod,tag:web" # comma seperated', "tag:prod,tag:web"),
        ('"unterminated', '"unterminated'),  # unterminated quote: keep raw
        ("", ""),
        ("no quotes at all", "no quotes at all"),
        ("'with spaces'", "with spaces"),
        ('""', ""),
    ],
)
def test_parse_value(raw: str, expected: str) -> None:
    assert Config._parse_value(raw) == expected
