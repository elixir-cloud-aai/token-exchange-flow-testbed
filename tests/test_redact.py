"""Tests of `testbed.redact`."""

import base64

from testbed.redact import REMOVED, scrub, token_view, unverified_claims
from tests.conftest import FakeProvider


def test_scrub_removes_nested_tokens(provider: FakeProvider) -> None:
    """JWTs at any depth are removed, e.g., visas in passports."""
    token = provider.mint()
    scrubbed = scrub({"a": [token, {"b": f"text {token} text"}], "c": 1})
    assert scrubbed == {"a": [REMOVED, {"b": f"text {REMOVED} text"}], "c": 1}


def test_token_view_has_claims_but_no_signature(provider: FakeProvider) -> None:
    """Views have the claims, selected header fields and no signature."""
    token = provider.mint(ga4gh_passport_v1=[provider.mint()])
    view = token_view(token)
    assert view["claims"]["sub"] == "user-1"
    assert view["claims"]["ga4gh_passport_v1"] == [REMOVED]
    assert set(view["header"]) == {"alg", "kid", "typ"}
    assert token.rsplit(".", 1)[1] not in str(view)


def test_opaque_tokens_show_only_their_format() -> None:
    """Opaque tokens aren't shown."""
    assert token_view("opaque-value") == {"format": "opaque"}
    assert token_view("a.b.c") == {"format": "opaque"}
    assert unverified_claims("opaque-value") == {}
    assert unverified_claims("a.b.c") == {}


def test_tokens_with_parts_that_are_not_objects_are_opaque() -> None:
    """A JWT-like value whose parts are JSON, but no objects, shows no claims."""
    part = base64.urlsafe_b64encode(b"[1]").decode().rstrip("=")
    assert unverified_claims(f"{part}.{part}.x") == {}
    assert token_view(f"{part}.{part}.x") == {"format": "opaque"}
