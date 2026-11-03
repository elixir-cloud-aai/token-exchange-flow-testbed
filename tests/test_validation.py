"""Tests of `testbed.validation`: the checks that FOCA makes."""

import json
import time
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from testbed.validation import InvalidToken, TokenValidator, discover
from tests.conftest import FakeProvider, FakeResponse


def _validator(provider: FakeProvider) -> TokenValidator:
    """Create a validator for the node.

    Args:
        provider: Fake provider.

    Returns:
        Validator.
    """
    return TokenValidator([provider.issuer], ["id-node"], provider)


def _reason(provider: FakeProvider, token: str) -> str:
    """Get the reason for which a token is refused.

    Args:
        provider: Fake provider.
        token: Token.

    Returns:
        Reason.
    """
    with pytest.raises(InvalidToken) as caught:
        _validator(provider).validate(token)
    return caught.value.reason


def test_valid_token(provider: FakeProvider) -> None:
    """A valid token yields its claims; `aud` may be a list."""
    assert _validator(provider).validate(provider.mint())["sub"] == "user-1"
    token = provider.mint(aud=["other", "id-node"])
    assert _validator(provider).validate(token)["sub"] == "user-1"


def test_media_type_form_of_typ_is_accepted(provider: FakeProvider) -> None:
    """As in FOCA, `typ` may be the full media type, in any case."""
    claims = _validator(provider).validate(provider.mint(typ="Application/AT+JWT"))
    assert claims["sub"] == "user-1"


@pytest.mark.parametrize(
    ("claims", "reason"),
    [
        ({"aud": "id-gateway"}, "audience"),
        ({"aud": None}, "audience"),
        ({"exp": 1000, "iat": 500}, "expired"),
        ({"exp": None}, "claims"),
        ({"iat": None}, "claims"),
        ({"sub": None}, "claims"),
        ({"iss": "https://other.example/"}, "issuer"),
        ({"iss": None}, "issuer"),
        ({"nbf": int(time.time()) + 3600}, "claims"),
    ],
)
def test_refused_claims(
    provider: FakeProvider, claims: dict[str, Any], reason: str
) -> None:
    """Tokens with wrong or missing claims are refused, for the right reason."""
    assert _reason(provider, provider.mint(**claims)) == reason


@pytest.mark.parametrize("typ", ["JWT", "id_token"])
def test_refused_type(provider: FakeProvider, typ: str) -> None:
    """Other JWTs of the issuer, e.g., ID tokens, are refused."""
    assert _reason(provider, provider.mint(typ=typ)) == "type"


def test_no_type_is_refused(provider: FakeProvider) -> None:
    """Tokens without a `typ` header are refused."""
    token = jwt.encode(
        {"iss": provider.issuer, "sub": "user-1"},
        provider.key,
        algorithm="RS256",
        headers={"typ": None},
    )
    assert _reason(provider, token) == "type"


def test_other_key_with_known_kid_is_refused(provider: FakeProvider) -> None:
    """A token signed with another key, claiming a known key ID, is refused."""
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    assert _reason(provider, provider.mint(key=other)) == "signature"


def test_tampered_payload_is_refused(provider: FakeProvider) -> None:
    """Changing the claims of a token invalidates it."""
    header, _, signature = provider.mint().split(".")
    claims = {
        "iss": provider.issuer,
        "sub": "evil",
        "aud": "id-node",
        "iat": 1,
        "exp": 99999999999,
    }
    payload = jwt.utils.base64url_encode(json.dumps(claims).encode()).decode()
    assert _reason(provider, f"{header}.{payload}.{signature}") == "signature"


def test_algorithm_confusion_is_refused(provider: FakeProvider) -> None:
    """Tokens with an algorithm that isn't accepted are refused."""
    # A made-up key, for a token that must be refused
    token = jwt.encode(  # nosemgrep
        {
            "iss": provider.issuer,
            "sub": "user-1",
            "aud": "id-node",
            "iat": 1,
            "exp": 99999999999,
        },
        "x" * 32,
        algorithm="HS256",
        headers={"typ": "at+jwt", "kid": provider.kid},
    )
    assert _reason(provider, token) == "signature"


def test_malformed_token_is_refused(provider: FakeProvider) -> None:
    """Anything but a JWT is refused."""
    assert _reason(provider, "not-a-jwt") == "malformed"


def test_unknown_key_refetches_once(provider: FakeProvider) -> None:
    """An unknown key ID triggers one more fetch of the keys, then a refusal."""
    assert _reason(provider, provider.mint(kid="unknown")) == "key"
    assert provider.jwks_hits == 2


def test_rotated_key_is_found(provider: FakeProvider) -> None:
    """A key that appears after the first fetch is found on the second."""
    validator = _validator(provider)
    validator.validate(provider.mint())
    provider.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    provider.kid = "key-2"
    assert validator.validate(provider.mint())["sub"] == "user-1"


def test_discovery_for_another_issuer_is_refused(provider: FakeProvider) -> None:
    """A discovery document must be about the issuer of the token."""
    provider.discovery_overrides = {"issuer": "https://other.example/"}
    assert _reason(provider, provider.mint()) == "provider"


def test_missing_jwks_uri_is_refused(provider: FakeProvider) -> None:
    """A discovery document must name the keys."""
    provider.discovery_overrides = {"jwks_uri": None}
    assert _reason(provider, provider.mint()) == "provider"


def test_unavailable_keys_are_a_provider_problem(provider: FakeProvider) -> None:
    """Failing to fetch the keys isn't a problem of the token."""
    provider.routes[f"{provider.issuer.rstrip('/')}/jwks"] = lambda _url, _kw: (
        FakeResponse(500)
    )
    assert _reason(provider, provider.mint()) == "provider"


def test_details_hold_no_tokens(provider: FakeProvider) -> None:
    """Details of refusals are free of tokens."""
    token = provider.mint()
    assert token not in InvalidToken("issuer", f"Issuer {token}").detail


def test_discovery_failure_names_the_url(provider: FakeProvider) -> None:
    """A provider that can't be reached is reported without details of the error."""
    provider.routes[provider.issuer] = lambda _url, _options: FakeResponse(500)
    with pytest.raises(InvalidToken, match="Discovery failed") as refused:
        discover(provider.issuer, provider)
    assert refused.value.reason == "provider"
