"""Hop limit and trace context across services."""

import re
import secrets

# Number of further forwards allowed. There's no standard header for this:
# `Max-Forwards` (RFC 9110) only applies to TRACE and OPTIONS. Not signed, so it
# stops accidental loops only: a misbehaving hop can reset it.
HOP_LIMIT_HEADER = "Hop-Limit"
DEFAULT_HOP_LIMIT = 8
MAX_DIGITS = 3
TRACEPARENT_HEADER = "traceparent"
_TRACEPARENT = re.compile(r"00-([0-9a-f]{32})-([0-9a-f]{16})-[0-9a-f]{2}")


def parse_hop_limit(value: str | None) -> int | None:
    """Parse a hop limit header.

    Args:
        value: Value of the header, if any.

    Returns:
        The hop limit, the default if there's no header, `None` if invalid.
    """
    if value is None:
        return DEFAULT_HOP_LIMIT
    if not value.isascii() or not value.isdigit() or len(value) > MAX_DIGITS:
        return None
    return int(value)


def resolve_traceparent(value: str | None) -> tuple[str, str]:
    """Get the trace context to use and pass on.

    A valid `traceparent` (W3C Trace Context) is passed on unchanged, which the
    specification allows for services that don't take part in the trace.

    Args:
        value: Received value, if any.

    Returns:
        Value to use, and `received` or `generated`.
    """
    if value is not None:
        match = _TRACEPARENT.fullmatch(value)
        if match and set(match[1]) != {"0"} and set(match[2]) != {"0"}:
            return value, "received"
    return f"00-{secrets.token_hex(16)}-{secrets.token_hex(8)}-01", "generated"
