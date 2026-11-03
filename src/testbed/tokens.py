"""Requests to the provider's token, user info and introspection endpoints."""

import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from testbed.redact import scrub, token_view
from testbed.rules import REFUSED_BY_RULE, RuleViolation, check_exchange
from testbed.settings import Client, Settings
from testbed.validation import TIMEOUT, HttpClient, TokenValidator, discover

logger = logging.getLogger(__name__)

GRANT_EXCHANGE = "urn:ietf:params:oauth:grant-type:token-exchange"
TYPE_ACCESS = "urn:ietf:params:oauth:token-type:access_token"
TYPE_REFRESH = "urn:ietf:params:oauth:token-type:refresh_token"
REFUSED_BY_PROVIDER = "provider"
REFUSED_BY_CLIENT = "dummy client"


class Refused(Exception):
    """A request was refused.

    Attributes:
        status: HTTP status; `None` for refusals by the testbed.
        error: OAuth 2.0 error code.
        description: Description, without tokens.
        refused_by: Who refused: the provider, or a testbed rule (mock only).
    """

    def __init__(
        self,
        status: int | None,
        error: str,
        description: str,
        refused_by: str = REFUSED_BY_PROVIDER,
    ) -> None:
        """Create the exception.

        Args:
            status: HTTP status; `None` for refusals by the testbed.
            error: OAuth 2.0 error code.
            description: Description, without tokens.
            refused_by: Who refused.
        """
        super().__init__(f"{error}: {description}")
        self.status = status
        self.error = error
        self.description = scrub(description)
        self.refused_by = refused_by

    def view(self) -> dict[str, Any]:
        """Create a view of the refusal for reports.

        Returns:
            Status, error, description and who refused.
        """
        return {
            "refused_by": self.refused_by,
            "status": self.status,
            "error": self.error,
            "error_description": self.description,
        }


@dataclass(frozen=True)
class TokenResponse:
    """Successful response of a token endpoint. Tokens are not in the `repr`.

    Attributes:
        access_token: Issued token (RFC 8693 uses this field for any type).
        refresh_token: Refresh token, if any.
        id_token: ID token, if any.
        expires_in: Lifetime that the provider states, in seconds.
        scope: Scope that the provider states.
        issued_token_type: Type of the issued token, if stated.
    """

    access_token: str = field(repr=False)
    refresh_token: str | None = field(default=None, repr=False)
    id_token: str | None = field(default=None, repr=False)
    expires_in: int | None = None
    scope: str | None = None
    issued_token_type: str | None = None

    @property
    def is_refresh_token(self) -> bool:
        """Whether the issued token itself is a refresh token.

        Returns:
            True if the provider says so (RFC 8693, section 2.2.1).
        """
        return self.issued_token_type == TYPE_REFRESH

    @property
    def usable_refresh_token(self) -> str | None:
        """Get the refresh token that this response holds, in either field.

        Returns:
            The refresh token, if any.
        """
        if self.refresh_token:
            return self.refresh_token
        return self.access_token if self.is_refresh_token else None

    def view(self) -> dict[str, Any]:
        """Create a view of the response that is safe to show.

        Returns:
            Decoded access token, and what else the response has.
        """
        view: dict[str, Any] = {
            **token_view(self.access_token),
            "expires_in": self.expires_in,
            "scope": self.scope,
            "issued_token_type": self.issued_token_type,
            "id_token": "present" if self.id_token else "absent",
            "refresh_token": "absent",
        }
        if self.usable_refresh_token:
            view["refresh_token"] = {
                "present": True,
                **token_view(self.usable_refresh_token),
            }
        return view


def parse_token_response(response: Any) -> TokenResponse:
    """Parse the response of a token endpoint.

    Args:
        response: HTTP response.

    Returns:
        Parsed response.

    Raises:
        Refused: The provider refused the request.
    """
    try:
        body = response.json()
    except ValueError:
        body = {}
    if not isinstance(body, dict):
        body = {}
    if response.status_code != 200 or "access_token" not in body:
        raise Refused(
            response.status_code,
            str(body.get("error", "unknown")),
            str(body.get("error_description", "")),
        )
    return TokenResponse(
        access_token=body["access_token"],
        refresh_token=body.get("refresh_token"),
        id_token=body.get("id_token"),
        expires_in=body.get("expires_in"),
        scope=body.get("scope"),
        issued_token_type=body.get("issued_token_type"),
    )


class TokenClient:
    """Client of a provider's endpoints."""

    def __init__(
        self, settings: Settings, http: HttpClient, issuer: str | None = None
    ) -> None:
        """Create the client.

        Args:
            settings: Settings.
            http: HTTP client.
            issuer: Issuer; defaults to the provider's.
        """
        self.settings = settings
        self.http = http
        self.issuer = issuer or settings.issuer
        self._document: dict[str, Any] | None = None

    @property
    def document(self) -> dict[str, Any]:
        """Discovery document of the issuer."""
        if self._document is None:
            self._document = discover(self.issuer, self.http)
        return self._document

    def post_form(
        self, client: Client, endpoint: str, form: dict[str, Any], auth: str = "auto"
    ) -> Any:
        """Send a form to an endpoint, authenticated as a client.

        Args:
            client: Client.
            endpoint: Name of the endpoint in the discovery document.
            form: Form parameters.
            auth: `basic`, `post`, `none`, or `auto` for `basic` if the client
                has a secret and `none` otherwise.

        Returns:
            HTTP response.
        """
        data = dict(form)
        kwargs: dict[str, Any] = {}
        method = auth if auth != "auto" else ("basic" if client.secret else "none")
        if method == "basic":
            kwargs["auth"] = (client.client_id, client.secret or "")
        else:
            data["client_id"] = client.client_id
            if method == "post":
                data["client_secret"] = client.secret or ""
        return self.http.post(
            self.document[endpoint],
            data=data,
            timeout=TIMEOUT,
            allow_redirects=False,
            **kwargs,
        )

    def exchange(
        self,
        client: Client,
        subject_token: str,
        audience: Sequence[str] = (),
        resource: Sequence[str] = (),
        scope: str | None = None,
        requested_type: str | None = None,
        auth: str = "auto",
        apply_rules: bool = True,
    ) -> TokenResponse:
        """Exchange a token (RFC 8693).

        Args:
            client: Exchanging client.
            subject_token: Subject token.
            audience: Requested audiences.
            resource: Requested resources (RFC 8707).
            scope: Requested scope.
            requested_type: `requested_token_type`, if any.
            auth: Client authentication method (see `post_form()`).
            apply_rules: With the mock: whether to enforce LS Login's rules.
                `False` shows what the mock itself lets through.

        Returns:
            Issued token.

        Raises:
            Refused: The exchange was refused.
        """
        if self.settings.emulate_ls_login_rules and apply_rules:
            validator = TokenValidator(
                issuers=self.settings.trusted_issuers,
                audience=[client.client_id],
                http=self.http,
                algorithms=self.settings.algorithms,
                token_types=self.settings.token_types,
            )
            try:
                check_exchange(client, subject_token, [*audience, *resource], validator)
            except RuleViolation as exc:
                raise Refused(
                    None, exc.error, exc.description, REFUSED_BY_RULE
                ) from exc
        form: dict[str, Any] = {
            "grant_type": GRANT_EXCHANGE,
            "subject_token": subject_token,
            "subject_token_type": TYPE_ACCESS,
        }
        if audience:
            form["audience"] = list(audience)
        if resource:
            form["resource"] = list(resource)
        if scope:
            form["scope"] = scope
        if requested_type:
            form["requested_token_type"] = requested_type
        response = self.post_form(client, "token_endpoint", form, auth)
        return parse_token_response(response)

    def refresh(
        self,
        client: Client,
        refresh_token: str,
        audience: Sequence[str] = (),
        resource: Sequence[str] = (),
        scope: str | None = None,
    ) -> TokenResponse:
        """Redeem a refresh token.

        Args:
            client: Client that holds the refresh token.
            refresh_token: Refresh token.
            audience: Requested audiences.
            resource: Requested resources.
            scope: Requested scope.

        Returns:
            Issued tokens.

        Raises:
            Refused: The request was refused.
        """
        form: dict[str, Any] = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }
        if audience:
            form["audience"] = list(audience)
        if resource:
            form["resource"] = list(resource)
        if scope:
            form["scope"] = scope
        return parse_token_response(self.post_form(client, "token_endpoint", form))

    def client_credentials(self, client: Client, scope: str | None) -> TokenResponse:
        """Get a token for a client itself.

        Args:
            client: Client.
            scope: Requested scope.

        Returns:
            Issued token.

        Raises:
            Refused: The request was refused.
        """
        form = {"grant_type": "client_credentials"}
        if scope:
            form["scope"] = scope
        return parse_token_response(self.post_form(client, "token_endpoint", form))

    def userinfo(self, token: str) -> dict[str, Any]:
        """Get user info with a token.

        Args:
            token: Access token.

        Returns:
            User info, with nested tokens removed.

        Raises:
            Refused: The provider refused the request.
        """
        response = self.http.get(
            self.document["userinfo_endpoint"],
            headers={"Authorization": f"Bearer {token}"},
            timeout=TIMEOUT,
            allow_redirects=False,
        )
        if response.status_code != 200:
            raise Refused(response.status_code, "userinfo_failed", "")
        body = response.json()
        if not isinstance(body, dict):
            raise Refused(response.status_code, "userinfo_invalid", "")
        result: dict[str, Any] = scrub(body)
        return result

    def introspect(
        self, client: Client, token: str, hint: str | None = None
    ) -> dict[str, Any]:
        """Introspect a token (RFC 7662).

        Args:
            client: Client asking.
            token: Token to introspect.
            hint: `token_type_hint`, if any.

        Returns:
            Introspection response, with nested tokens removed.

        Raises:
            Refused: The provider refused the request.
        """
        form = {"token": token}
        if hint:
            form["token_type_hint"] = hint
        response = self.post_form(client, "introspection_endpoint", form)
        if response.status_code != 200:
            raise Refused(response.status_code, "introspection_failed", "")
        result: dict[str, Any] = scrub(response.json())
        return result

    def revoke(self, client: Client, token: str, hint: str | None = None) -> int:
        """Revoke a token (RFC 7009).

        Args:
            client: Client that holds the token.
            token: Token to revoke.
            hint: `token_type_hint`, if any.

        Returns:
            HTTP status of the response.
        """
        form = {"token": token}
        if hint:
            form["token_type_hint"] = hint
        status: int = self.post_form(client, "revocation_endpoint", form).status_code
        return status
