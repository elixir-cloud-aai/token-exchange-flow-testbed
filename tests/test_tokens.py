"""Tests of `testbed.tokens`."""

import pytest

from testbed.rules import REFUSED_BY_RULE
from testbed.settings import Settings
from testbed.tokens import (
    GRANT_EXCHANGE,
    REFUSED_BY_PROVIDER,
    TYPE_ACCESS,
    TYPE_REFRESH,
    Refused,
    TokenClient,
    TokenResponse,
)
from tests.conftest import FakeProvider, FakeResponse


def test_exchange_sends_the_rfc_8693_form(
    ls_settings: Settings, provider: FakeProvider
) -> None:
    """Exchanges carry all parameters, with basic authentication by default."""
    client = ls_settings.clients["gateway"]
    subject = provider.mint(aud=["id-gateway"])
    issued = TokenClient(ls_settings, provider).exchange(
        client,
        subject,
        audience=["id-node"],
        resource=["https://node.example/"],
        scope="openid",
        requested_type=TYPE_REFRESH,
    )
    _, form, options = provider.posts[-1]
    assert form == {
        "grant_type": GRANT_EXCHANGE,
        "subject_token": subject,
        "subject_token_type": TYPE_ACCESS,
        "audience": ["id-node"],
        "resource": ["https://node.example/"],
        "scope": "openid",
        "requested_token_type": TYPE_REFRESH,
    }
    assert options["auth"] == ("id-gateway", "secret-gateway")
    assert issued.access_token


@pytest.mark.parametrize(
    ("role", "auth", "secret_in_form", "has_client_id"),
    [
        ("gateway", "post", True, True),
        ("gateway", "none", False, True),
        ("public", "auto", False, True),
    ],
)
def test_client_authentication_methods(
    ls_settings: Settings,
    provider: FakeProvider,
    role: str,
    auth: str,
    secret_in_form: bool,
    has_client_id: bool,
) -> None:
    """Clients can authenticate in the form, or not at all if public."""
    TokenClient(ls_settings, provider).exchange(
        ls_settings.clients[role], provider.mint(), auth=auth
    )
    _, form, options = provider.posts[-1]
    assert ("client_secret" in form) is secret_in_form
    assert ("client_id" in form) is has_client_id
    assert "auth" not in options


def test_ls_login_alone_decides(ls_settings: Settings, provider: FakeProvider) -> None:
    """With LS Login, the testbed's rules aren't applied."""
    subject = provider.mint(aud=["somebody-else"])
    TokenClient(ls_settings, provider).exchange(
        ls_settings.clients["gateway"], subject, audience=["anything"]
    )
    assert provider.posts


def test_mock_applies_the_rules(
    mock_settings: Settings, mock_provider: FakeProvider
) -> None:
    """With the mock, the rules refuse before the mock is even asked."""
    subject = mock_provider.mint(aud=["somebody-else"])
    with pytest.raises(Refused) as caught:
        TokenClient(mock_settings, mock_provider).exchange(
            mock_settings.clients["gateway"], subject, audience=["tx-node"]
        )
    assert caught.value.refused_by == REFUSED_BY_RULE
    assert not mock_provider.posts


def test_mock_rules_can_be_turned_off(
    mock_settings: Settings, mock_provider: FakeProvider
) -> None:
    """Turning off the rules shows what the mock itself lets through."""
    subject = mock_provider.mint(aud=["somebody-else"])
    TokenClient(mock_settings, mock_provider).exchange(
        mock_settings.clients["gateway"], subject, apply_rules=False
    )
    assert mock_provider.posts


def test_refusals_of_the_provider(
    ls_settings: Settings, provider: FakeProvider
) -> None:
    """Refusals keep the provider's error, free of tokens."""
    token = provider.mint()
    provider.token_error = FakeResponse(
        400, {"error": "invalid_target", "error_description": f"about {token}"}
    )
    with pytest.raises(Refused) as caught:
        TokenClient(ls_settings, provider).exchange(
            ls_settings.clients["gateway"], token
        )
    view = caught.value.view()
    assert view["refused_by"] == REFUSED_BY_PROVIDER
    assert view["status"] == 400
    assert view["error"] == "invalid_target"
    assert token not in str(view)


@pytest.mark.parametrize("body", [None, ["list"]])
def test_unparseable_refusals(
    ls_settings: Settings, provider: FakeProvider, body: object
) -> None:
    """Responses that aren't JSON objects are refusals, too."""
    provider.token_error = FakeResponse(502, body)
    with pytest.raises(Refused) as caught:
        TokenClient(ls_settings, provider).exchange(
            ls_settings.clients["gateway"], provider.mint()
        )
    assert caught.value.error == "unknown"


def test_token_response_hides_tokens(
    ls_settings: Settings, provider: FakeProvider
) -> None:
    """Neither the representation nor the view of a response holds tokens."""
    issued = TokenClient(ls_settings, provider).client_credentials(
        ls_settings.clients["gateway"], "openid"
    )
    assert issued.access_token not in repr(issued)
    assert str(issued.refresh_token) not in repr(issued)
    view = issued.view()
    assert issued.access_token not in str(view)
    assert str(issued.refresh_token) not in str(view)
    assert view["refresh_token"] == {"present": True, "format": "opaque"}
    assert view["id_token"] == "present"


def test_refresh_sends_the_grant(ls_settings: Settings, provider: FakeProvider) -> None:
    """Refreshing can narrow the audience, resource and scope."""
    TokenClient(ls_settings, provider).refresh(
        ls_settings.clients["orchestrator"],
        "refresh-value",
        audience=["id-gateway"],
        resource=["https://gateway.example/"],
        scope="openid",
    )
    _, form, _ = provider.posts[-1]
    assert form["grant_type"] == "refresh_token"
    assert form["refresh_token"] == "refresh-value"
    assert form["audience"] == ["id-gateway"]
    assert form["resource"] == ["https://gateway.example/"]
    assert form["scope"] == "openid"


def test_userinfo(ls_settings: Settings, provider: FakeProvider) -> None:
    """User info is requested with the token, and refusals are reported."""
    tokens = TokenClient(ls_settings, provider)
    provider.entitlements["user-1"] = ["urn:a"]
    assert tokens.userinfo(provider.mint())["entitlements"] == ["urn:a"]
    base = provider.issuer.rstrip("/")
    provider.routes[f"{base}/userinfo"] = lambda _url, _kw: FakeResponse(401)
    with pytest.raises(Refused):
        tokens.userinfo(provider.mint())
    provider.routes[f"{base}/userinfo"] = lambda _url, _kw: FakeResponse(200, [])
    with pytest.raises(Refused):
        tokens.userinfo(provider.mint())


def test_introspection_and_revocation(
    ls_settings: Settings, provider: FakeProvider
) -> None:
    """Introspection and revocation send the token type hint."""
    tokens = TokenClient(ls_settings, provider)
    client = ls_settings.clients["orchestrator"]
    assert tokens.introspect(client, "value", "refresh_token")["active"]
    assert provider.posts[-1][1]["token_type_hint"] == "refresh_token"
    assert tokens.revoke(client, "value", "refresh_token") == 200
    assert provider.posts[-1][1]["token_type_hint"] == "refresh_token"
    base = provider.issuer.rstrip("/")
    provider.routes[f"{base}/introspect"] = lambda _url, _kw: FakeResponse(401)
    with pytest.raises(Refused):
        tokens.introspect(client, "value")


def test_client_credentials_and_revocation_without_options(
    ls_settings: Settings, provider: FakeProvider
) -> None:
    """Scope and hint are left out if not given."""
    client = ls_settings.clients["node"]
    tokens = TokenClient(ls_settings, provider)
    tokens.client_credentials(client, None)
    assert "scope" not in provider.posts[-1][1]
    assert tokens.revoke(client, "value") == 200
    assert "token_type_hint" not in provider.posts[-1][1]


def test_view_says_when_there_is_no_refresh_token() -> None:
    """A response without a refresh token says so."""
    assert TokenResponse(access_token="opaque").view()["refresh_token"] == "absent"
