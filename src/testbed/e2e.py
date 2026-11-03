"""End-to-end run against the mock, driven through the session's commands.

Uses the same command lines as the docs. Passing shows that OUR code works and
handles refusals. It says nothing about LS Login: see the MOCK GAP section of
the output and docs/testbed/limits.md.
"""

import json
import os
import re
import socket
import sys
import tempfile
import time
from collections.abc import Callable, Iterable
from dataclasses import replace
from pathlib import Path
from typing import Any

import requests

from testbed.launcher import Services
from testbed.redact import JWT_PATTERN
from testbed.rules import REFUSED_BY_RULE
from testbed.serve import create_http
from testbed.session import Session
from testbed.settings import (
    DUMMY_SECRET,
    MOCK,
    MOCK_ENTITLEMENT,
    MOCK_ISSUER,
    SERVICE_PORTS,
    Settings,
    load_settings,
)
from testbed.tokens import Refused, TokenClient
from testbed.validation import InvalidToken

TRACE = "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"
# Pages with `tb>` lines. Each group runs in one session, in this order
PAGE_GROUPS = (
    ("setup/checking.md",),
    ("tutorial/ls-login.md", "tutorial/refused.md"),
    ("session.md",),
)


class Run:
    """Results of the run, and all output, to scan for leaks."""

    def __init__(self, session_output: list[str]) -> None:
        """Create the run.

        Args:
            session_output: All output so far; appended to by this run.
        """
        self.failures: list[str] = []
        self.count = 0
        self.output = session_output

    def say(self, line: str) -> None:
        """Print a line and keep it for the leak scan.

        Args:
            line: Line of output.
        """
        self.output.append(line)
        print(line, flush=True)

    def section(self, title: str) -> None:
        """Print a section heading.

        Args:
            title: Heading.
        """
        self.say(f"\n== {title}")

    def check(self, name: str, passed: bool, seen: Any = None) -> None:
        """Record and print the result of a check.

        Args:
            name: What is checked.
            passed: Whether the check passed.
            seen: What was seen, for the output; decoded claims only.
        """
        self.count += 1
        if not passed:
            self.failures.append(name)
        suffix = f"  [{json.dumps(seen)}]" if seen is not None else ""
        self.say(f"{'PASS' if passed else 'FAIL'}  {name}{suffix}")


def _brief(hops: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Reduce rows of a call to what matters in the output.

    Args:
        hops: Rows of a call.

    Returns:
        Selected fields.
    """
    fields = ("service", "aud", "client_id", "act", "hop_limit", "policy")
    return [{key: hop.get(key) for key in fields} for hop in hops]


def _happy_path(run: Run, tb: Callable[[str], dict[str, Any]]) -> None:
    """Check two hops: client to gateway to node, and the orchestrator variant.

    Args:
        run: The run.
        tb: Runs a session command.
    """
    run.section("Happy path: client -> gateway -> node")
    login = tb("login user --as client --mock-user inside")
    claims = login.get("claims", {})
    run.check(
        "login with PKCE via the local callback",
        login["ok"] and claims.get("sub") == "test-user-inside",
        {"aud": claims.get("aud"), "client_id": claims.get("client_id")},
    )
    run.check("at+jwt header", login.get("header", {}).get("typ") == "at+jwt")
    hop1 = tb("exchange to-gateway --as client --from user --audience @gateway")
    run.check(
        "client exchanges for the gateway",
        hop1["ok"] and hop1["claims"]["aud"] == "tx-gateway",
        {"aud": hop1.get("claims", {}).get("aud")},
    )
    call = tb(f"call gateway --token to-gateway --save direct --traceparent {TRACE}")
    hops = call.get("hops", [])
    run.check("gateway -> node returns 200", call.get("status") == 200, _brief(hops))
    run.check(
        "each hop sees only itself in aud; sub is preserved",
        [hop["aud"] for hop in hops] == ["tx-gateway", "tx-node"]
        and {hop["sub"] for hop in hops} == {"test-user-inside"},
    )
    run.check(
        "traceparent passed through unchanged",
        [hop["traceparent"] for hop in hops] == [TRACE, TRACE],
    )
    run.check("hop limit decremented", [hop["hop_limit"] for hop in hops] == [8, 7])

    run.section("Variant: client -> orchestrator -> gateway -> node")
    tb("exchange to-orch --as client --from user --audience @orchestrator")
    chain = tb("call orchestrator --token to-orch --save chained")
    hops = chain.get("hops", [])
    run.check(
        "three hops return 200",
        chain.get("status") == 200 and len(hops) == 3,
        [hop["aud"] for hop in hops],
    )
    run.check(
        "traceparent generated once, then kept",
        len({hop["traceparent"] for hop in hops}) == 1
        and hops[0]["trace_origin"] == "generated"
        and hops[2]["trace_origin"] == "received",
    )

    run.section("Case for act: the node can't see the path")
    compared = tb("compare direct chained")
    run.check(
        "node sees the same claims on both paths",
        compared.get("identical_at_last_hop") is True
        and compared.get("act_present") == [False, False],
        compared,
    )


def _refusals(run: Run, tb: Callable[[str], dict[str, Any]]) -> None:
    """Check the refused cases.

    Args:
        run: The run.
        tb: Runs a session command.
    """
    run.section("Refused by the testbed's LS Login rules; mock only")
    refused = tb("exchange bad --as gateway --from user --audience @node")
    run.check(
        "subject token without our client in aud",
        not refused["ok"] and refused.get("refused_by") == REFUSED_BY_RULE,
        refused,
    )
    refused = tb("exchange bad --as client --from user --audience @unregistered")
    run.check(
        "target not registered",
        not refused["ok"]
        and refused.get("refused_by") == REFUSED_BY_RULE
        and refused.get("error") == "invalid_target",
        refused,
    )
    refused = tb("exchange bad --as gateway --from to-gateway --audience @unregistered")
    run.check(
        "target not registered (valid subject token)",
        refused.get("error") == "invalid_target",
    )
    by_url = tb("exchange to-gw-url --as client --from user --resource @gateway.url")
    result = tb("call gateway --token to-gw-url")
    run.check(
        "token with only a URL in aud reaches the gateway, but can't go further",
        by_url["ok"] and result.get("status") == 502,
        {"aud": by_url.get("claims", {}).get("aud")},
    )

    run.section("Refused by the services' own validation")
    for name, line, reason in (
        ("wrong audience at the node", "call node --token to-gateway", "audience"),
        ("login token at the node", "call node --token user", "audience"),
        ("tampered signature", "call gateway --token to-gateway --tamper", "signature"),
    ):
        result = tb(line)
        hop = result.get("hops", [{}])[0]
        run.check(
            name, result.get("status") == 401 and hop.get("reason") == reason, reason
        )
    tb("login rogue --as client --mock-issuer rogue")
    result = tb("call node --token rogue")
    run.check(
        "untrusted issuer",
        result.get("status") == 401 and result["hops"][0]["reason"] == "issuer",
    )
    tb("credentials plain --as node --scope plain-jwt")
    result = tb("call node --token plain")
    run.check(
        "right audience, but typ is not at+jwt",
        result.get("status") == 401 and result["hops"][0]["reason"] == "type",
    )
    tb("login short --as client --mock-issuer short")
    tb("wait-expiry short --margin 1")
    result = tb("call node --token short")
    run.check(
        "expired token at the node",
        result.get("status") == 401 and result["hops"][0]["reason"] == "expired",
    )
    refused = tb("exchange bad --as client --from short --audience @gateway")
    run.check(
        "expired subject token, by the testbed's rule",
        refused.get("refused_by") == REFUSED_BY_RULE
        and "expired" in refused.get("error_description", ""),
    )


def _entitlements(run: Run, tb: Callable[[str], dict[str, Any]]) -> None:
    """Check that users outside the group are refused at the node only.

    Args:
        run: The run.
        tb: Runs a session command.
    """
    run.section("Users outside the group: refused by the node only")
    inside = tb("call gateway --token to-gateway")
    run.check(
        "inside: node allows",
        inside.get("status") == 200 and inside["hops"][-1]["policy"] == "allowed",
        inside["hops"][-1]["entitlements"],
    )
    login = tb("login outside --as client --mock-user outside")
    run.check("outside: can log in", login["ok"])
    run.check(
        "outside: client can exchange",
        tb("exchange out-gw --as client --from outside --audience @gateway")["ok"],
    )
    result = tb("call gateway --token out-gw")
    hops = result.get("hops", [])
    run.check(
        "outside: gateway passes it on, node answers 403, not 401",
        result.get("status") == 403
        and hops[0]["policy"] == "off"
        and hops[1]["refused"] == "entitlement",
        _brief(hops),
    )


def _refresh(run: Run, tb: Callable[[str], dict[str, Any]]) -> None:
    """Check the refresh token commands.

    Args:
        run: The run.
        tb: Runs a session command.
    """
    run.section("Refresh tokens: commands only; the mock's behaviour is no evidence")
    login = tb("show user")
    run.check("login returned a refresh token", login["refresh_token"] != "absent")
    refreshed = tb("refresh user2 --as client --from user")
    run.check(
        "refresh returns a token for the same user",
        refreshed["ok"] and refreshed["claims"]["sub"] == "test-user-inside",
        {"rotated": refreshed.get("refresh_token_rotated")},
    )
    run.check("introspection works", tb("introspect user --as client")["active"])
    run.check("user info works", tb("userinfo user")["sub"] == "test-user-inside")
    run.check("lifetimes listed", "user" in tb("lifetimes")["tokens"])
    run.check("revocation works", tb("revoke user --as client --refresh")["ok"])


def _loops(run: Run, tb: Callable[[str], dict[str, Any]]) -> None:
    """Check the hop limit.

    Args:
        run: The run.
        tb: Runs a session command.
    """
    run.section("Hop limit; no provider involved beyond exchanges")
    result = tb("call gateway --token to-gateway --hop-limit 0")
    run.check("limit 0 at the gateway: 508", result.get("status") == 508)
    result = tb("call gateway --token to-gateway --hop-limit 1")
    run.check("limit 1: reaches the node", result.get("status") == 200)
    result = tb("call gateway --token to-gateway --hop-limit nonsense")
    run.check("invalid limit: 400", result.get("status") == 400)
    # The `loop` client exists on the mock only, with itself as a target
    tb("credentials loop-seed --as loop")
    result = tb("call loop --token loop-seed --hop-limit 3")
    hops = result.get("hops", [])
    run.check(
        "a loop stops at the limit",
        result.get("status") == 508
        and [hop["hop_limit"] for hop in hops] == [3, 2, 1, 0],
        [(hop["hop_limit"], hop["reason"]) for hop in hops],
    )


def _mock_gaps(run: Run, session: Session) -> None:
    """Show what the mock itself lets through, with the testbed's rules off.

    If one of these starts failing, the mock's behaviour changed: update
    docs/testbed/limits.md and the tests.

    Args:
        run: The run.
        session: The session.
    """
    tb = session.execute
    settings = session.settings
    run.section("MOCK GAP: what the mock accepts with the testbed's rules off")
    tb("login gap --as client")
    tb("login gap-short --as client --mock-issuer short")
    tb("wait-expiry gap-short --margin 1")
    for name, line in (
        ("exchanger not in subject aud", "--as gateway --from gap --audience @node"),
        ("unregistered target", "--as client --from gap --audience @unregistered"),
        ("expired subject", "--as client --from gap-short --audience @gateway"),
        (
            "tampered subject",
            "--as client --from gap --audience @gateway --tamper-subject",
        ),
    ):
        result = tb(f"exchange gap-x {line} --no-rules")
        run.check(f"mock accepts: {name}", result["ok"])
    client = replace(settings.clients["gateway"], secret="wrong-secret")
    try:
        TokenClient(settings, create_http(settings)).exchange(
            client,
            session.tokens["gap"].access_token,
            audience=["tx-node"],
            apply_rules=False,
        )
        accepted = True
    except Refused:
        accepted = False
    run.check("mock accepts: wrong client secret", accepted)
    # The mock has no public clients for exchange, so that can't be shown here
    result = tb("exchange gap-x --as public --from gap --audience @gateway --no-rules")
    run.check(
        "mock refuses public clients, regardless of settings; LS Login unknown",
        not result["ok"] and result.get("error") == "invalid_request",
    )
    result = tb(
        "exchange gap-x --as client --from gap --audience @gateway "
        "--requested-type refresh --scope offline_access"
    )
    run.check(
        "mock never returns a refresh token from an exchange",
        result["ok"] and result["refresh_token"] == "absent",
    )
    run.check(
        "mock has no act claim, even when asked",
        "act" not in result.get("claims", {}),
    )


def docs_commands(docs: Path, pages: tuple[str, ...]) -> list[str]:
    """Get the session commands of pages of the docs.

    Args:
        docs: Folder of the docs.
        pages: Pages, relative to the folder.

    Returns:
        Command lines, without the prompt.
    """
    lines: list[str] = []
    for page in pages:
        text = (docs / page).read_text(encoding="utf-8")
        lines += re.findall(r"^tb> (.+)$", text, flags=re.MULTILINE)
    return lines


def _docs_commands(run: Run, settings: Settings, record: Path, docs: Path) -> None:
    """Run every command of the docs, to catch mistakes in them.

    Refusals are fine here, and results are no evidence. Only commands that
    can't run count as failures. Steps that build on a refresh token from an
    exchange can't run, as the mock doesn't issue one.

    Args:
        run: The run.
        settings: Settings.
        record: File for all results of the session, for the leak scan.
        docs: Folder of the docs.
    """
    run.section("Every command of the docs runs (results are no evidence)")
    for pages in PAGE_GROUPS:
        lines = docs_commands(docs, pages)
        session = Session(
            settings, create_http(settings), output=run.output.append, record=record
        )
        broken = []
        for line in lines:
            # Waits for as long as tokens live
            if line.startswith("wait-expiry"):
                continue
            result = session.execute(line)
            conditional = re.search(r"\bro(-[abc])?\b", line) is not None
            if "failure" in result or ("usage_error" in result and not conditional):
                broken.append((line, result))
        run.check(
            f"{', '.join(pages)}: {len(lines)} commands",
            bool(lines) and not broken,
            broken or None,
        )


def _leak_scan(run: Run, record: Path) -> None:
    """Check that no output or result of this run holds a token or secret.

    Args:
        run: The run.
        record: File with all results of the session.
    """
    run.section("Leak scan: all output, service logs and session results")
    recorded = record.read_text(encoding="utf-8")
    run.check("results include decoded claims", "test-user-inside" in recorded)
    text = "\n".join([*run.output, recorded])
    run.check("no JWT in any output", JWT_PATTERN.search(text) is None)
    run.check("no client secret in any output", DUMMY_SECRET not in text)


def run_scenarios(
    settings: Settings, output: list[str], record: Path, docs: Path
) -> Run:
    """Run all scenarios.

    Args:
        settings: Settings for the mock.
        output: All output so far, for the leak scan.
        record: File for all results of the session, for the leak scan.
        docs: Folder of the docs.

    Returns:
        The finished run.
    """
    run = Run(output)
    session = Session(
        settings, create_http(settings), output=output.append, record=record
    )
    tb = session.execute
    run.section("Provider")
    clients = tb("clients")
    run.check(
        "mock with the testbed's LS Login rules on",
        clients["provider"] == MOCK and clients["ls_login_rules_emulated"] is True,
    )
    run.check("issuer", tb("discovery")["issuer"] == MOCK_ISSUER)
    for scenario in (_happy_path, _refusals, _entitlements, _refresh, _loops):
        scenario(run, tb)
    _mock_gaps(run, session)
    _docs_commands(run, settings, record, docs)
    return run


def ports_in_use(ports: Iterable[int]) -> list[int]:
    """Find the ports that something else listens on.

    Args:
        ports: Ports on the local host.

    Returns:
        Ports that can't be bound.
    """
    taken = []
    for port in ports:
        with socket.socket() as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                probe.bind(("localhost", port))
            except OSError:
                taken.append(port)
    return taken


def main() -> None:
    """Start the services, run all scenarios, stop the services."""
    taken = ports_in_use(SERVICE_PORTS.values())
    if taken:
        print(
            f"Ports in use: {taken}. This run starts its own services: stop "
            "others first (with Compose: `docker compose down -v`).",
            flush=True,
        )
        sys.exit(2)
    settings = load_settings(
        {
            **os.environ,
            "TESTBED_PROVIDER": MOCK,
            "TESTBED_REQUIRED_ENTITLEMENT": MOCK_ENTITLEMENT,
        },
        MOCK,
    )
    output: list[str] = []
    services = Services(settings, output.append)
    started = time.monotonic()
    folder = tempfile.TemporaryDirectory(prefix="testbed-e2e-")
    record = Path(folder.name) / "record.jsonl"
    try:
        services.wait_until_healthy()
        run = run_scenarios(
            settings, output, record, Path(os.environ.get("TESTBED_DOCS", "docs"))
        )
    except (
        InvalidToken,
        requests.RequestException,
        KeyError,
        TypeError,
        OSError,
    ) as exc:
        print(f"Run aborted: {type(exc).__name__}: {exc}", flush=True)
        print("\n".join(line for line in output if line.startswith("[")), flush=True)
        sys.exit(2)
    finally:
        services.stop()
    _leak_scan(run, record)
    folder.cleanup()
    seconds = time.monotonic() - started
    passed = run.count - len(run.failures)
    print(f"\n{passed}/{run.count} checks passed in {seconds:.0f} s")
    if run.failures:
        print("FAILED:", *run.failures, sep="\n  ")
        sys.exit(1)


if __name__ == "__main__":
    main()
