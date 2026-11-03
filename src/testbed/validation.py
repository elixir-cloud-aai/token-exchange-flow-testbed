"""Validation of access tokens, the way FOCA does it.

Mirrors `foca.security.auth._validate()` with FOCA's defaults (checked against
FOCA 0.19.0): trusted issuer first, then the `typ` header, then OpenID Connect
discovery, signature, `exp`, `iat`, `iss`, `sub` and `aud`, only `RS256`. Unlike
FOCA, the reason for a refusal is reported to the caller, as this is a testbed.
"""

import logging
from collections.abc import Sequence
from typing import Any, Protocol

import jwt

from testbed.redact import scrub, unverified_claims

logger = logging.getLogger(__name__)
TIMEOUT = 10


class HttpClient(Protocol):
    """The part of `requests.Session` that the testbed uses."""

    def get(self, url: str, **kwargs: Any) -> Any:
        """Send a GET request.

        Args:
            url: URL.
            **kwargs: Options of the request.

        Returns:
            Response.
        """

    def post(self, url: str, **kwargs: Any) -> Any:
        """Send a POST request.

        Args:
            url: URL.
            **kwargs: Options of the request.

        Returns:
            Response.
        """


class InvalidToken(Exception):
    """A token was refused.

    Attributes:
        reason: One of `malformed`, `issuer`, `type`, `provider`, `key`,
            `signature`, `expired`, `audience`, `claims`.
        detail: Description, without the token.
    """

    def __init__(self, reason: str, detail: str = "") -> None:
        """Create the exception.

        Args:
            reason: Reason for the refusal.
            detail: Description, without the token.
        """
        super().__init__(f"{reason}: {detail}")
        self.reason = reason
        self.detail = scrub(detail)


def discover(issuer: str, http: HttpClient) -> dict[str, Any]:
    """Fetch and check the discovery document of an issuer.

    Args:
        issuer: Issuer, exactly as in its tokens.
        http: HTTP client.

    Returns:
        Discovery document.

    Raises:
        InvalidToken: The document can't be fetched or is for another issuer.
    """
    url = f"{issuer.rstrip('/')}/.well-known/openid-configuration"
    try:
        response = http.get(url, timeout=TIMEOUT, allow_redirects=False)
        response.raise_for_status()
        document = response.json()
    except Exception as exc:
        raise InvalidToken("provider", f"Discovery failed: {url}") from exc
    if not isinstance(document, dict) or document.get("issuer") != issuer:
        raise InvalidToken("provider", f"Discovery document is not for {issuer}")
    return document


class TokenValidator:
    """Validates access tokens for one service.

    Attributes:
        audience: Accepted audiences.
    """

    def __init__(
        self,
        issuers: Sequence[str],
        audience: Sequence[str],
        http: HttpClient,
        algorithms: Sequence[str] = ("RS256",),
        token_types: Sequence[str] = ("at+jwt", "application/at+jwt"),
    ) -> None:
        """Create the validator.

        Args:
            issuers: Trusted issuers.
            audience: Accepted audiences.
            http: HTTP client.
            algorithms: Accepted signature algorithms.
            token_types: Accepted values of the `typ` header.
        """
        self.audience = list(audience)
        self._issuers = set(issuers)
        self._http = http
        self._algorithms = list(algorithms)
        self._token_types = {typ.lower() for typ in token_types}
        self._jwks_uris: dict[str, str] = {}
        self._jwk_sets: dict[str, jwt.PyJWKSet] = {}

    def validate(self, token: str) -> dict[str, Any]:
        """Validate a token.

        Args:
            token: Access token.

        Returns:
            Verified claims.

        Raises:
            InvalidToken: The token is refused.
        """
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError as exc:
            raise InvalidToken("malformed", "Not a JWT") from exc
        # Only to choose the issuer's keys; verified below
        unverified = unverified_claims(token)
        issuer = unverified.get("iss")
        if not isinstance(issuer, str) or issuer not in self._issuers:
            raise InvalidToken("issuer", f"Issuer is not trusted: {issuer}")
        token_type = header.get("typ")
        if (
            not isinstance(token_type, str)
            or token_type.lower() not in self._token_types
        ):
            raise InvalidToken("type", f"Token type is not accepted: {token_type}")
        return self._verify(token, issuer, header.get("kid"))

    def _keys(self, issuer: str, key_id: Any) -> list[jwt.PyJWK]:
        """Get the signing keys for a token, fetching the keys again if unknown.

        Args:
            issuer: Trusted issuer of the token.
            key_id: `kid` header of the token.

        Returns:
            Matching signing keys.

        Raises:
            InvalidToken: The keys can't be fetched or none matches.
        """
        for refetch in (False, True):
            if refetch or issuer not in self._jwk_sets:
                self._jwk_sets[issuer] = self._fetch_keys(issuer)
            keys = [
                key
                for key in self._jwk_sets[issuer].keys
                if key.public_key_use in (None, "sig")
                and (key_id is None or key.key_id == key_id)
            ]
            if keys:
                return keys
        raise InvalidToken("key", "Signing key is not among the issuer's keys")

    def _fetch_keys(self, issuer: str) -> jwt.PyJWKSet:
        """Fetch the keys of an issuer.

        Args:
            issuer: Trusted issuer.

        Returns:
            Keys of the issuer.

        Raises:
            InvalidToken: The keys can't be fetched.
        """
        if issuer not in self._jwks_uris:
            jwks_uri = discover(issuer, self._http).get("jwks_uri")
            if not isinstance(jwks_uri, str):
                raise InvalidToken("provider", "Discovery document has no JWKS URI")
            self._jwks_uris[issuer] = jwks_uri
        try:
            response = self._http.get(
                self._jwks_uris[issuer], timeout=TIMEOUT, allow_redirects=False
            )
            response.raise_for_status()
            return jwt.PyJWKSet.from_dict(response.json())
        except Exception as exc:
            raise InvalidToken("provider", "Could not fetch the JWKS") from exc

    def _verify(self, token: str, issuer: str, key_id: Any) -> dict[str, Any]:
        """Verify signature and claims of a token.

        Args:
            token: Access token.
            issuer: Trusted issuer of the token.
            key_id: `kid` header of the token.

        Returns:
            Verified claims.

        Raises:
            InvalidToken: The token is refused.
        """
        for key in self._keys(issuer, key_id):
            try:
                claims: dict[str, Any] = jwt.decode(
                    token,
                    key=key,
                    algorithms=self._algorithms,
                    audience=self.audience,
                    issuer=issuer,
                    options={"require": ["exp", "iat", "iss", "sub"]},
                )
            except (
                jwt.InvalidSignatureError,
                jwt.InvalidAlgorithmError,
                jwt.InvalidKeyError,
            ):
                continue
            except jwt.ExpiredSignatureError as exc:
                raise InvalidToken("expired", "Token has expired") from exc
            except (jwt.InvalidAudienceError, jwt.MissingRequiredClaimError) as exc:
                if (
                    isinstance(exc, jwt.MissingRequiredClaimError)
                    and exc.claim != "aud"
                ):
                    raise InvalidToken("claims", str(exc)) from exc
                # The signature is verified by now; only for the message
                aud = unverified_claims(token).get("aud")
                raise InvalidToken(
                    "audience", f"Audience {aud} is not one of {self.audience}"
                ) from exc
            except jwt.PyJWTError as exc:
                raise InvalidToken("claims", str(exc)) from exc
            return claims
        raise InvalidToken("signature", "Signature could not be verified")
