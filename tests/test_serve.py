"""Tests of `testbed.serve`."""

from dataclasses import replace
from typing import Any, cast

import pytest

from testbed import serve
from testbed.settings import SERVICE_PORTS, Settings


def test_http_client_ignores_proxies_for_the_mock_only(
    mock_settings: Settings, ls_settings: Settings
) -> None:
    """The mock is local, whereas LS Login may need a proxy."""
    assert serve.create_http(mock_settings).trust_env is False  # type: ignore[attr-defined]
    assert serve.create_http(ls_settings).trust_env is True  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    ("role", "forwards"), [("gateway", True), ("orchestrator", True), ("node", False)]
)
def test_create_service_by_role(
    mock_settings: Settings,
    role: str,
    forwards: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Roles with a next hop are gateways; the others are nodes."""
    client = serve.create_service(mock_settings, role).test_client()
    response = client.get("/report", headers={"Authorization": "Bearer nonsense"})
    assert response.status_code == 401
    assert response.get_json()["service"] == role
    monkeypatch.setattr(serve, "create_gateway", lambda *_args, **_kw: "gateway")
    monkeypatch.setattr(serve, "create_node", lambda *_args, **_kw: "node")
    expected = "gateway" if forwards else "node"
    created: Any = serve.create_service(mock_settings, role)
    assert created == expected


def test_main_serves_the_role_on_its_port(monkeypatch: pytest.MonkeyPatch) -> None:
    """The role comes from the command line, the port from the settings."""
    calls: list[tuple[str, int]] = []

    class FakeServer:
        """Stands in for a Werkzeug server."""

        def serve_forever(self) -> None:
            """Return at once."""

    def make_server(host: str, port: int, _app: Any, **_options: Any) -> FakeServer:
        """Record the address of the server.

        Args:
            host: Address.
            port: Port.
            _app: App.
            **_options: Options.

        Returns:
            Fake server.
        """
        calls.append((host, port))
        return FakeServer()

    monkeypatch.setattr(serve, "make_server", make_server)
    monkeypatch.setattr("sys.argv", ["serve", "node"])
    monkeypatch.delenv("TESTBED_PROVIDER", raising=False)
    serve.main()
    assert calls == [("localhost", SERVICE_PORTS["node"])]


def test_tokens_for_this_machine_never_go_through_a_proxy(
    mock_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Proxy settings apply to the provider, not to the local services."""
    monkeypatch.setenv("https_proxy", "http://proxy.example:3128")
    monkeypatch.setenv("http_proxy", "http://proxy.example:3128")
    monkeypatch.delenv("no_proxy", raising=False)
    monkeypatch.delenv("NO_PROXY", raising=False)
    http = serve.create_http(replace(mock_settings, provider="lslogin"))

    def proxies(url: Any) -> Any:
        """Get the proxies that a request would use.

        Args:
            url: URL of the request.

        Returns:
            Proxies.
        """
        merge = cast(Any, http).merge_environment_settings
        return merge(url, {}, None, None, None)["proxies"]

    assert proxies("http://localhost:18991/report") == {}
    assert proxies("https://provider.example/token")["https"].endswith(":3128")
    assert proxies(b"http://localhost:18991/report")["http"].endswith(":3128")
