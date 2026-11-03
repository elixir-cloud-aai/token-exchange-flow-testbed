"""Interactive session of the dummy client: `testbed-session --provider <name>`.

Tokens exist only in memory and only for the length of the session. Everything
shown or recorded is decoded claims, never a token or secret.
"""

import argparse
import json
import os
import shlex
import sys
import time
import webbrowser
from collections.abc import Callable
from pathlib import Path
from typing import Any, NoReturn

from testbed.hops import HOP_LIMIT_HEADER, TRACEPARENT_HEADER
from testbed.login import code_flow, device_flow
from testbed.redact import scrub, unverified_claims
from testbed.serve import create_http
from testbed.settings import (
    MOCK,
    MOCK_ENTITLEMENT,
    MOCK_ROGUE_ISSUER,
    MOCK_SHORT_ISSUER,
    NOT_REGISTERED,
    Client,
    Settings,
    load_settings,
)
from testbed.tokens import (
    TYPE_ACCESS,
    TYPE_REFRESH,
    Refused,
    TokenClient,
    TokenResponse,
)
from testbed.validation import TIMEOUT, HttpClient, InvalidToken

DEFAULT_SCOPE = "openid eduperson_entitlement offline_access"
# Claims that differ between any two tokens, whatever path they took
VOLATILE_CLAIMS = {"jti", "iat", "nbf", "exp", "nonce"}
# Fixtures of the mock: made-up test users, no real data
MOCK_USERS: dict[str, dict[str, Any]] = {
    "inside": {
        "username": "test-user-inside",
        "claims": {"eduperson_entitlement": [MOCK_ENTITLEMENT]},
    },
    "outside": {"username": "test-user-outside", "claims": {}},
}
REQUESTED_TYPES = {"access": TYPE_ACCESS, "refresh": TYPE_REFRESH}


class UsageError(Exception):
    """A command line is invalid."""


class _Parser(argparse.ArgumentParser):
    """Argument parser that raises exceptions instead of exiting."""

    def error(self, message: str) -> NoReturn:
        """Raise an exception for invalid arguments.

        Args:
            message: Description of the problem.

        Raises:
            UsageError: Always.
        """
        raise UsageError(message)


def _tamper(token: str) -> str:
    """Invalidate the signature of a JWT, keeping its claims.

    Args:
        token: JWT.

    Returns:
        JWT with another signature.
    """
    head, _, signature = token.rpartition(".")
    # Not the last character: its low bits may not be significant in base64url
    middle = len(signature) // 2
    flipped = "A" if signature[middle] != "A" else "B"
    return f"{head}.{signature[:middle]}{flipped}{signature[middle + 1 :]}"


def _final_hop(report: dict[str, Any]) -> dict[str, Any]:
    """Get the report of the last service in a chain.

    Args:
        report: Report of the first service.

    Returns:
        Report of the last service.
    """
    while isinstance(report.get("next"), dict):
        report = report["next"]
    return report


def hop_rows(report: dict[str, Any]) -> list[dict[str, Any]]:
    """Summarise a chain of reports, one row per service.

    Args:
        report: Report of the first service.

    Returns:
        What each service saw.
    """
    rows = []
    current: dict[str, Any] | None = report
    while isinstance(current, dict):
        claims = current.get("token", {}).get("claims", {})
        rows.append(
            {
                "service": current.get("service"),
                "refused": current.get("refused"),
                "reason": current.get("reason"),
                "sub": claims.get("sub"),
                "aud": claims.get("aud"),
                "client_id": claims.get("client_id"),
                "azp": claims.get("azp"),
                "act": claims.get("act"),
                "scope": claims.get("scope"),
                "lifetime": current.get("lifetime", {}).get("exp_minus_iat"),
                "entitlements": current.get("entitlements", {}).get("values"),
                "policy": current.get("policy"),
                "hop_limit": current.get("hop_limit"),
                "trace_origin": current.get("trace", {}).get("origin"),
                "traceparent": current.get("trace", {}).get("traceparent"),
            }
        )
        current = current.get("next")
    return rows


def compare_reports(first: dict[str, Any], second: dict[str, Any]) -> dict[str, Any]:
    """Compare what the last service saw in two chains.

    This is the case for `act`: without it, the node can't tell paths apart.

    Args:
        first: Report of the first chain.
        second: Report of the second chain.

    Returns:
        Stable claims that differ, and whether the node can see the path.
    """
    claims = [
        _final_hop(report).get("token", {}).get("claims", {})
        for report in (first, second)
    ]
    keys = (set(claims[0]) | set(claims[1])) - VOLATILE_CLAIMS
    differing = {
        key: [claims[0].get(key), claims[1].get(key)]
        for key in sorted(keys)
        if claims[0].get(key) != claims[1].get(key)
    }
    return {
        "hops": [len(hop_rows(first)), len(hop_rows(second))],
        "identical_at_last_hop": not differing,
        "differing_claims": differing,
        "act_present": ["act" in claim for claim in claims],
        "ignored": sorted(VOLATILE_CLAIMS),
    }


def _build_parser() -> _Parser:
    """Create the parser of session commands.

    Returns:
        Parser.
    """
    parser = _Parser(prog="", add_help=False, exit_on_error=False)
    commands = parser.add_subparsers(
        dest="command", parser_class=_Parser, required=True
    )

    def add(name: str, summary: str) -> _Parser:
        """Add a command.

        Args:
            name: Name of the command.
            summary: Description of the command.

        Returns:
            Parser of the command.
        """
        parsed: _Parser = commands.add_parser(
            name, help=summary, description=summary, exit_on_error=False, add_help=False
        )
        return parsed

    add("clients", "Show the configured clients (never their secrets).")
    add("discovery", "Show what the provider's discovery document says.")
    add("lifetimes", "Show the lifetimes of all tokens of this session.")
    add("help", "Show the commands.")
    add("quit", "End the session; all tokens are gone with it.")

    login = add("login", "Log in a user via the dummy client.")
    login.add_argument("name")
    login.add_argument("--as", dest="role", default="client")
    login.add_argument("--flow", choices=("code", "device"), default="code")
    login.add_argument("--scope", default=DEFAULT_SCOPE)
    login.add_argument("--resource", action="append", default=[])
    login.add_argument("--no-browser", action="store_true")
    login.add_argument("--mock-user", choices=sorted(MOCK_USERS), default="inside")
    login.add_argument("--mock-issuer", choices=("short", "rogue"))

    exchange = add("exchange", "Exchange a token; `--as` is the exchanging client.")
    exchange.add_argument("name")
    exchange.add_argument("--as", dest="role", required=True)
    exchange.add_argument("--from", dest="subject", required=True)
    exchange.add_argument("--audience", action="append", default=[])
    exchange.add_argument("--resource", action="append", default=[])
    exchange.add_argument("--scope")
    exchange.add_argument("--requested-type", choices=sorted(REQUESTED_TYPES))
    exchange.add_argument("--auth", choices=("auto", "basic", "post", "none"))
    exchange.add_argument("--tamper-subject", action="store_true")
    exchange.add_argument("--no-rules", action="store_true")

    refresh = add("refresh", "Redeem the refresh token held by a token of the session.")
    refresh.add_argument("name")
    refresh.add_argument("--as", dest="role", required=True)
    refresh.add_argument("--from", dest="holder", required=True)
    refresh.add_argument("--audience", action="append", default=[])
    refresh.add_argument("--resource", action="append", default=[])
    refresh.add_argument("--scope")

    credentials = add("credentials", "Get a client's own token.")
    credentials.add_argument("name")
    credentials.add_argument("--as", dest="role", required=True)
    credentials.add_argument("--scope")

    call = add("call", "Call a service with a token and show what each hop saw.")
    call.add_argument("service")
    call.add_argument("--token", required=True)
    call.add_argument("--save")
    call.add_argument("--hop-limit")
    call.add_argument("--traceparent")
    call.add_argument("--tamper", action="store_true")
    call.add_argument("--id-token", action="store_true")
    call.add_argument("--full", action="store_true")

    for name, summary in (
        ("show", "Show the decoded claims of a token."),
        ("userinfo", "Call user info with a token; shows released entitlements."),
    ):
        add(name, summary).add_argument("name")

    for name, summary in (
        ("introspect", "Introspect a token as a client."),
        ("revoke", "Revoke a token as a client."),
    ):
        command = add(name, summary)
        command.add_argument("name")
        command.add_argument("--as", dest="role", required=True)
        command.add_argument("--refresh", action="store_true")

    wait = add("wait-expiry", "Block until a token has expired.")
    wait.add_argument("name")
    wait.add_argument("--margin", type=int, default=5)

    compare = add("compare", "Compare what the last hop saw in two saved calls.")
    compare.add_argument("first")
    compare.add_argument("second")
    return parser


class Session:
    """State and commands of a session.

    Attributes:
        tokens: Tokens of the session, by name; in memory only.
        reports: Saved reports of calls, by name.
    """

    def __init__(
        self,
        settings: Settings,
        http: HttpClient,
        output: Callable[[str], None] = print,
        record: Path | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        """Create a session.

        Args:
            settings: Settings.
            http: HTTP client.
            output: Shows text to the user.
            record: File to append decoded results to, if any.
            sleep: Waits for a number of seconds.
        """
        self.settings = settings
        self.tokens: dict[str, TokenResponse] = {}
        self.reports: dict[str, dict[str, Any]] = {}
        self._http = http
        self._output = output
        self._record = record
        self._sleep = sleep
        self._provider = TokenClient(settings, http)
        self._parser = _build_parser()

    def _client(self, role: str) -> Client:
        """Get the client of a role.

        Args:
            role: Role.

        Returns:
            Client.

        Raises:
            UsageError: There's no such client.
        """
        if role not in self.settings.clients:
            raise UsageError(f"No client for role '{role}'")
        return self.settings.clients[role]

    def _token(self, name: str) -> TokenResponse:
        """Get a token of the session.

        Args:
            name: Name of the token.

        Returns:
            Token.

        Raises:
            UsageError: There's no such token.
        """
        if name not in self.tokens:
            raise UsageError(f"No token '{name}'; have: {sorted(self.tokens)}")
        return self.tokens[name]

    def _resolve(self, target: str) -> str:
        """Resolve a shorthand for an audience or resource.

        Args:
            target: `@<role>` for the role's client ID, `@<role>.url` for its
                resource indicator, `@unregistered` for a target that no client
                has registered; anything else is used as it is.

        Returns:
            Audience or resource.

        Raises:
            UsageError: The shorthand can't be resolved.
        """
        if not target.startswith("@"):
            return target
        if target == "@unregistered":
            return NOT_REGISTERED
        role, _, kind = target[1:].partition(".")
        client = self._client(role)
        if kind == "url":
            if not client.resource:
                raise UsageError(f"No resource indicator for role '{role}'")
            return client.resource
        return client.client_id

    def _mock_browser(self, user: str) -> Callable[[str], None]:
        """Create a browser stand-in that logs in at the mock.

        Args:
            user: Key of a mock user.

        Returns:
            Function that completes the login at an authorization URL.
        """

        def browse(url: str) -> None:
            """Submit the mock's login form and follow the redirect.

            Args:
                url: Authorization URL.
            """
            fixture = MOCK_USERS[user]
            response = self._http.post(
                url,
                data={
                    "username": fixture["username"],
                    "claims": json.dumps(fixture["claims"]),
                },
                timeout=TIMEOUT,
                allow_redirects=False,
            )
            self._http.get(
                response.headers["Location"], timeout=TIMEOUT, allow_redirects=False
            )

        return browse

    def _real_browser(self, open_browser: bool) -> Callable[[str], None]:
        """Create a function that sends the user to an authorization URL.

        Args:
            open_browser: Whether to open the browser, too.

        Returns:
            Function that shows and optionally opens the URL.
        """

        def browse(url: str) -> None:
            """Show and optionally open the URL.

            Args:
                url: Authorization URL (holds no token or secret).
            """
            self._output(f"Log in at: {url}")
            if open_browser:
                webbrowser.open(url)

        return browse

    def _login(self, args: argparse.Namespace) -> dict[str, Any]:
        """Run the `login` command.

        Args:
            args: Arguments.

        Returns:
            Result.

        Raises:
            UsageError: Mock options are used with another provider.
        """
        is_mock = self.settings.provider == MOCK
        if args.mock_issuer and not is_mock:
            raise UsageError("--mock-issuer only works with the mock")
        issuers = {"short": MOCK_SHORT_ISSUER, "rogue": MOCK_ROGUE_ISSUER}
        provider = (
            TokenClient(self.settings, self._http, issuers[args.mock_issuer])
            if args.mock_issuer
            else self._provider
        )
        client = self._client(args.role)
        resources = [self._resolve(item) for item in args.resource]
        if args.flow == "device":
            issued = device_flow(
                provider, client, args.scope, self._output, self._sleep
            )
        else:
            browser = (
                self._mock_browser(args.mock_user)
                if is_mock
                else self._real_browser(not args.no_browser)
            )
            issued = code_flow(provider, client, args.scope, resources, browser)
        self.tokens[args.name] = issued
        return {"ok": True, "token": args.name, **issued.view()}

    def _exchange(self, args: argparse.Namespace) -> dict[str, Any]:
        """Run the `exchange` command.

        Args:
            args: Arguments.

        Returns:
            Result.
        """
        subject = self._token(args.subject).access_token
        if args.tamper_subject:
            subject = _tamper(subject)
        issued = self._provider.exchange(
            self._client(args.role),
            subject,
            audience=[self._resolve(item) for item in args.audience],
            resource=[self._resolve(item) for item in args.resource],
            scope=args.scope,
            requested_type=(
                REQUESTED_TYPES[args.requested_type] if args.requested_type else None
            ),
            auth=args.auth or "auto",
            apply_rules=not args.no_rules,
        )
        self.tokens[args.name] = issued
        return {"ok": True, "token": args.name, **issued.view()}

    def _refresh(self, args: argparse.Namespace) -> dict[str, Any]:
        """Run the `refresh` command.

        Args:
            args: Arguments.

        Returns:
            Result; says whether the provider rotated the refresh token.

        Raises:
            UsageError: The token holds no refresh token.
        """
        holder = self._token(args.holder)
        if not holder.refresh_token:
            raise UsageError(f"'{args.holder}' holds no refresh token")
        issued = self._provider.refresh(
            self._client(args.role),
            holder.refresh_token,
            audience=[self._resolve(item) for item in args.audience],
            resource=[self._resolve(item) for item in args.resource],
            scope=args.scope,
        )
        self.tokens[args.name] = issued
        rotated = (
            None
            if issued.refresh_token is None
            else issued.refresh_token != holder.refresh_token
        )
        return {
            "ok": True,
            "token": args.name,
            "refresh_token_rotated": rotated,
            **issued.view(),
        }

    def _credentials(self, args: argparse.Namespace) -> dict[str, Any]:
        """Run the `credentials` command.

        Args:
            args: Arguments.

        Returns:
            Result.
        """
        issued = self._provider.client_credentials(self._client(args.role), args.scope)
        self.tokens[args.name] = issued
        return {"ok": True, "token": args.name, **issued.view()}

    def _call(self, args: argparse.Namespace) -> dict[str, Any]:
        """Run the `call` command.

        Args:
            args: Arguments.

        Returns:
            Result, with one row per service.
        """
        held = self._token(args.token)
        token = held.access_token
        if args.id_token:
            if not held.id_token:
                raise UsageError(f"'{args.token}' holds no ID token")
            token = held.id_token
        if args.tamper:
            token = _tamper(token)
        headers = {"Authorization": f"Bearer {token}"}
        if args.hop_limit is not None:
            headers[HOP_LIMIT_HEADER] = args.hop_limit
        if args.traceparent is not None:
            headers[TRACEPARENT_HEADER] = args.traceparent
        response = self._http.get(
            f"{self.settings.service_url(args.service)}/report",
            headers=headers,
            timeout=TIMEOUT * 6,
            allow_redirects=False,
        )
        report: dict[str, Any] = scrub(response.json())
        if args.save:
            self.reports[args.save] = report
        result = {
            "ok": response.status_code == 200,
            "status": response.status_code,
            "hops": hop_rows(report),
        }
        if args.full:
            result["report"] = report
        return result

    def _lifetimes(self) -> dict[str, Any]:
        """Run the `lifetimes` command.

        Returns:
            For each token: stated lifetime, `exp` minus `iat`, time left, and
            whether it holds a refresh token.
        """
        now = int(time.time())
        rows = {}
        for name, token in self.tokens.items():
            claims = unverified_claims(token.access_token)
            exp, iat = claims.get("exp"), claims.get("iat")
            rows[name] = {
                "expires_in_stated_at_issue": token.expires_in,
                "exp_minus_iat": exp - iat if exp and iat else None,
                "seconds_left": exp - now if exp else None,
                "refresh_token": bool(token.refresh_token),
            }
        return {"ok": True, "tokens": rows}

    def _wait_expiry(self, args: argparse.Namespace) -> dict[str, Any]:
        """Run the `wait-expiry` command.

        Args:
            args: Arguments.

        Returns:
            Result.

        Raises:
            UsageError: The token has no `exp` claim.
        """
        exp = unverified_claims(self._token(args.name).access_token).get("exp")
        if not isinstance(exp, int):
            raise UsageError(f"'{args.name}' has no `exp` claim")
        seconds = exp + args.margin - time.time()
        if seconds > 0:
            self._output(f"Waiting {int(seconds)} s; the session stays open.")
            self._sleep(seconds)
        return {"ok": True, "token": args.name, "expired_at": exp}

    def _clients(self) -> dict[str, Any]:
        """Run the `clients` command.

        Returns:
            Client IDs and resource indicators; whether there's a secret.
        """
        return {
            "ok": True,
            "provider": self.settings.provider,
            "issuer": self.settings.issuer,
            "ls_login_rules_emulated": self.settings.emulate_ls_login_rules,
            "clients": {
                role: {
                    "client_id": client.client_id,
                    "resource": client.resource,
                    "has_secret": client.secret is not None,
                }
                for role, client in self.settings.clients.items()
            },
        }

    def _discovery(self) -> dict[str, Any]:
        """Run the `discovery` command.

        Returns:
            Selected fields of the discovery document.
        """
        document = self._provider.document
        fields = (
            "issuer",
            "grant_types_supported",
            "token_endpoint_auth_methods_supported",
            "code_challenge_methods_supported",
            "device_authorization_endpoint",
            "introspection_endpoint",
            "revocation_endpoint",
        )
        return {"ok": True, **{key: document.get(key) for key in fields}}

    def _dispatch(self, args: argparse.Namespace) -> dict[str, Any]:
        """Run a parsed command.

        Args:
            args: Arguments.

        Returns:
            Result.
        """
        command = args.command
        result: dict[str, Any]
        if command == "login":
            result = self._login(args)
        elif command == "exchange":
            result = self._exchange(args)
        elif command == "refresh":
            result = self._refresh(args)
        elif command == "credentials":
            result = self._credentials(args)
        elif command == "call":
            result = self._call(args)
        elif command == "lifetimes":
            result = self._lifetimes()
        elif command == "wait-expiry":
            result = self._wait_expiry(args)
        elif command == "clients":
            result = self._clients()
        elif command == "discovery":
            result = self._discovery()
        elif command == "show":
            result = {"ok": True, **self._token(args.name).view()}
        elif command == "userinfo":
            result = {
                "ok": True,
                **self._provider.userinfo(self._token(args.name).access_token),
            }
        elif command == "introspect":
            result = {"ok": True, **self._introspect(args)}
        elif command == "revoke":
            result = self._revoke(args)
        elif command == "compare":
            result = {
                "ok": True,
                **compare_reports(self._report(args.first), self._report(args.second)),
            }
        else:
            result = {"ok": True, "help": self._parser.format_help()}
        return result

    def _report(self, name: str) -> dict[str, Any]:
        """Get a saved report.

        Args:
            name: Name of the report.

        Returns:
            Report.

        Raises:
            UsageError: There's no such report.
        """
        if name not in self.reports:
            raise UsageError(f"No saved report '{name}'; have: {sorted(self.reports)}")
        return self.reports[name]

    def _held(self, args: argparse.Namespace) -> tuple[str, str | None]:
        """Get the token that a command is about.

        Args:
            args: Arguments, with `name` and `refresh`.

        Returns:
            Token and its type hint.

        Raises:
            UsageError: The token holds no refresh token.
        """
        held = self._token(args.name)
        if not args.refresh:
            return held.access_token, "access_token"
        if not held.refresh_token:
            raise UsageError(f"'{args.name}' holds no refresh token")
        return held.refresh_token, "refresh_token"

    def _introspect(self, args: argparse.Namespace) -> dict[str, Any]:
        """Run the `introspect` command.

        Args:
            args: Arguments.

        Returns:
            Result.
        """
        token, hint = self._held(args)
        return self._provider.introspect(self._client(args.role), token, hint)

    def _revoke(self, args: argparse.Namespace) -> dict[str, Any]:
        """Run the `revoke` command.

        Args:
            args: Arguments.

        Returns:
            Result.
        """
        token, hint = self._held(args)
        status = self._provider.revoke(self._client(args.role), token, hint)
        return {"ok": status == 200, "status": status}

    def execute(self, line: str) -> dict[str, Any]:
        """Run one command line.

        Args:
            line: Command line.

        Returns:
            Scrubbed result. `ok` says whether the request succeeded; refusals
            are results, too.
        """
        try:
            words = shlex.split(line)
            args = self._parser.parse_args(words)
            result = self._dispatch(args)
        except (UsageError, ValueError, argparse.ArgumentError) as exc:
            result = {"ok": False, "usage_error": str(exc)}
        except Refused as exc:
            result = {"ok": False, **exc.view()}
        except InvalidToken as exc:
            result = {"ok": False, "provider_problem": exc.detail}
        except Exception as exc:
            # Tokens exist only in this process: no failure may end the session.
            # The type only, as messages of some exceptions could hold values
            result = {"ok": False, "failure": type(exc).__name__}
        scrubbed: dict[str, Any] = scrub(result)
        self._write_record(line, scrubbed)
        return scrubbed

    def _write_record(self, line: str, result: dict[str, Any]) -> None:
        """Append a result to the record, if any.

        Args:
            line: Command line.
            result: Scrubbed result.
        """
        if self._record is not None:
            entry = {"time": int(time.time()), "command": line, "result": result}
            with self._record.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(entry) + "\n")

    def run_interactive(self, read: Callable[[str], str] = input) -> None:
        """Read commands until the user quits.

        Args:
            read: Reads a line from the user.
        """
        while True:
            try:
                line = read("tb> ").strip()
            except (EOFError, KeyboardInterrupt):
                return
            if line in ("quit", "exit"):
                return
            if line and not line.startswith("#"):
                try:
                    result = self.execute(line)
                except KeyboardInterrupt:
                    # E.g., to stop waiting; the tokens stay
                    self._output("Interrupted.")
                    continue
                self._output(result.pop("help", None) or json.dumps(result, indent=2))


def _check_record(record: Path) -> None:
    """Check that results can be recorded, before any token exists.

    Failing later would end the session and lose its tokens.

    Args:
        record: File to append results to.

    Raises:
        SystemExit: The file can't be written.
    """
    try:
        record.parent.mkdir(parents=True, exist_ok=True)
        with record.open("a", encoding="utf-8"):
            pass
    except OSError as exc:
        raise SystemExit(
            f"Can't write {record}: {exc.strerror}. In a container, the folder "
            "must be writable for its user; see docs/reference/settings.md."
        ) from exc


def main() -> None:
    """Run an interactive session."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", default=os.environ.get("TESTBED_PROVIDER"))
    parser.add_argument("--record", type=Path, help="Append results to this file")
    args = parser.parse_args()
    try:
        settings = load_settings(os.environ, args.provider)
    except ValueError as exc:
        sys.exit(str(exc))
    if args.record:
        _check_record(args.record)
    Session(settings, create_http(settings), record=args.record).run_interactive()
