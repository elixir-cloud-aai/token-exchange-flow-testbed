"""User login for the dummy client: authorization code with PKCE, or device."""

import base64
import hashlib
import secrets
import threading
import time
import urllib.parse
from collections.abc import Callable, Sequence
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

from testbed.settings import CALLBACK_PORT, Client
from testbed.tokens import (
    REFUSED_BY_CLIENT,
    Refused,
    TokenClient,
    TokenResponse,
    parse_token_response,
)

GRANT_DEVICE = "urn:ietf:params:oauth:grant-type:device_code"
REDIRECT_URI = f"http://localhost:{CALLBACK_PORT}/callback"
PAGE = b"<!doctype html><title>Testbed</title>Done. Back to the terminal."


def pkce_pair() -> tuple[str, str]:
    """Create a PKCE verifier and its S256 challenge.

    Returns:
        Verifier and challenge.
    """
    verifier = secrets.token_urlsafe(48)
    digest = hashlib.sha256(verifier.encode()).digest()
    return verifier, base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


class _CallbackServer(HTTPServer):
    """Receives one redirect from the provider.

    Attributes:
        params: Query parameters of the redirect.
    """

    params: dict[str, list[str]] | None = None


class _CallbackHandler(BaseHTTPRequestHandler):
    """Handles the redirect from the provider."""

    def do_GET(self) -> None:
        """Keep the query parameters of the redirect and answer the browser."""
        assert isinstance(self.server, _CallbackServer)
        query = urllib.parse.urlparse(self.path).query
        self.server.params = urllib.parse.parse_qs(query)
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(PAGE)

    def log_message(self, format: str, *args: Any) -> None:
        """Don't log requests: the URL holds the authorization code.

        Args:
            format: Format string.
            *args: Values.
        """


def code_flow(
    tokens: TokenClient,
    client: Client,
    scope: str,
    resources: Sequence[str],
    browser: Callable[[str], None],
    timeout: float = 300,
) -> TokenResponse:
    """Log in a user with the authorization code flow and PKCE.

    Args:
        tokens: Client of the provider.
        client: The dummy client's registration.
        scope: Requested scope.
        resources: Requested resources (RFC 8707).
        browser: Sends a browser to the authorization URL.
        timeout: How long to wait for the login, in seconds.

    Returns:
        Issued tokens.

    Raises:
        Refused: The provider refused, or the login didn't complete.
    """
    verifier, challenge = pkce_pair()
    state = secrets.token_urlsafe(16)
    query: dict[str, Any] = {
        "client_id": client.client_id,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "scope": scope,
        "state": state,
        "nonce": secrets.token_urlsafe(16),
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    if resources:
        query["resource"] = list(resources)
    encoded = urllib.parse.urlencode(query, doseq=True)
    url = f"{tokens.document['authorization_endpoint']}?{encoded}"

    server = _CallbackServer(
        (tokens.settings.callback_bind, CALLBACK_PORT), _CallbackHandler
    )
    server.timeout = timeout
    try:
        thread = threading.Thread(target=server.handle_request, daemon=True)
        thread.start()
        browser(url)
        thread.join(timeout)
    finally:
        server.server_close()
    params = server.params or {}
    if params.get("state", [None])[0] != state or "code" not in params:
        error = params.get("error", ["login_failed"])[0]
        description = params.get("error_description", ["No valid redirect"])[0]
        raise Refused(None, error, description, REFUSED_BY_CLIENT)
    form: dict[str, Any] = {
        "grant_type": "authorization_code",
        "code": params["code"][0],
        "redirect_uri": REDIRECT_URI,
        "code_verifier": verifier,
    }
    if resources:
        form["resource"] = list(resources)
    return parse_token_response(tokens.post_form(client, "token_endpoint", form))


def device_flow(
    tokens: TokenClient,
    client: Client,
    scope: str,
    show: Callable[[str], None],
    sleep: Callable[[float], None] = time.sleep,
    timeout: float = 600,
) -> TokenResponse:
    """Log in a user with the device flow, which needs no redirect URI.

    Args:
        tokens: Client of the provider.
        client: The dummy client's registration.
        scope: Requested scope.
        show: Shows the user where to log in.
        sleep: Waits for a number of seconds.
        timeout: How long to wait for the login, in seconds.

    Returns:
        Issued tokens.

    Raises:
        Refused: The provider refused, or the login didn't complete.
    """
    if "device_authorization_endpoint" not in tokens.document:
        raise Refused(
            None, "unsupported", "The provider has no device flow", REFUSED_BY_CLIENT
        )
    response = tokens.post_form(
        client, "device_authorization_endpoint", {"scope": scope}
    )
    if response.status_code != 200:
        raise Refused(response.status_code, "device_authorization_failed", "")
    body = response.json()
    show(
        f"Open {body.get('verification_uri_complete', body.get('verification_uri'))}"
        f" and enter or confirm the code {body.get('user_code')}"
    )
    interval = float(body.get("interval", 5))
    waited = 0.0
    while waited < timeout:
        sleep(interval)
        waited += interval
        form = {"grant_type": GRANT_DEVICE, "device_code": body["device_code"]}
        try:
            return parse_token_response(
                tokens.post_form(client, "token_endpoint", form)
            )
        except Refused as exc:
            if exc.error == "slow_down":
                interval += 5
            elif exc.error != "authorization_pending":
                raise
    raise Refused(
        None, "timeout", "The device login didn't complete", REFUSED_BY_CLIENT
    )
