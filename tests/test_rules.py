"""Tests of `testbed.rules`, the emulation of LS Login's rules for the mock."""

import pytest

from testbed.rules import RuleViolation, check_exchange
from testbed.settings import Client
from testbed.validation import TokenValidator
from tests.conftest import FakeProvider

CLIENT = Client("gateway", "id-gateway", "x", registered=("id-node",))


def _validator(provider: FakeProvider) -> TokenValidator:
    """Create the validator for the rule.

    Args:
        provider: Fake provider.

    Returns:
        Validator that accepts the exchanging client as audience.
    """
    return TokenValidator([provider.issuer], [CLIENT.client_id], provider)


def test_allowed_exchange(provider: FakeProvider) -> None:
    """Our client in `aud` and a registered target pass."""
    token = provider.mint(aud=["id-gateway"])
    check_exchange(CLIENT, token, ["id-node"], _validator(provider))


def test_exchanging_client_must_be_in_aud(provider: FakeProvider) -> None:
    """LS Login: the exchanging client's ID must be in the subject's `aud`."""
    token = provider.mint(aud=["id-client"])
    with pytest.raises(RuleViolation) as caught:
        check_exchange(CLIENT, token, ["id-node"], _validator(provider))
    assert caught.value.error == "invalid_grant"
    assert "audience" in caught.value.description


def test_target_must_be_registered(provider: FakeProvider) -> None:
    """LS Login: targets are validated against registered resource indicators."""
    token = provider.mint(aud=["id-gateway"])
    with pytest.raises(RuleViolation) as caught:
        check_exchange(CLIENT, token, ["id-other"], _validator(provider))
    assert caught.value.error == "invalid_target"


def test_expired_subject_is_refused(provider: FakeProvider) -> None:
    """An expired subject token is refused (assumed, to be seen on LS Login)."""
    token = provider.mint(aud=["id-gateway"], exp=1000, iat=500)
    with pytest.raises(RuleViolation, match="expired"):
        check_exchange(CLIENT, token, ["id-node"], _validator(provider))
