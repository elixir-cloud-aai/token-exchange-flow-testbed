"""Fixtures: a fake provider that signs real JWTs, without any network."""

import json
import socket
import time
from collections.abc import Callable, Iterator
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from testbed import login
from testbed.redact import unverified_claims
from testbed.settings import LS_LOGIN_ISSUER, MOCK_ISSUER, Settings, load_settings

LS_ENV = {
    "TESTBED_NODE_CLIENT_ID": "id-node",
    "TESTBED_NODE_CLIENT_SECRET": "secret-node",
    "TESTBED_GATEWAY_CLIENT_ID": "id-gateway",
    "TESTBED_GATEWAY_CLIENT_SECRET": "secret-gateway",
    "TESTBED_ORCHESTRATOR_CLIENT_ID": "id-orchestrator",
    "TESTBED_ORCHESTRATOR_CLIENT_SECRET": "secret-orchestrator",
    "TESTBED_CLIENT_CLIENT_ID": "id-client",
    "TESTBED_CLIENT_CLIENT_SECRET": "secret-client",
    "TESTBED_PUBLIC_CLIENT_ID": "id-public",
    "TESTBED_NODE_RESOURCE": "https://node.example/",
    "TESTBED_REQUIRED_ENTITLEMENT": "urn:example:compute",
}
ENTITLEMENT = "urn:example:compute"


@pytest.fixture(scope="module")
def callback_port() -> Iterator[int]:
    """Use a temporary login callback port, leaving running sessions alone.

    Yields:
        Temporary callback port for the test module.
    """
    with socket.socket() as listener:
        listener.bind(("localhost", 0))
        port = listener.getsockname()[1]
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(login, "CALLBACK_PORT", port)
        patch.setattr(login, "REDIRECT_URI", f"http://localhost:{port}/callback")
        yield port


class FakeResponse:
    """Response of the fake provider or a service.

    Attributes:
        status_code: HTTP status.
        headers: Response headers.
    """

    def __init__(
        self,
        status_code: int = 200,
        body: Any = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        """Create the response.

        Args:
            status_code: HTTP status.
            body: JSON body; a `ValueError` on parsing if it's `None`.
            headers: Response headers.
        """
        self.status_code = status_code
        self.headers = headers or {}
        self._body = body

    def json(self) -> Any:
        """Get the body.

        Returns:
            The body.

        Raises:
            ValueError: The response has no JSON body.
        """
        if self._body is None:
            raise ValueError("No JSON")
        return self._body

    def raise_for_status(self) -> None:
        """Raise an exception for error statuses.

        Raises:
            RuntimeError: The status is an error.
        """
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)


class FakeProvider:
    """Identity provider and HTTP client in one.

    Attributes:
        issuer: Issuer of the tokens.
        key: Current signing key.
        posts: Sent forms, with their URLs and options.
        gets: URLs of GET requests, with their options.
        entitlements: User info entitlements by subject.
        routes: Functions that answer URLs by prefix.
        token_error: Response of the token endpoint, if it should fail.
        jwks_hits: How many times the keys were fetched.
    """

    def __init__(self, issuer: str) -> None:
        """Create the provider.

        Args:
            issuer: Issuer of the tokens.
        """
        self.issuer = issuer
        self.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.kid = "key-1"
        self.posts: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
        self.gets: list[tuple[str, dict[str, Any]]] = []
        self.entitlements: dict[str, list[str]] = {}
        self.routes: dict[str, Callable[[str, dict[str, Any]], FakeResponse]] = {}
        self.token_error: FakeResponse | None = None
        self.jwks_hits = 0
        self.discovery_overrides: dict[str, Any] = {}

    def mint(
        self,
        typ: str = "at+jwt",
        kid: str | None = None,
        key: Any = None,
        **claims: Any,
    ) -> str:
        """Sign a token.

        Args:
            typ: `typ` header.
            kid: `kid` header; defaults to the current key's.
            key: Signing key; defaults to the current key.
            **claims: Claims; `None` removes a default claim.

        Returns:
            Signed JWT.
        """
        now = int(time.time())
        payload = {
            "iss": self.issuer,
            "sub": "user-1",
            "aud": "id-node",
            "iat": now,
            "exp": now + 3600,
            **claims,
        }
        payload = {name: value for name, value in payload.items() if value is not None}
        return jwt.encode(
            payload,
            key or self.key,
            algorithm="RS256",
            headers={"typ": typ, "kid": kid or self.kid},
        )

    def _base(self) -> str:
        """Get the base URL of the endpoints.

        Returns:
            Issuer without a trailing slash.
        """
        return self.issuer.rstrip("/")

    def get(self, url: str, **kwargs: Any) -> FakeResponse:
        """Answer a GET request.

        Args:
            url: URL.
            **kwargs: Options of the request.

        Returns:
            Response.
        """
        self.gets.append((url, kwargs))
        for prefix, route in self.routes.items():
            if url.startswith(prefix):
                return route(url, kwargs)
        base = self._base()
        if url == f"{base}/.well-known/openid-configuration":
            return FakeResponse(
                body={
                    "issuer": self.issuer,
                    "jwks_uri": f"{base}/jwks",
                    "token_endpoint": f"{base}/token",
                    "authorization_endpoint": f"{base}/authorize",
                    "userinfo_endpoint": f"{base}/userinfo",
                    "introspection_endpoint": f"{base}/introspect",
                    "revocation_endpoint": f"{base}/revoke",
                    "device_authorization_endpoint": f"{base}/device",
                    **self.discovery_overrides,
                }
            )
        if url == f"{base}/jwks":
            self.jwks_hits += 1
            jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(self.key.public_key()))
            return FakeResponse(
                body={"keys": [{**jwk, "kid": self.kid, "use": "sig", "alg": "RS256"}]}
            )
        if url == f"{base}/userinfo":
            token = kwargs["headers"]["Authorization"].removeprefix("Bearer ")
            subject = unverified_claims(token)["sub"]
            return FakeResponse(
                body={
                    "sub": subject,
                    "entitlements": self.entitlements.get(subject, []),
                }
            )
        return FakeResponse(404)

    def post(self, url: str, **kwargs: Any) -> FakeResponse:
        """Answer a POST request.

        Args:
            url: URL.
            **kwargs: Options of the request.

        Returns:
            Response.
        """
        data = kwargs.get("data", {})
        self.posts.append((url, data, kwargs))
        for prefix, route in self.routes.items():
            if url.startswith(prefix):
                return route(url, kwargs)
        base = self._base()
        if url == f"{base}/token":
            return self._token(data)
        if url == f"{base}/introspect":
            return FakeResponse(body={"active": True, "sub": "user-1"})
        if url == f"{base}/revoke":
            return FakeResponse(200, {})
        return FakeResponse(404)

    def _token(self, data: dict[str, Any]) -> FakeResponse:
        """Answer a request to the token endpoint.

        Args:
            data: Form.

        Returns:
            Response.
        """
        if self.token_error is not None:
            return self.token_error
        audience = data.get("audience") or data.get("resource") or ["id-client"]
        subject = "user-1"
        if "subject_token" in data:
            subject = unverified_claims(data["subject_token"])["sub"]
        return FakeResponse(
            body={
                "access_token": self.mint(aud=audience, sub=subject),
                "refresh_token": "opaque-refresh-token-value",
                "id_token": self.mint(typ="JWT", aud="id-client"),
                "expires_in": 3600,
            }
        )


@pytest.fixture
def ls_settings() -> Settings:
    """Provide settings for LS Login, with made-up clients.

    Returns:
        Settings.
    """
    return load_settings(LS_ENV, "lslogin")


@pytest.fixture
def mock_settings() -> Settings:
    """Provide settings for the mock.

    Returns:
        Settings.
    """
    return load_settings({}, "mock")


@pytest.fixture
def provider() -> FakeProvider:
    """Provide a fake of LS Login.

    Returns:
        Fake provider.
    """
    return FakeProvider(LS_LOGIN_ISSUER)


@pytest.fixture
def mock_provider() -> FakeProvider:
    """Provide a fake of the mock.

    Returns:
        Fake provider.
    """
    return FakeProvider(MOCK_ISSUER)
