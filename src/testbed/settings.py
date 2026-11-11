"""Settings of the testbed, from environment variables.

Client secrets only ever come from the environment. They are excluded from the
representations of all objects, so that they can't end up in logs.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field

MOCK = "mock"
LS_LOGIN = "lslogin"
LS_LOGIN_ISSUER = "https://login.aai.lifescience-ri.eu/oidc/"
MOCK_ISSUER = "http://localhost:18990/testbed"
# Issuer of the mock with tokens that expire after seconds, for expiry tests
MOCK_SHORT_ISSUER = "http://localhost:18990/testbed-short"
# Issuer of the mock that services don't trust
MOCK_ROGUE_ISSUER = "http://localhost:18990/rogue"
MOCK_ENTITLEMENT = "urn:example:testbed:group:compute"
CALLBACK_PORT = 18994
# The mock accepts any secret, see docs/testbed/limits.md
DUMMY_SECRET = "testbed-dummy-secret"
NOT_REGISTERED = "https://not-registered.testbed.invalid/"

ROLES = ("client", "public", "orchestrator", "gateway", "node", "loop")
LS_LOGIN_REQUIRED_ROLES = ("client", "orchestrator", "gateway", "node")
SERVICE_PORTS = {"gateway": 18991, "node": 18992, "orchestrator": 18993, "loop": 18995}
NEXT_HOP = {"orchestrator": "gateway", "gateway": "node", "loop": "loop"}
TARGET_PARAMS = ("audience", "resource", "resource-url", "both")


@dataclass(frozen=True)
class Client:
    """OAuth 2.0 client of a role in the testbed.

    Attributes:
        role: Role in the testbed.
        client_id: Client ID at the provider.
        secret: Client secret; `None` for public clients.
        resource: Resource indicator (URL form) of the service.
        registered: Audiences and resources registered for the client. Mock
            only: LS Login checks its own registration.
    """

    role: str
    client_id: str
    secret: str | None = field(default=None, repr=False)
    resource: str | None = None
    registered: tuple[str, ...] = ()


@dataclass(frozen=True)
class Settings:
    """Settings of the testbed.

    Attributes:
        provider: `mock` or `lslogin`.
        issuer: Issuer of the provider, exactly as in its tokens.
        trusted_issuers: Issuers that services accept tokens from.
        clients: Clients by role.
        algorithms: Accepted signature algorithms.
        token_types: Accepted values of the `typ` header.
        required_entitlement: Entitlement that the node requires, if any.
        target_param: Which parameters services name their next hop with in
            exchanges: `audience`, `resource`, `resource-url` or `both`.
        exchange_scope: `scope` that services request in exchanges, if any.
        callback_bind: Address that the login callback listens on. `localhost`
            on a host; in a container, all interfaces, as its published port
            arrives from outside the container's loopback interface.
    """

    provider: str
    issuer: str
    trusted_issuers: tuple[str, ...]
    clients: dict[str, Client]
    algorithms: tuple[str, ...] = ("RS256",)
    token_types: tuple[str, ...] = ("at+jwt", "application/at+jwt")
    required_entitlement: str | None = None
    target_param: str = "audience"
    exchange_scope: str | None = None
    callback_bind: str = "localhost"

    @property
    def emulate_ls_login_rules(self) -> bool:
        """Whether the testbed itself enforces LS Login's rules; mock only."""
        return self.provider == MOCK

    def service_url(self, role: str) -> str:
        """Get the local URL of a service.

        Args:
            role: Role of the service.

        Returns:
            Base URL of the service.
        """
        return f"http://localhost:{SERVICE_PORTS[role]}"


def _mock_settings(env: Mapping[str, str]) -> Settings:
    """Create settings for the mock provider, with dummy clients.

    Args:
        env: Environment variables.

    Returns:
        Settings. Secrets are dummies, as the mock accepts any secret.
    """
    url = "https://{}.testbed.invalid/".format
    clients = {
        "client": Client(
            "client",
            "tx-client",
            DUMMY_SECRET,
            registered=(
                "tx-gateway",
                url("gateway"),
                "tx-orchestrator",
                url("orchestrator"),
            ),
        ),
        "public": Client(
            "public", "tx-public", None, registered=("tx-gateway", url("gateway"))
        ),
        "orchestrator": Client(
            "orchestrator",
            "tx-orchestrator",
            DUMMY_SECRET,
            url("orchestrator"),
            ("tx-gateway", url("gateway")),
        ),
        "gateway": Client(
            "gateway",
            "tx-gateway",
            DUMMY_SECRET,
            url("gateway"),
            ("tx-node", url("node")),
        ),
        "node": Client("node", "tx-node", DUMMY_SECRET, url("node")),
        "loop": Client("loop", "tx-loop", DUMMY_SECRET, url("loop"), ("tx-loop",)),
    }
    return Settings(
        provider=MOCK,
        issuer=MOCK_ISSUER,
        trusted_issuers=(MOCK_ISSUER, MOCK_SHORT_ISSUER),
        clients=clients,
        required_entitlement=(
            env.get("TESTBED_REQUIRED_ENTITLEMENT", MOCK_ENTITLEMENT) or None
        ),
        target_param=_target_param(env),
        exchange_scope=env.get("TESTBED_EXCHANGE_SCOPE") or None,
        callback_bind=env.get("TESTBED_CALLBACK_BIND") or "localhost",
    )


def _target_param(env: Mapping[str, str]) -> str:
    """Get the setting for how services name their next hop.

    Args:
        env: Environment variables.

    Returns:
        `audience`, `resource` or `both`.

    Raises:
        ValueError: The value is not one of those.
    """
    value = env.get("TESTBED_TARGET_PARAM", "audience")
    if value not in TARGET_PARAMS:
        raise ValueError(f"TESTBED_TARGET_PARAM must be one of {TARGET_PARAMS}")
    return value


def _ls_login_settings(env: Mapping[str, str]) -> Settings:
    """Create settings for LS Login, from the environment.

    Args:
        env: Environment variables.

    Returns:
        Settings.

    Raises:
        ValueError: Required variables are missing. Names only, no values.
    """
    missing = [
        f"TESTBED_{role.upper()}_CLIENT_ID"
        for role in LS_LOGIN_REQUIRED_ROLES
        if not env.get(f"TESTBED_{role.upper()}_CLIENT_ID")
    ]
    if missing:
        raise ValueError(f"Missing environment variables: {', '.join(missing)}")
    issuer = env.get("TESTBED_ISSUER") or LS_LOGIN_ISSUER
    clients = {}
    for role in ROLES:
        prefix = f"TESTBED_{role.upper()}"
        client_id = env.get(f"{prefix}_CLIENT_ID")
        if client_id:
            clients[role] = Client(
                role,
                client_id,
                env.get(f"{prefix}_CLIENT_SECRET") or None,
                env.get(f"{prefix}_RESOURCE") or None,
            )
    target_param = _target_param(env)
    if target_param == "resource-url":
        for role in set(NEXT_HOP.values()) & set(clients):
            if not clients[role].resource:
                raise ValueError(
                    f"TESTBED_TARGET_PARAM=resource-url needs "
                    f"TESTBED_{role.upper()}_RESOURCE"
                )
    return Settings(
        provider=LS_LOGIN,
        issuer=issuer,
        trusted_issuers=(issuer,),
        clients=clients,
        algorithms=tuple(env.get("TESTBED_ALGORITHMS", "RS256").split(",")),
        required_entitlement=env.get("TESTBED_REQUIRED_ENTITLEMENT") or None,
        target_param=target_param,
        exchange_scope=env.get("TESTBED_EXCHANGE_SCOPE") or None,
        callback_bind=env.get("TESTBED_CALLBACK_BIND") or "localhost",
    )


def load_settings(env: Mapping[str, str], provider: str | None = None) -> Settings:
    """Load settings from environment variables.

    Args:
        env: Environment variables.
        provider: Provider; defaults to `TESTBED_PROVIDER`, then to the mock.

    Returns:
        Settings.

    Raises:
        ValueError: The provider is unknown or variables are missing.
    """
    name = provider or env.get("TESTBED_PROVIDER", MOCK)
    if name == MOCK:
        return _mock_settings(env)
    if name == LS_LOGIN:
        return _ls_login_settings(env)
    raise ValueError(f"Unknown provider: {name}")
