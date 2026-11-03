"""Tests of the node and the gateway."""

from typing import Any

import pytest
import requests
from flask.testing import FlaskClient

from testbed.gateway import create_gateway, targets
from testbed.node import create_node
from testbed.service import _lifetime
from testbed.settings import Settings, load_settings
from tests.conftest import ENTITLEMENT, LS_ENV, FakeProvider, FakeResponse

TRACE = "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"


def _bearer(token: str, **headers: str) -> dict[str, str]:
    """Create the headers of a request.

    Args:
        token: Access token.
        **headers: More headers; `_` stands for `-` in names.

    Returns:
        Headers.
    """
    extra = {name.replace("_", "-"): value for name, value in headers.items()}
    return {"Authorization": f"Bearer {token}", **extra}


@pytest.fixture
def node(ls_settings: Settings, provider: FakeProvider) -> FlaskClient:
    """Provide a client of the node.

    Args:
        ls_settings: Settings.
        provider: Fake provider.

    Returns:
        Test client.
    """
    return create_node(ls_settings, provider).test_client()


@pytest.fixture
def gateway(
    ls_settings: Settings, provider: FakeProvider, node: FlaskClient
) -> FlaskClient:
    """Provide a client of the gateway, with the node as its next hop.

    Args:
        ls_settings: Settings.
        provider: Fake provider.
        node: Test client of the node.

    Returns:
        Test client.
    """

    def to_node(_url: str, options: dict[str, Any]) -> FakeResponse:
        """Pass a request on to the node.

        Args:
            _url: URL.
            options: Options of the request.

        Returns:
            Response of the node.
        """
        response = node.get("/report", headers=options["headers"])
        return FakeResponse(response.status_code, response.get_json())

    provider.routes[ls_settings.service_url("node")] = to_node
    return create_gateway(ls_settings, provider).test_client()


def test_node_reports_what_it_saw(node: FlaskClient, provider: FakeProvider) -> None:
    """The node reports decoded claims, entitlements and the path it can see."""
    provider.entitlements["user-1"] = [ENTITLEMENT]
    token = provider.mint(client_id="id-gateway")
    response = node.get("/report", headers=_bearer(token, traceparent=TRACE))
    assert response.status_code == 200
    report = response.get_json()
    assert report["token"]["claims"]["aud"] == "id-node"
    assert report["subject"] == {"iss": provider.issuer, "sub": "user-1"}
    assert report["chain"] == {
        "act": None,
        "client_id": "id-gateway",
        "visible": False,
    }
    assert report["policy"] == "allowed"
    assert report["trace"] == {"traceparent": TRACE, "origin": "received"}
    assert report["lifetime"] == {"exp_minus_iat": 3600}
    assert token not in response.get_data(as_text=True)
    assert token.rsplit(".", 1)[1] not in response.get_data(as_text=True)


def test_node_shows_act_if_present(node: FlaskClient, provider: FakeProvider) -> None:
    """Should LS Login add `act`, the report shows the chain."""
    provider.entitlements["user-1"] = [ENTITLEMENT]
    act = {"sub": "id-gateway", "act": {"sub": "id-client"}}
    report = node.get("/report", headers=_bearer(provider.mint(act=act))).get_json()
    assert report["chain"]["act"] == act
    assert report["chain"]["visible"] is True


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Authorization": "Basic abc"},
        {"Authorization": "Bearer "},
    ],
)
def test_missing_token_is_401(node: FlaskClient, headers: dict[str, str]) -> None:
    """Requests without a bearer token are refused, with a challenge."""
    response = node.get("/report", headers=headers)
    assert response.status_code == 401
    assert response.get_json()["reason"] == "missing"
    assert response.headers["WWW-Authenticate"].startswith("Bearer")


def test_wrong_audience_at_the_node_is_401(
    node: FlaskClient, provider: FakeProvider
) -> None:
    """A token meant for the gateway is refused by the node."""
    response = node.get("/report", headers=_bearer(provider.mint(aud="id-gateway")))
    assert response.status_code == 401
    assert response.get_json()["reason"] == "audience"


def test_node_accepts_its_resource_indicator(
    node: FlaskClient, provider: FakeProvider
) -> None:
    """The node's URL form counts as its audience, too."""
    provider.entitlements["user-1"] = [ENTITLEMENT]
    token = provider.mint(aud="https://node.example/")
    assert node.get("/report", headers=_bearer(token)).status_code == 200


def test_user_outside_the_group_gets_403(
    node: FlaskClient, provider: FakeProvider
) -> None:
    """Missing the group is 403 with a report, not 401: not locked out."""
    response = node.get("/report", headers=_bearer(provider.mint()))
    assert response.status_code == 403
    body = response.get_json()
    assert body["refused"] == "entitlement"
    assert body["policy"] == "denied"


def test_entitlement_as_a_single_string(
    node: FlaskClient, provider: FakeProvider
) -> None:
    """User info may hold a single entitlement as a string."""
    base = provider.issuer.rstrip("/")
    provider.routes[f"{base}/userinfo"] = lambda _url, _kw: FakeResponse(
        200, {"sub": "user-1", "entitlements": ENTITLEMENT}
    )
    assert node.get("/report", headers=_bearer(provider.mint())).status_code == 200


def test_userinfo_of_another_subject_is_not_used(
    node: FlaskClient, provider: FakeProvider
) -> None:
    """User info must be about the token's subject, as in FOCA."""
    base = provider.issuer.rstrip("/")
    provider.routes[f"{base}/userinfo"] = lambda _url, _kw: FakeResponse(
        200, {"sub": "other", "eduperson_entitlement": [ENTITLEMENT]}
    )
    response = node.get("/report", headers=_bearer(provider.mint()))
    assert response.status_code == 502
    assert "another subject" in response.get_json()["entitlements"]["error"]


@pytest.mark.parametrize("status", [401, 503])
def test_failing_userinfo_is_no_decision(
    node: FlaskClient, provider: FakeProvider, status: int
) -> None:
    """Without user info, nobody knows: not a 403, and the node says why."""
    base = provider.issuer.rstrip("/")
    provider.routes[f"{base}/userinfo"] = lambda _url, _kw: FakeResponse(status)
    response = node.get("/report", headers=_bearer(provider.mint()))
    assert response.status_code == 502
    body = response.get_json()
    assert body["refused"] == "userinfo"
    assert body["policy"] == "unknown"
    assert body["entitlements"]["error"]["status"] == status


def test_unreachable_userinfo_is_no_decision(
    node: FlaskClient, provider: FakeProvider
) -> None:
    """Network problems with user info are no decision, either."""

    def fail(_url: str, _options: dict[str, Any]) -> FakeResponse:
        """Fail like a network problem.

        Args:
            _url: URL.
            _options: Options of the request.

        Raises:
            ConnectionError: Always.
        """
        raise ConnectionError

    provider.routes[f"{provider.issuer.rstrip('/')}/userinfo"] = fail
    response = node.get("/report", headers=_bearer(provider.mint()))
    assert response.status_code == 502
    assert response.get_json()["entitlements"]["error"] == "user info request failed"


def test_policy_is_off_without_a_required_entitlement(provider: FakeProvider) -> None:
    """Without a required entitlement, the node allows any valid token."""
    env = {**LS_ENV, "TESTBED_REQUIRED_ENTITLEMENT": ""}
    client = create_node(load_settings(env, "lslogin"), provider).test_client()
    response = client.get("/report", headers=_bearer(provider.mint()))
    assert response.status_code == 200
    assert response.get_json()["policy"] == "off"


def test_gateway_exchanges_and_forwards(
    gateway: FlaskClient, provider: FakeProvider
) -> None:
    """The gateway passes on an exchanged token, the trace and the hop limit."""
    provider.entitlements["user-1"] = [ENTITLEMENT]
    subject = provider.mint(aud="id-gateway")
    response = gateway.get(
        "/report", headers=_bearer(subject, traceparent=TRACE, Hop_Limit="5")
    )
    assert response.status_code == 200
    report = response.get_json()
    assert report["service"] == "gateway"
    assert report["policy"] == "off"
    assert report["hop_limit"] == 5
    assert report["exchange"]["issued"]["claims"]["aud"] == ["id-node"]
    assert report["next"]["service"] == "node"
    assert report["next"]["hop_limit"] == 4
    assert report["next"]["trace"]["traceparent"] == TRACE
    assert report["next"]["token"]["claims"]["sub"] == "user-1"
    assert subject not in response.get_data(as_text=True)


def test_gateway_passes_on_the_nodes_refusal(
    gateway: FlaskClient, provider: FakeProvider
) -> None:
    """A user outside the group passes the gateway; the node answers 403."""
    response = gateway.get("/report", headers=_bearer(provider.mint(aud="id-gateway")))
    assert response.status_code == 403
    report = response.get_json()
    assert report["policy"] == "off"
    assert report["next"]["refused"] == "entitlement"


def test_gateway_refuses_tokens_for_others(
    gateway: FlaskClient, provider: FakeProvider
) -> None:
    """The gateway validates before it exchanges anything."""
    response = gateway.get("/report", headers=_bearer(provider.mint(aud="id-node")))
    assert response.status_code == 401
    assert not provider.posts


def test_hop_limit_0_stops_the_request(
    gateway: FlaskClient, provider: FakeProvider
) -> None:
    """At limit 0, the gateway neither exchanges nor forwards: 508."""
    token = provider.mint(aud="id-gateway")
    response = gateway.get("/report", headers=_bearer(token, Hop_Limit="0"))
    assert response.status_code == 508
    assert response.get_json()["reason"] == "exceeded"
    assert not provider.posts


def test_invalid_hop_limit_is_400(gateway: FlaskClient, provider: FakeProvider) -> None:
    """Invalid hop limits are refused."""
    token = provider.mint(aud="id-gateway")
    response = gateway.get("/report", headers=_bearer(token, Hop_Limit="many"))
    assert response.status_code == 400


def test_refused_exchange_is_502_with_the_refusal(
    gateway: FlaskClient, provider: FakeProvider
) -> None:
    """The caller learns who refused the exchange and why."""
    provider.token_error = FakeResponse(
        400, {"error": "invalid_target", "error_description": "not registered"}
    )
    response = gateway.get("/report", headers=_bearer(provider.mint(aud="id-gateway")))
    assert response.status_code == 502
    body = response.get_json()
    assert body["exchange"]["refusal"]["error"] == "invalid_target"
    assert body["exchange"]["refusal"]["refused_by"] == "provider"
    assert body["exchange"]["request"]["audience"] == ["id-node"]


def test_unreachable_provider_is_502(
    gateway: FlaskClient, provider: FakeProvider
) -> None:
    """If the provider can't be reached for the exchange, the caller is told."""

    def fail(_url: str, _options: dict[str, Any]) -> FakeResponse:
        """Fail like a network problem.

        Args:
            _url: URL.
            _options: Options of the request.

        Raises:
            requests.ConnectionError: Always.
        """
        raise requests.ConnectionError

    provider.routes[f"{provider.issuer.rstrip('/')}/token"] = fail
    response = gateway.get("/report", headers=_bearer(provider.mint(aud="id-gateway")))
    assert response.status_code == 502
    assert response.get_json()["reason"] == "provider unreachable"


def test_unreachable_next_hop_is_502(
    ls_settings: Settings, provider: FakeProvider
) -> None:
    """A next hop that can't be reached is reported."""
    client = create_gateway(ls_settings, provider).test_client()

    def fail(_url: str, _options: dict[str, Any]) -> FakeResponse:
        """Fail like a network problem.

        Args:
            _url: URL.
            _options: Options of the request.

        Raises:
            ConnectionError: Always.
        """
        raise ConnectionError

    provider.routes[ls_settings.service_url("node")] = fail
    response = client.get("/report", headers=_bearer(provider.mint(aud="id-gateway")))
    assert response.status_code == 502
    assert response.get_json()["reason"] == "unreachable"


def test_orchestrator_is_a_gateway_with_another_role(
    ls_settings: Settings, provider: FakeProvider
) -> None:
    """The orchestrator validates with its own ID and targets the gateway."""
    client = create_gateway(ls_settings, provider, "orchestrator").test_client()
    token = provider.mint(aud="id-orchestrator")
    response = client.get("/report", headers=_bearer(token))
    # The fake has no gateway service to reach
    assert response.status_code == 502
    assert provider.posts[-1][1]["audience"] == ["id-gateway"]


def test_health_needs_no_token(node: FlaskClient) -> None:
    """The health endpoint is open."""
    assert node.get("/healthz").status_code == 200


def test_logs_hold_no_tokens(
    gateway: FlaskClient,
    provider: FakeProvider,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Logs of a whole chain hold no token, signature or secret."""
    caplog.set_level("DEBUG")
    provider.entitlements["user-1"] = [ENTITLEMENT]
    subject = provider.mint(aud="id-gateway")
    gateway.get("/report", headers=_bearer(subject))
    assert '"service": "node"' in caplog.text
    assert '"service": "gateway"' in caplog.text
    assert "eyJ" not in caplog.text
    assert "secret-gateway" not in caplog.text


@pytest.mark.parametrize(
    ("param", "audience", "resource"),
    [
        ("audience", ["id-node"], []),
        ("resource", [], ["id-node"]),
        ("resource-url", [], ["https://node.example/"]),
        ("both", ["id-node"], ["https://node.example/"]),
    ],
)
def test_targets(param: str, audience: list[str], resource: list[str]) -> None:
    """The setting chooses how the next hop is named."""
    settings = load_settings(
        {
            **LS_ENV,
            "TESTBED_GATEWAY_RESOURCE": "https://gateway.example/",
            "TESTBED_ORCHESTRATOR_RESOURCE": "https://orchestrator.example/",
            "TESTBED_TARGET_PARAM": param,
        },
        "lslogin",
    )
    assert targets(settings, settings.clients["node"]) == {
        "audience": audience,
        "resource": resource,
    }


@pytest.mark.parametrize("value", [1, {"a": 1}, ["ok", 1]])
def test_entitlements_of_the_wrong_type_are_an_error(
    node: FlaskClient, provider: FakeProvider, value: Any
) -> None:
    """Odd values in user info are reported, and don't crash the node."""
    base = provider.issuer.rstrip("/")
    provider.routes[f"{base}/userinfo"] = lambda _url, _kw: FakeResponse(
        200, {"sub": "user-1", "eduperson_entitlement": value}
    )
    response = node.get("/report", headers=_bearer(provider.mint(sub="user-1")))
    assert response.status_code == 502
    assert "not a list" in response.get_json()["entitlements"]["error"]


def test_tokens_without_times_have_no_lifetime() -> None:
    """A lifetime is only stated if the claims allow it."""
    assert _lifetime({"exp": 10, "iat": 4}) == {"exp_minus_iat": 6}
    assert _lifetime({"exp": 10}) == {"exp_minus_iat": None}
