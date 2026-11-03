"""proTES-like gateway: validates, exchanges the token per hop and forwards.

With another role, the same code is the Conquest-like orchestrator.
"""

from typing import Any

import requests
from flask import Flask, Response, request

from testbed.hops import HOP_LIMIT_HEADER, TRACEPARENT_HEADER
from testbed.service import (
    RequestContext,
    Service,
    Stop,
    add_health,
    respond,
)
from testbed.settings import NEXT_HOP, Client, Settings
from testbed.tokens import Refused, TokenResponse
from testbed.validation import TIMEOUT, HttpClient, InvalidToken

HTTP_BAD_GATEWAY = 502
HTTP_LOOP_DETECTED = 508


def targets(settings: Settings, next_client: Client) -> dict[str, list[str]]:
    """Get the parameters that name the next hop in an exchange.

    Args:
        settings: Settings.
        next_client: Client of the next hop.

    Returns:
        Arguments `audience` and `resource` for an exchange.
    """
    audience = [next_client.client_id]
    resource = [next_client.resource] if next_client.resource else []
    if settings.target_param == "audience":
        return {"audience": audience, "resource": []}
    if settings.target_param == "resource":
        return {"audience": [], "resource": resource}
    return {"audience": audience, "resource": resource}


def _forward(
    service: Service, role: str, context: RequestContext
) -> tuple[int, dict[str, Any]]:
    """Exchange the token for the next hop and forward the request.

    Args:
        service: The service.
        role: Role of the service.
        context: Checked request.

    Returns:
        HTTP status and body for the caller.
    """
    report = context.report
    if context.hop_limit <= 0:
        return HTTP_LOOP_DETECTED, {
            **report,
            "refused": "hop limit",
            "reason": "exceeded",
        }
    next_role = NEXT_HOP[role]
    next_client = service.settings.clients[next_role]
    target = targets(service.settings, next_client)
    try:
        issued: TokenResponse = service.tokens.exchange(
            service.client,
            context.token,
            audience=target["audience"],
            resource=target["resource"],
            scope=service.settings.exchange_scope,
        )
    except Refused as exc:
        return HTTP_BAD_GATEWAY, {
            **report,
            "refused": "exchange",
            "reason": exc.error,
            "exchange": {"request": target, "refusal": exc.view()},
        }
    except (InvalidToken, requests.RequestException) as exc:
        return HTTP_BAD_GATEWAY, {
            **report,
            "refused": "exchange",
            "reason": "provider unreachable",
            "exchange": {"request": target, "failure": type(exc).__name__},
        }
    report["exchange"] = {"request": target, "issued": issued.view()}
    try:
        response = service.http.get(
            f"{service.settings.service_url(next_role)}/report",
            headers={
                "Authorization": f"Bearer {issued.access_token}",
                HOP_LIMIT_HEADER: str(context.hop_limit - 1),
                TRACEPARENT_HEADER: context.traceparent,
            },
            timeout=TIMEOUT * 4,
            allow_redirects=False,
        )
        next_report = response.json()
    except Exception:
        return HTTP_BAD_GATEWAY, {
            **report,
            "refused": "next hop",
            "reason": "unreachable",
        }
    report["next"] = next_report
    return response.status_code, report


def create_gateway(
    settings: Settings, http: HttpClient, role: str = "gateway"
) -> Flask:
    """Create a gateway.

    Who may use the gateway is not checked beyond the token: each node applies
    its own policy (proTES #391).

    Args:
        settings: Settings.
        http: HTTP client.
        role: Role of the service; has a next hop.

    Returns:
        Flask app.
    """
    app = Flask(role)
    service = Service(settings, role, http, enforce_entitlement=False)
    add_health(app)

    @app.get("/report")
    def report() -> tuple[Response, int]:
        """Validate, exchange, forward and report.

        Returns:
            Report, with the reports of the next hops, and status.
        """
        try:
            context = service.check(request.headers)
        except Stop as stop:
            return respond(role, stop.status, stop.body)
        status, body = _forward(service, role, context)
        return respond(role, status, body)

    return app
