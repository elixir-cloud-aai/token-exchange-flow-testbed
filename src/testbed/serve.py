"""Run one service: `python -m testbed.serve <role>`."""

import logging
import os
import sys
from collections.abc import MutableMapping
from typing import Any, cast
from urllib.parse import urlsplit

import requests
from flask import Flask
from werkzeug.serving import make_server

from testbed.gateway import create_gateway
from testbed.node import create_node
from testbed.settings import MOCK, NEXT_HOP, SERVICE_PORTS, Settings, load_settings
from testbed.validation import HttpClient


class _DirectToLocalhost(requests.Session):
    """HTTP client that never sends requests for this machine through a proxy.

    Calls between the services and the session carry bearer tokens in cleartext,
    on the loopback interface. Proxy settings still apply to the provider.
    """

    def merge_environment_settings(
        self,
        url: str | bytes | None,
        proxies: MutableMapping[str, str] | None,
        stream: bool | None,
        verify: bool | str | None,
        cert: str | tuple[str, str] | None,
    ) -> Any:
        """Add the settings from the environment, except for local URLs.

        Args:
            url: URL of the request.
            proxies: Proxies of the request.
            stream: Whether the response is streamed.
            verify: How TLS certificates are verified.
            cert: Client certificate.

        Returns:
            Settings of the request.
        """
        merged: Any = super().merge_environment_settings(
            url, proxies, stream, verify, cert
        )
        if isinstance(url, str) and urlsplit(url).hostname == "localhost":
            merged["proxies"] = {}
        return merged


def create_http(settings: Settings) -> HttpClient:
    """Create the HTTP client of the testbed.

    Args:
        settings: Settings.

    Returns:
        HTTP client; ignores proxy settings for the mock, which is local.
    """
    http = _DirectToLocalhost()
    http.trust_env = settings.provider != MOCK
    return cast(HttpClient, http)


def create_service(settings: Settings, role: str) -> Flask:
    """Create the service of a role.

    Args:
        settings: Settings.
        role: Role of the service.

    Returns:
        Flask app.
    """
    http = create_http(settings)
    if role in NEXT_HOP:
        return create_gateway(settings, http, role)
    return create_node(settings, http, role)


def main() -> None:
    """Run the service named on the command line."""
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(name)s %(message)s", stream=sys.stdout
    )
    # Our own log line per request says more; access logs would only add noise
    logging.getLogger("werkzeug").setLevel(logging.WARNING)
    role = sys.argv[1]
    settings = load_settings(os.environ)
    app = create_service(settings, role)
    make_server("localhost", SERVICE_PORTS[role], app, threaded=True).serve_forever()


if __name__ == "__main__":
    main()
