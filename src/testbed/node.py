"""TES-like node: validates tokens and reports what it saw. Forwards nothing."""

from flask import Flask, Response, request

from testbed.service import (
    HTTP_OK,
    Service,
    Stop,
    add_health,
    respond,
)
from testbed.settings import Settings
from testbed.validation import HttpClient


def create_node(settings: Settings, http: HttpClient, role: str = "node") -> Flask:
    """Create the node.

    The node requires the entitlement, if one is configured: each node applies
    its own policy (proTES #391).

    Args:
        settings: Settings.
        http: HTTP client.
        role: Role of the service.

    Returns:
        Flask app.
    """
    app = Flask(role)
    service = Service(settings, role, http, enforce_entitlement=True)
    add_health(app)

    @app.get("/report")
    def report() -> tuple[Response, int]:
        """Report the validated token.

        Returns:
            Report and status.
        """
        try:
            context = service.check(request.headers)
        except Stop as stop:
            return respond(role, stop.status, stop.body)
        return respond(role, HTTP_OK, context.report)

    return app
