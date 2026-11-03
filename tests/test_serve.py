"""Tests of `testbed.serve`."""

from typing import Any

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
    mock_settings: Settings, role: str, forwards: bool
) -> None:
    """Roles with a next hop are gateways; the others are nodes."""
    client = serve.create_service(mock_settings, role).test_client()
    response = client.get("/report", headers={"Authorization": "Bearer nonsense"})
    assert response.status_code == 401
    assert response.get_json()["service"] == role
    assert serve.create_service(mock_settings, role).name == role
    assert (role in ("gateway", "orchestrator")) is forwards


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
