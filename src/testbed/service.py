"""What gateways and nodes have in common: checks and reports of a request."""

import json
import logging
from dataclasses import dataclass
from typing import Any

from flask import Flask, Response, jsonify

from testbed.hops import (
    HOP_LIMIT_HEADER,
    TRACEPARENT_HEADER,
    parse_hop_limit,
    resolve_traceparent,
)
from testbed.redact import scrub, token_view
from testbed.settings import Client, Settings
from testbed.tokens import Refused, TokenClient
from testbed.validation import HttpClient, InvalidToken, TokenValidator

logger = logging.getLogger(__name__)
HTTP_OK = 200
HTTP_BAD_REQUEST = 400
HTTP_UNAUTHORIZED = 401
HTTP_FORBIDDEN = 403
HTTP_BAD_GATEWAY = 502


@dataclass
class RequestContext:
    """A request that passed the checks.

    Attributes:
        token: Validated access token.
        claims: Verified claims of the token.
        hop_limit: Hop limit, as received or the default.
        traceparent: Trace context to pass on.
        report: Report of the service, for the caller.
    """

    token: str
    claims: dict[str, Any]
    hop_limit: int
    traceparent: str
    report: dict[str, Any]


class Stop(Exception):
    """Handling a request ends here, with this response.

    Attributes:
        status: HTTP status.
        body: Response body.
    """

    def __init__(self, status: int, body: dict[str, Any]) -> None:
        """Create the exception.

        Args:
            status: HTTP status.
            body: Response body.
        """
        super().__init__(status)
        self.status = status
        self.body = body


class Service:
    """Checks incoming requests of one service.

    Attributes:
        settings: Settings.
        client: The service's own client.
        tokens: Client of the provider.
        http: HTTP client.
        enforce_entitlement: Whether the service requires the entitlement.
    """

    def __init__(
        self,
        settings: Settings,
        role: str,
        http: HttpClient,
        enforce_entitlement: bool,
    ) -> None:
        """Create the service.

        Args:
            settings: Settings.
            role: Role of the service.
            http: HTTP client.
            enforce_entitlement: Whether the service requires the entitlement.
        """
        self.settings = settings
        self.client: Client = settings.clients[role]
        self.tokens = TokenClient(settings, http)
        self.http = http
        self.enforce_entitlement = enforce_entitlement
        audience = [self.client.client_id]
        if self.client.resource:
            audience.append(self.client.resource)
        self._validator = TokenValidator(
            issuers=settings.trusted_issuers,
            audience=audience,
            http=http,
            algorithms=settings.algorithms,
            token_types=settings.token_types,
        )

    def _entitlements(self, token: str, claims: dict[str, Any]) -> dict[str, Any]:
        """Get the user's entitlements from user info, as computed for this token.

        Args:
            token: Validated access token.
            claims: Verified claims of the token.

        Returns:
            Entitlements, or the reason why there are none to show.
        """
        try:
            userinfo = self.tokens.userinfo(token)
        except Refused as exc:
            return {"values": [], "error": exc.view()}
        except Exception:
            logger.exception("User info request failed")
            return {"values": [], "error": "user info request failed"}
        if userinfo.get("sub") != claims.get("sub"):
            return {"values": [], "error": "user info is about another subject"}
        found = userinfo.get("entitlements", [])
        found = [found] if isinstance(found, str) else found
        if not isinstance(found, list) or not all(
            isinstance(item, str) for item in found
        ):
            return {"values": [], "error": "entitlements is not a list of strings"}
        return {"values": found}

    def check(self, headers: Any) -> RequestContext:
        """Check an incoming request.

        Args:
            headers: Request headers.

        Returns:
            Context of the request.

        Raises:
            Stop: The request is refused.
        """
        service = self.client.role
        authorization = headers.get("Authorization", "")
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise Stop(
                HTTP_UNAUTHORIZED,
                {"service": service, "refused": "token", "reason": "missing"},
            )
        try:
            claims = self._validator.validate(token.strip())
        except InvalidToken as exc:
            raise Stop(
                HTTP_UNAUTHORIZED,
                {
                    "service": service,
                    "refused": "token",
                    "reason": exc.reason,
                    "detail": exc.detail,
                },
            ) from exc
        hop_limit = parse_hop_limit(headers.get(HOP_LIMIT_HEADER))
        if hop_limit is None:
            raise Stop(
                HTTP_BAD_REQUEST,
                {"service": service, "refused": "hop limit", "reason": "invalid"},
            )
        traceparent, origin = resolve_traceparent(headers.get(TRACEPARENT_HEADER))
        report: dict[str, Any] = {
            "service": service,
            "token": token_view(token.strip()),
            "subject": {"iss": claims.get("iss"), "sub": claims.get("sub")},
            "chain": {
                "act": scrub(claims.get("act")),
                "client_id": claims.get("client_id"),
                "visible": "act" in claims,
            },
            "entitlements": self._entitlements(token.strip(), claims),
            "hop_limit": hop_limit,
            "trace": {"traceparent": traceparent, "origin": origin},
            "lifetime": _lifetime(claims),
        }
        self._apply_policy(report)
        return RequestContext(token.strip(), claims, hop_limit, traceparent, report)

    def _apply_policy(self, report: dict[str, Any]) -> None:
        """Apply the service's entitlement policy to a request.

        A user without the entitlement is told so (403) rather than treated as
        unauthenticated (401), so that portals can offer a way to get access. If
        user info gave no answer, nobody knows, so that isn't a 403 (502).

        Args:
            report: Report of the service, updated with the decision.

        Raises:
            Stop: The user lacks the entitlement, or it could not be determined.
        """
        required = self.settings.required_entitlement
        if not self.enforce_entitlement or required is None:
            report["policy"] = "off"
            return
        if required in report["entitlements"]["values"]:
            report["policy"] = "allowed"
            return
        if "error" in report["entitlements"]:
            report["policy"] = "unknown"
            raise Stop(HTTP_BAD_GATEWAY, {**report, "refused": "userinfo"})
        report["policy"] = "denied"
        raise Stop(HTTP_FORBIDDEN, {**report, "refused": "entitlement"})


def _lifetime(claims: dict[str, Any]) -> dict[str, Any]:
    """Get the stated lifetime of a token.

    Args:
        claims: Verified claims.

    Returns:
        `exp` minus `iat`, in seconds.
    """
    exp, iat = claims.get("exp"), claims.get("iat")
    if isinstance(exp, int) and isinstance(iat, int):
        return {"exp_minus_iat": exp - iat}
    return {"exp_minus_iat": None}


def log_outcome(service: str, status: int, body: dict[str, Any]) -> None:
    """Log the outcome of a request: decoded claims only, never tokens.

    Args:
        service: Name of the service.
        status: HTTP status of the response.
        body: Response body.
    """
    claims = body.get("token", {}).get("claims", {})
    summary = {
        "service": service,
        "status": status,
        "reason": body.get("reason") or body.get("refused"),
        "sub": claims.get("sub"),
        "aud": claims.get("aud"),
        "client_id": claims.get("client_id"),
        "act": claims.get("act"),
        "traceparent": body.get("trace", {}).get("traceparent"),
        "hop_limit": body.get("hop_limit"),
    }
    # Scrubbed and without credentials, see above
    logger.info("%s", json.dumps(scrub(summary)))


def respond(service: str, status: int, body: dict[str, Any]) -> tuple[Response, int]:
    """Log the outcome of a request and create the response.

    Args:
        service: Name of the service.
        status: HTTP status.
        body: Response body.

    Returns:
        Response and status for Flask.
    """
    log_outcome(service, status, body)
    response = jsonify(scrub(body))
    if status == HTTP_UNAUTHORIZED:
        response.headers["WWW-Authenticate"] = 'Bearer error="invalid_token"'
    return response, status


def add_health(app: Flask) -> None:
    """Add a health endpoint to an app.

    Args:
        app: Flask app.
    """

    @app.get("/healthz")
    def healthz() -> tuple[Response, int]:
        """Report that the service is up.

        Returns:
            Empty report and status.
        """
        return jsonify(status="ok"), HTTP_OK
