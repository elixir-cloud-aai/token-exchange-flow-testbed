"""Tests of `testbed.settings`."""

import pytest

from testbed.settings import LS_LOGIN_ISSUER, Client, Settings, load_settings
from tests.conftest import LS_ENV


def test_mock_is_the_default_and_emulates_rules() -> None:
    """Without settings, the testbed uses the mock with the rules on."""
    settings = load_settings({})
    assert settings.provider == "mock"
    assert settings.emulate_ls_login_rules


def test_ls_login_uses_the_issuer_and_no_emulation(ls_settings: Settings) -> None:
    """With LS Login, the provider decides alone."""
    assert ls_settings.issuer == LS_LOGIN_ISSUER
    assert ls_settings.trusted_issuers == (LS_LOGIN_ISSUER,)
    assert not ls_settings.emulate_ls_login_rules
    assert ls_settings.clients["node"].resource == "https://node.example/"
    assert ls_settings.clients["public"].secret is None


def test_missing_variables_are_named_without_values() -> None:
    """Errors name missing variables and show no values."""
    env = {**LS_ENV}
    del env["TESTBED_GATEWAY_CLIENT_ID"]
    with pytest.raises(ValueError, match="TESTBED_GATEWAY_CLIENT_ID") as caught:
        load_settings(env, "lslogin")
    assert "secret" not in str(caught.value)


def test_secrets_are_not_in_representations(ls_settings: Settings) -> None:
    """Secrets don't end up in logs through representations."""
    assert "secret-gateway" not in repr(ls_settings)
    assert "secret-gateway" not in repr(Client("gateway", "id", "secret-gateway"))


def test_unknown_values_are_refused() -> None:
    """Unknown providers and target parameters are errors."""
    with pytest.raises(ValueError, match="Unknown provider"):
        load_settings({}, "other")
    with pytest.raises(ValueError, match="TESTBED_TARGET_PARAM"):
        load_settings({"TESTBED_TARGET_PARAM": "other"})


def test_issuer_of_ls_login_can_be_changed(ls_settings: Settings) -> None:
    """Another issuer, e.g., of a new proxy stack, replaces the default."""
    other = "https://login.example/oidc"
    settings = load_settings({**LS_ENV, "TESTBED_ISSUER": other}, "lslogin")
    assert settings.issuer == other
    assert settings.trusted_issuers == (other,)
    assert ls_settings.issuer == LS_LOGIN_ISSUER


@pytest.mark.parametrize(
    ("provider", "env"), [("mock", {}), ("lslogin", LS_ENV)], ids=["mock", "lslogin"]
)
def test_callback_listens_on_localhost_unless_told_otherwise(
    provider: str, env: dict[str, str]
) -> None:
    """Containers set the address; a host stays on its loopback interface."""
    assert load_settings(env, provider).callback_bind == "localhost"
    bound = load_settings({**env, "TESTBED_CALLBACK_BIND": "192.0.2.1"}, provider)
    assert bound.callback_bind == "192.0.2.1"
