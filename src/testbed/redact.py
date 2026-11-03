"""Views of tokens that are safe to show: decoded claims, never tokens."""

import base64
import json
import re
from typing import Any

# Anything shaped like a JWS, e.g., visas in a `ga4gh_passport_v1` claim
JWT_PATTERN = re.compile(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]*")
REMOVED = "<token removed>"
HEADER_FIELDS = ("alg", "kid", "typ")


def scrub(value: Any) -> Any:
    """Remove anything shaped like a token from a value.

    Args:
        value: Any JSON-like value.

    Returns:
        Copy of the value in which all JWTs are replaced by a marker.
    """
    if isinstance(value, str):
        return JWT_PATTERN.sub(REMOVED, value)
    if isinstance(value, dict):
        return {key: scrub(item) for key, item in value.items()}
    if isinstance(value, list):
        return [scrub(item) for item in value]
    return value


def _decode_part(part: str) -> dict[str, Any]:
    """Decode one part of a JWT.

    Args:
        part: Base64url-encoded JSON object.

    Returns:
        Decoded object.

    Raises:
        ValueError: The part is not a base64url-encoded JSON object.
    """
    try:
        decoded = json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))
    except RecursionError as exc:
        raise ValueError("JWT part is nested too deeply") from exc
    if not isinstance(decoded, dict):
        raise ValueError("JWT part is not a JSON object")
    return decoded


def unverified_claims(token: str) -> dict[str, Any]:
    """Decode the claims of a JWT, without verifying it.

    For display, and for finding the keys of the issuer that the token names:
    never trust the result.

    Args:
        token: JWT.

    Returns:
        Claims, or an empty dictionary if the token is opaque.
    """
    parts = token.split(".")
    if len(parts) != 3:
        return {}
    try:
        return _decode_part(parts[1])
    except ValueError:
        return {}


def token_view(token: str) -> dict[str, Any]:
    """Create a view of a token that is safe to show.

    Args:
        token: JWT or opaque token.

    Returns:
        Selected header fields and all claims, without the signature and with
        nested tokens removed; only the format for opaque tokens.
    """
    parts = token.split(".")
    if len(parts) != 3:
        return {"format": "opaque"}
    try:
        header = _decode_part(parts[0])
        claims = scrub(_decode_part(parts[1]))
    except (ValueError, RecursionError):
        return {"format": "opaque"}
    return {
        "format": "jwt",
        "header": {key: header[key] for key in HEADER_FIELDS if key in header},
        "claims": claims,
    }
