"""Tests of `testbed.hops`."""

import pytest

from testbed.hops import DEFAULT_HOP_LIMIT, parse_hop_limit, resolve_traceparent

VALID = "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, DEFAULT_HOP_LIMIT),
        ("0", 0),
        ("3", 3),
        ("-1", None),
        ("x", None),
        ("", None),
        ("٣", None),
    ],
)
def test_parse_hop_limit(value: str | None, expected: int | None) -> None:
    """Hop limits are non-negative integers; a missing header gets the default."""
    assert parse_hop_limit(value) == expected


def test_valid_traceparent_is_passed_through() -> None:
    """A valid `traceparent` isn't changed."""
    assert resolve_traceparent(VALID) == (VALID, "received")


@pytest.mark.parametrize(
    "value",
    [
        None,
        "nonsense",
        "00-00000000000000000000000000000000-b7ad6b7169203331-01",
        "00-0af7651916cd43dd8448eb211c80319c-0000000000000000-01",
    ],
)
def test_invalid_traceparent_is_replaced(value: str | None) -> None:
    """Missing or invalid values are replaced by a new, valid one."""
    generated, origin = resolve_traceparent(value)
    assert origin == "generated"
    assert resolve_traceparent(generated) == (generated, "received")
