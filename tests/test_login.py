"""Tests of `testbed.login`."""

import base64
import hashlib
import urllib.parse
from dataclasses import replace
from typing import Any

import pytest
import requests

from testbed import login
from testbed.login import code_flow, device_flow, pkce_pair
from testbed.settings import Settings
from testbed.tokens import Refused, TokenClient
from tests.conftest import FakeProvider, FakeResponse

pytestmark = pytest.mark.usefixtures("callback_port")


def _no_proxy_get(url: str) -> None:
    """Follow a redirect to the local callback, like a browser.

    Args:
        url: URL.
    """
    session = requests.Session()
    session.trust_env = False
    session.get(url, timeout=5)


def _browser_returning(**params: str) -> Any:
    """Create a browser stand-in that returns to the callback.

    Args:
        **params: Query parameters of the redirect; `state` is taken from the
            authorization URL if not given.

    Returns:
        Function to pass as the browser.
    """

    def browse(url: str) -> None:
        """Return to the callback.

        Args:
            url: Authorization URL.
        """
        query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        values = {"state": query["state"][0], **params}
        _no_proxy_get(f"{login.REDIRECT_URI}?{urllib.parse.urlencode(values)}")

    return browse


def test_pkce_pair() -> None:
    """The challenge is the S256 hash of the verifier."""
    verifier, challenge = pkce_pair()
    digest = hashlib.sha256(verifier.encode()).digest()
    assert challenge == base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def test_code_flow(ls_settings: Settings, provider: FakeProvider) -> None:
    """The code is redeemed with the verifier and the resources."""
    seen: dict[str, list[str]] = {}

    def browse(url: str) -> None:
        """Keep the query of the authorization URL and return to the callback.

        Args:
            url: Authorization URL.
        """
        seen.update(urllib.parse.parse_qs(urllib.parse.urlparse(url).query))
        _browser_returning(code="the-code")(url)

    issued = code_flow(
        TokenClient(ls_settings, provider),
        ls_settings.clients["client"],
        "openid",
        ["https://gateway.example/"],
        browse,
        timeout=5,
    )
    assert issued.access_token
    assert seen["code_challenge_method"] == ["S256"]
    assert seen["resource"] == ["https://gateway.example/"]
    _, form, _ = provider.posts[-1]
    assert form["code"] == "the-code"
    assert form["resource"] == ["https://gateway.example/"]
    digest = hashlib.sha256(form["code_verifier"].encode()).digest()
    expected = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    assert seen["code_challenge"] == [expected]


def test_wrong_state_is_refused(ls_settings: Settings, provider: FakeProvider) -> None:
    """A redirect with another state isn't accepted."""
    with pytest.raises(Refused):
        code_flow(
            TokenClient(ls_settings, provider),
            ls_settings.clients["client"],
            "openid",
            [],
            _browser_returning(code="the-code", state="other"),
            timeout=5,
        )
    assert not provider.posts


def test_error_redirect_is_reported(
    ls_settings: Settings, provider: FakeProvider
) -> None:
    """Errors from the provider's redirect are passed on."""
    with pytest.raises(Refused) as caught:
        code_flow(
            TokenClient(ls_settings, provider),
            ls_settings.clients["client"],
            "openid",
            [],
            _browser_returning(error="access_denied", error_description="No group"),
            timeout=5,
        )
    assert caught.value.error == "access_denied"


def _device_provider(provider: FakeProvider, responses: list[FakeResponse]) -> None:
    """Make the fake provider answer the device flow.

    Args:
        provider: Fake provider.
        responses: Responses of the token endpoint, in order.
    """
    base = provider.issuer.rstrip("/")
    provider.routes[f"{base}/device"] = lambda _url, _kw: FakeResponse(
        200,
        {
            "device_code": "device-code-value",
            "user_code": "ABCD",
            "verification_uri": "https://login.example/device",
            "interval": 1,
        },
    )
    provider.routes[f"{base}/token"] = lambda _url, _kw: responses.pop(0)


def test_device_flow_polls_until_the_login_is_done(
    ls_settings: Settings, provider: FakeProvider
) -> None:
    """Pending answers are polled through; `slow_down` slows the polling."""
    token = provider.mint()
    _device_provider(
        provider,
        [
            FakeResponse(400, {"error": "authorization_pending"}),
            FakeResponse(400, {"error": "slow_down"}),
            FakeResponse(200, {"access_token": token}),
        ],
    )
    waits: list[float] = []
    shown: list[str] = []
    issued = device_flow(
        TokenClient(ls_settings, provider),
        ls_settings.clients["client"],
        "openid",
        shown.append,
        waits.append,
    )
    assert issued.access_token == token
    assert waits == [1.0, 1.0, 6.0]
    assert "ABCD" in shown[0]
    assert "device-code-value" not in shown[0]


def test_device_flow_stops_on_refusal(
    ls_settings: Settings, provider: FakeProvider
) -> None:
    """Other errors end the login."""
    _device_provider(provider, [FakeResponse(400, {"error": "access_denied"})])
    with pytest.raises(Refused):
        device_flow(
            TokenClient(ls_settings, provider),
            ls_settings.clients["client"],
            "openid",
            print,
            lambda _seconds: None,
        )


def test_device_flow_times_out(ls_settings: Settings, provider: FakeProvider) -> None:
    """A login that never completes ends in a timeout."""
    _device_provider(
        provider, [FakeResponse(400, {"error": "authorization_pending"})] * 3
    )
    with pytest.raises(Refused) as caught:
        device_flow(
            TokenClient(ls_settings, provider),
            ls_settings.clients["client"],
            "openid",
            print,
            lambda _seconds: None,
            timeout=3,
        )
    assert caught.value.error == "timeout"


def test_device_flow_needs_support(
    ls_settings: Settings, provider: FakeProvider
) -> None:
    """Providers without a device flow are reported, e.g., the mock."""
    provider.discovery_overrides = {"device_authorization_endpoint": None}
    tokens = TokenClient(ls_settings, provider)
    del tokens.document["device_authorization_endpoint"]
    with pytest.raises(Refused) as caught:
        device_flow(
            tokens, ls_settings.clients["client"], "openid", print, lambda _s: None
        )
    assert caught.value.error == "unsupported"


def test_device_authorization_refused(
    ls_settings: Settings, provider: FakeProvider
) -> None:
    """A refused device authorization is reported."""
    base = provider.issuer.rstrip("/")
    provider.routes[f"{base}/device"] = lambda _url, _kw: FakeResponse(400, {})
    with pytest.raises(Refused):
        device_flow(
            TokenClient(ls_settings, provider),
            ls_settings.clients["client"],
            "openid",
            print,
            lambda _s: None,
        )


def test_code_flow_without_resources(
    ls_settings: Settings, provider: FakeProvider
) -> None:
    """Without resources, neither the redirect nor the token request names any."""
    urls: list[str] = []

    def browse(url: str) -> None:
        """Record the URL and return to the callback.

        Args:
            url: Authorization URL.
        """
        urls.append(url)
        _browser_returning(code="the-code")(url)

    code_flow(
        TokenClient(ls_settings, provider),
        ls_settings.clients["client"],
        "openid",
        [],
        browse,
    )
    assert "resource" not in urls[0]
    assert "resource" not in provider.posts[-1][1]


def test_callback_listens_on_the_configured_address(
    ls_settings: Settings,
    provider: FakeProvider,
    monkeypatch: pytest.MonkeyPatch,
    callback_port: int,
) -> None:
    """The address of the callback comes from the settings; the URI stays."""
    addresses: list[tuple[str, int]] = []

    class Recording(login._CallbackServer):
        """Records the address, and listens on the loopback interface."""

        def __init__(self, address: tuple[str, int], handler: Any) -> None:
            """Create the server.

            Args:
                address: Requested address.
                handler: Request handler.
            """
            addresses.append(address)
            super().__init__(("localhost", address[1]), handler)

    monkeypatch.setattr(login, "_CallbackServer", Recording)
    settings = replace(ls_settings, callback_bind="192.0.2.1")
    tokens = TokenClient(settings, provider)
    code_flow(
        tokens,
        settings.clients["client"],
        "openid",
        [],
        _browser_returning(code="the-code"),
    )
    assert addresses == [("192.0.2.1", callback_port)]
    assert "localhost" in provider.posts[-1][1]["redirect_uri"]
