"""Tests of `testbed.session`."""

import io
import json
import os
import sys
import urllib.parse
from pathlib import Path
from typing import Any

import pytest
import requests

from testbed import login
from testbed.session import (
    Session,
    UsageError,
    _build_parser,
    _tamper,
    compare_reports,
    hop_rows,
    main,
)
from testbed.settings import (
    MOCK_ENTITLEMENT,
    MOCK_ISSUER,
    MOCK_SHORT_ISSUER,
    NOT_REGISTERED,
    Settings,
)
from testbed.tokens import TYPE_REFRESH, TokenResponse
from tests.conftest import FakeProvider, FakeResponse

pytestmark = pytest.mark.usefixtures("callback_port")


@pytest.fixture
def session(ls_settings: Settings, provider: FakeProvider) -> Session:
    """Provide a session with a token named `user`.

    Args:
        ls_settings: Settings.
        provider: Fake provider.

    Returns:
        Session.
    """
    result = Session(ls_settings, provider, output=lambda _line: None)
    result.tokens["user"] = TokenResponse(
        access_token=provider.mint(aud="id-client"),
        refresh_token="opaque-refresh-value",
        id_token=provider.mint(typ="JWT", aud="id-client"),
        expires_in=3600,
    )
    return result


def _chain(*auds: str, **last: Any) -> dict[str, Any]:
    """Create a report of a chain of services.

    Args:
        *auds: Audiences of the hops.
        **last: Claims of the last hop.

    Returns:
        Report of the first service.
    """
    report: dict[str, Any] | None = None
    for position, aud in enumerate(reversed(auds)):
        claims = {"aud": aud, "sub": "user-1", "jti": aud, "exp": position}
        if position == 0:
            claims.update(last)
        current: dict[str, Any] = {"service": aud, "token": {"claims": claims}}
        if report is not None:
            current["next"] = report
        report = current
    assert report is not None
    return report


def test_compare_reports_shows_an_invisible_chain() -> None:
    """Different paths with the same claims at the last hop can't be told apart."""
    result = compare_reports(_chain("a", "node"), _chain("b", "c", "node"))
    assert result["hops"] == [2, 3]
    assert result["identical_at_last_hop"] is True
    assert result["act_present"] == [False, False]


def test_compare_reports_shows_differences_and_act() -> None:
    """Should LS Login add `act`, the difference shows."""
    act = {"sub": "gateway"}
    result = compare_reports(_chain("a", "node"), _chain("a", "node", act=act))
    assert result["identical_at_last_hop"] is False
    assert result["differing_claims"] == {"act": [None, act]}
    assert result["act_present"] == [False, True]


def test_hop_rows_handles_refusals() -> None:
    """Refusals without a token still give a row."""
    rows = hop_rows({"service": "node", "refused": "token", "reason": "audience"})
    assert rows[0]["reason"] == "audience"
    assert rows[0]["sub"] is None


def test_tamper_changes_only_the_signature(provider: FakeProvider) -> None:
    """Tampering keeps header and claims."""
    token = provider.mint()
    assert _tamper(token) != token
    assert _tamper(token).rsplit(".", 1)[0] == token.rsplit(".", 1)[0]


def test_exchange_resolves_shorthands(session: Session, provider: FakeProvider) -> None:
    """Shorthands name clients and indicators; results hold no tokens."""
    result = session.execute(
        "exchange x --as gateway --from user --audience @node "
        "--resource @node.url --resource https://raw.example/ "
        '--scope "openid offline_access" --requested-type refresh --auth post'
    )
    assert result["ok"]
    _, form, _ = provider.posts[-1]
    assert form["audience"] == ["id-node"]
    assert form["resource"] == ["https://node.example/", "https://raw.example/"]
    assert form["scope"] == "openid offline_access"
    assert form["requested_token_type"].endswith("refresh_token")
    assert form["client_secret"] == "secret-gateway"
    assert session.tokens["x"].access_token not in json.dumps(result)


def test_exchange_with_tampered_subject(
    session: Session, provider: FakeProvider
) -> None:
    """A tampered subject token can be sent, to see the provider refuse it."""
    session.execute("exchange x --as gateway --from user --tamper-subject")
    _, form, _ = provider.posts[-1]
    assert form["subject_token"] != session.tokens["user"].access_token


def test_refusals_are_results(session: Session, provider: FakeProvider) -> None:
    """A refused exchange shows the provider's error and stores nothing."""
    provider.token_error = FakeResponse(400, {"error": "invalid_target"})
    result = session.execute("exchange x --as gateway --from user")
    assert result["ok"] is False
    assert result["error"] == "invalid_target"
    assert "x" not in session.tokens


@pytest.mark.parametrize(
    ("line", "message"),
    [
        ("exchange x --as gateway --from none", "No token"),
        ("exchange x --as nobody --from user", "No client"),
        ("exchange x --as gateway --from user --audience @nobody", "No client"),
        ("exchange x --as gateway --from user --audience @client.url", "No resource"),
        ("login x --mock-issuer short", "only works with the mock"),
        ("refresh x --as client --from nothing", "No token"),
        ("compare a b", "No saved report"),
        ("nonsense", "invalid choice"),
        ("exchange", "required"),
        ("show 'unbalanced", "quotation"),
    ],
)
def test_usage_errors(session: Session, line: str, message: str) -> None:
    """Invalid command lines give an error, and the session goes on."""
    result = session.execute(line)
    assert result["ok"] is False
    assert message in result["usage_error"]


def test_call_reports_each_hop(
    session: Session, provider: FakeProvider, ls_settings: Settings
) -> None:
    """Calls send the headers, keep the report and give one row per service."""
    report = {
        "service": "gateway",
        "token": {"claims": {"sub": "user-1", "aud": "id-gateway"}},
        "lifetime": {"exp_minus_iat": 3600},
        "next": {"service": "node", "token": {"claims": {"aud": "id-node"}}},
    }
    seen: dict[str, Any] = {}

    def answer(_url: str, options: dict[str, Any]) -> FakeResponse:
        """Answer the call and keep its options.

        Args:
            _url: URL.
            options: Options of the request.

        Returns:
            Response with the report.
        """
        seen.update(options)
        return FakeResponse(200, report)

    provider.routes[ls_settings.service_url("gateway")] = answer
    result = session.execute(
        "call gateway --token user --save r --hop-limit 2 --traceparent t --full"
    )
    assert result["status"] == 200
    assert [row["service"] for row in result["hops"]] == ["gateway", "node"]
    assert result["hops"][0]["lifetime"] == 3600
    assert result["report"] == report
    assert session.reports["r"] == report
    assert seen["headers"]["Hop-Limit"] == "2"
    assert seen["headers"]["traceparent"] == "t"


def test_call_with_id_token_and_tampering(
    session: Session, provider: FakeProvider, ls_settings: Settings
) -> None:
    """The ID token can be sent as if it were an access token, or a tampered one."""
    seen: list[str] = []

    def answer(_url: str, options: dict[str, Any]) -> FakeResponse:
        """Keep the token of the call.

        Args:
            _url: URL.
            options: Options of the request.

        Returns:
            Empty report.
        """
        seen.append(options["headers"]["Authorization"].removeprefix("Bearer "))
        return FakeResponse(401, {"service": "node"})

    provider.routes[ls_settings.service_url("node")] = answer
    session.execute("call node --token user --id-token")
    session.execute("call node --token user --tamper")
    held = session.tokens["user"]
    assert seen[0] == held.id_token
    assert seen[1] != held.access_token
    session.tokens["bare"] = TokenResponse(access_token="x")
    assert (
        "ID token"
        in session.execute("call node --token bare --id-token")["usage_error"]
    )


def test_refresh_reports_rotation(session: Session, provider: FakeProvider) -> None:
    """Redeeming shows whether the refresh token changed."""
    result = session.execute("refresh r --as client --from user")
    assert result["ok"]
    assert result["refresh_token_rotated"] is True
    result = session.execute("refresh r2 --as client --from r")
    assert result["refresh_token_rotated"] is False
    session.tokens["bare"] = TokenResponse(access_token=provider.mint())
    result = session.execute("refresh r3 --as client --from bare")
    assert "no refresh token" in result["usage_error"]


def test_no_rotation_info_without_a_new_refresh_token(
    session: Session, provider: FakeProvider
) -> None:
    """If no refresh token comes back, rotation is unknown."""
    provider.token_error = None
    base = provider.issuer.rstrip("/")
    provider.routes[f"{base}/token"] = lambda _url, _kw: FakeResponse(
        200, {"access_token": provider.mint()}
    )
    result = session.execute("refresh r --as client --from user")
    assert result["refresh_token_rotated"] is None


def test_other_commands(session: Session, provider: FakeProvider) -> None:
    """Information commands give results that hold no tokens or secrets."""
    provider.entitlements["user-1"] = ["urn:a"]
    results = {
        line: session.execute(line)
        for line in (
            "clients",
            "discovery",
            "show user",
            "userinfo user",
            "lifetimes",
            "introspect user --as node",
            "introspect user --as client --refresh",
            "credentials c --as gateway --scope openid",
            "revoke user --as client --refresh",
            "wait-expiry c --margin -100000",
            "help",
        )
    }
    assert results["clients"]["ls_login_rules_emulated"] is False
    assert results["clients"]["clients"]["public"]["has_secret"] is False
    assert results["userinfo user"]["entitlements"] == ["urn:a"]
    assert results["lifetimes"]["tokens"]["user"]["exp_minus_iat"] == 3600
    assert results["introspect user --as node"]["active"] is True
    assert results["revoke user --as client --refresh"]["ok"] is True
    text = json.dumps(results)
    assert "secret-" not in text
    assert "opaque-refresh-value" not in text
    assert "eyJ" not in text


def test_refresh_flag_needs_a_refresh_token(session: Session) -> None:
    """Commands about a refresh token need one."""
    session.tokens["bare"] = TokenResponse(access_token="opaque")
    result = session.execute("revoke bare --as client --refresh")
    assert "no refresh token" in result["usage_error"]
    assert "no `exp`" in session.execute("wait-expiry bare")["usage_error"]


def test_wait_expiry_waits(ls_settings: Settings, provider: FakeProvider) -> None:
    """Waiting uses the token's `exp`."""
    waits: list[float] = []
    session = Session(
        ls_settings, provider, output=lambda _line: None, sleep=waits.append
    )
    session.tokens["t"] = TokenResponse(access_token=provider.mint())
    assert session.execute("wait-expiry t")["ok"]
    assert 3500 < waits[0] < 3700


def test_login_with_device_flow(ls_settings: Settings, provider: FakeProvider) -> None:
    """The session stores the token of a device login."""
    base = provider.issuer.rstrip("/")
    provider.routes[f"{base}/device"] = lambda _url, _kw: FakeResponse(
        200,
        {"device_code": "d", "user_code": "U", "verification_uri": "https://x/"},
    )
    session = Session(
        ls_settings, provider, output=lambda _line: None, sleep=lambda _s: None
    )
    assert session.execute("login d --flow device")["ok"]
    assert "d" in session.tokens


def test_record_holds_no_tokens(
    ls_settings: Settings, provider: FakeProvider, tmp_path: Path
) -> None:
    """The record has decoded claims only."""
    path = tmp_path / "record.jsonl"
    session = Session(ls_settings, provider, output=lambda _line: None, record=path)
    session.tokens["user"] = TokenResponse(
        access_token=provider.mint(), refresh_token="opaque-refresh-value"
    )
    session.execute("show user")
    session.execute("exchange x --as gateway --from user --audience @node")
    text = path.read_text()
    entries = [json.loads(line) for line in text.splitlines()]
    assert entries[0]["result"]["claims"]["sub"] == "user-1"
    assert "eyJ" not in text
    assert "opaque-refresh-value" not in text
    assert "secret-" not in text


def test_interactive_session(session: Session) -> None:
    """Interactive sessions read commands until told to quit."""
    lines = iter(["", "# comment", "help", "show user", "quit", "never"])
    shown: list[str] = []
    session._output = shown.append
    session.run_interactive(lambda _prompt: next(lines))
    assert "login" in shown[0]
    assert json.loads(shown[1])["claims"]["sub"] == "user-1"
    assert len(shown) == 2


def test_interactive_session_ends_with_input(session: Session) -> None:
    """The end of the input ends the session."""

    def read(_prompt: str) -> str:
        """End the input.

        Args:
            _prompt: Prompt.

        Raises:
            EOFError: Always.
        """
        raise EOFError

    session.run_interactive(read)


def test_failures_do_not_end_the_session(
    session: Session, provider: FakeProvider, ls_settings: Settings
) -> None:
    """Tokens exist only in the session, so that failures must not end it."""

    def fail(_url: str, _options: dict[str, Any]) -> FakeResponse:
        """Fail with a message that could hold a value.

        Args:
            _url: URL.
            _options: Options of the request.

        Raises:
            ConnectionError: Always.
        """
        raise ConnectionError("value")

    provider.routes[ls_settings.service_url("node")] = fail
    result = session.execute("call node --token user")
    assert result == {"ok": False, "failure": "ConnectionError"}
    assert session.tokens["user"]


def test_interrupt_keeps_the_session(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Interrupting a command, e.g., a wait, keeps the session and its tokens."""
    lines = iter(["show user", "quit"])
    shown: list[str] = []
    session._output = shown.append

    def interrupt(_line: str) -> dict[str, Any]:
        """Interrupt the command.

        Args:
            _line: Command line.

        Raises:
            KeyboardInterrupt: Always.
        """
        raise KeyboardInterrupt

    monkeypatch.setattr(session, "execute", interrupt)
    session.run_interactive(lambda _prompt: next(lines))
    assert shown == ["Interrupted."]
    assert session.tokens["user"]


def _follow_callback(url: str, _options: dict[str, Any]) -> FakeResponse:
    """Send a redirect to the local callback, like a browser.

    Args:
        url: URL.
        _options: Options of the request.

    Returns:
        Response.
    """
    http = requests.Session()
    http.trust_env = False
    return FakeResponse(http.get(url, timeout=5).status_code)


def _login_form(url: str, options: dict[str, Any]) -> FakeResponse:
    """Answer the mock's login form with a redirect to the callback.

    Args:
        url: Authorization URL.
        options: Options of the request.

    Returns:
        Response.
    """
    FORMS.append(options["data"])
    query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    state = query["state"][0]
    location = f"{login.REDIRECT_URI}?code=the-code&state={state}"
    return FakeResponse(302, {}, {"Location": location})


FORMS: list[dict[str, Any]] = []


@pytest.mark.parametrize(
    ("user", "entitlements"), [("inside", [MOCK_ENTITLEMENT]), ("outside", [])]
)
def test_login_at_the_mock_fills_in_its_form(
    mock_settings: Settings,
    mock_provider: FakeProvider,
    user: str,
    entitlements: list[str],
) -> None:
    """The mock's login form gets the made-up user, and no browser is needed."""
    FORMS.clear()
    mock_provider.routes[f"{MOCK_ISSUER}/authorize"] = _login_form
    mock_provider.routes[login.REDIRECT_URI] = _follow_callback
    session = Session(mock_settings, mock_provider, output=lambda _line: None)
    assert session.execute(f"login u --as client --mock-user {user}")["ok"]
    assert FORMS[0]["username"] == f"test-user-{user}"
    assert json.loads(FORMS[0]["claims"]).get("entitlements", []) == entitlements


def test_login_at_another_issuer_of_the_mock(mock_settings: Settings) -> None:
    """`--mock-issuer` logs in at that issuer."""
    short = FakeProvider(MOCK_SHORT_ISSUER)
    short.routes[f"{MOCK_SHORT_ISSUER}/authorize"] = _login_form
    short.routes[login.REDIRECT_URI] = _follow_callback
    session = Session(mock_settings, short, output=lambda _line: None)
    assert session.execute("login s --as client --mock-issuer short")["ok"]


def test_mock_options_only_work_with_the_mock(session: Session) -> None:
    """Asking LS Login for a mock issuer is a usage error."""
    result = session.execute("login s --mock-issuer short")
    assert "only works with the mock" in result["usage_error"]


@pytest.mark.parametrize(("flag", "opened"), [("", 1), (" --no-browser", 0)])
def test_login_at_a_real_provider_shows_the_url(
    ls_settings: Settings,
    provider: FakeProvider,
    monkeypatch: pytest.MonkeyPatch,
    flag: str,
    opened: int,
) -> None:
    """The user gets the URL, and a browser unless told otherwise."""
    shown: list[str] = []
    browsers: list[str] = []

    def open_browser(url: str) -> bool:
        """Return to the callback, like a user logging in.

        Args:
            url: Authorization URL.

        Returns:
            Whether a browser opened.
        """
        browsers.append(url)
        return True

    def output(line: str) -> None:
        """Keep a line, and act on the login URL like a user.

        Args:
            line: Line of output.
        """
        shown.append(line)
        url = line.removeprefix("Log in at: ")
        state = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["state"][0]
        _follow_callback(f"{login.REDIRECT_URI}?code=the-code&state={state}", {})

    monkeypatch.setattr("testbed.session.webbrowser.open", open_browser)
    session = Session(ls_settings, provider, output=output)
    assert session.execute(f"login u --as client{flag}")["ok"]
    assert shown[0].startswith("Log in at: ")
    assert len(browsers) == opened


def test_invalid_command_lines_are_usage_errors(session: Session) -> None:
    """Invalid command lines end in a message, not in the end of the session."""
    assert "usage_error" in session.execute("no-such-command")
    assert "usage_error" in session.execute("show")
    assert "No saved report" in session.execute("compare a b")["usage_error"]
    assert (
        "No client"
        in session.execute("exchange x --as nobody --from user")["usage_error"]
    )


def test_targets_without_a_resource_indicator_are_usage_errors(
    session: Session,
) -> None:
    """A URL form that isn't configured is named."""
    line = "exchange x --as client --from user --resource @gateway.url"
    assert "No resource indicator" in session.execute(line)["usage_error"]


def test_targets_are_used_as_they_are(session: Session, provider: FakeProvider) -> None:
    """Values that aren't shorthands reach the provider unchanged."""
    line = "exchange x --as client --from user --audience https://any.example/"
    assert session.execute(line)["ok"]
    assert provider.posts[-1][1]["audience"] == ["https://any.example/"]


def test_unexpected_errors_keep_the_session_alive(
    session: Session, provider: FakeProvider
) -> None:
    """A failure shows its type only, as messages could hold values."""

    def fail(_url: str, _options: dict[str, Any]) -> FakeResponse:
        """Fail with a message that must not be shown.

        Args:
            _url: URL.
            _options: Options of the request.

        Raises:
            RuntimeError: Always.
        """
        raise RuntimeError("do-not-show")

    provider.routes[f"{provider.issuer.rstrip('/')}/userinfo"] = fail
    assert session.execute("userinfo user") == {"ok": False, "failure": "RuntimeError"}


def test_main_runs_a_session_and_records(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The command line starts a session; folders of the record are created."""
    record = tmp_path / "new" / "session.jsonl"
    monkeypatch.setattr("sys.stdin", io.StringIO("clients\nquit\n"))
    monkeypatch.setattr(
        sys, "argv", ["testbed-session", "--provider", "mock", "--record", str(record)]
    )
    main()
    assert '"provider": "mock"' in capsys.readouterr().out
    assert '"clients"' in record.read_text()


def test_main_without_a_record(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A record is optional."""
    monkeypatch.setattr("sys.stdin", io.StringIO("quit\n"))
    monkeypatch.setattr(sys, "argv", ["testbed-session", "--provider", "mock"])
    main()
    assert capsys.readouterr().out == "tb> "


def test_main_names_missing_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Missing variables end the program with their names."""
    for name in list(os.environ):
        if name.startswith("TESTBED_"):
            monkeypatch.delenv(name)
    monkeypatch.setattr(sys, "argv", ["testbed-session", "--provider", "lslogin"])
    with pytest.raises(SystemExit, match="TESTBED_NODE_CLIENT_ID"):
        main()


def test_main_refuses_a_record_it_cannot_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A problem with the record shows up before any token exists."""
    blocker = tmp_path / "file"
    blocker.write_text("")
    monkeypatch.setattr(
        sys,
        "argv",
        ["testbed-session", "--provider", "mock", "--record", f"{blocker}/session"],
    )
    with pytest.raises(SystemExit, match="Can't write"):
        main()


def test_unknown_options_are_usage_errors(session: Session) -> None:
    """Options that a command doesn't have end in a message, too."""
    assert (
        "unrecognized" in session.execute("show user --no-such-option")["usage_error"]
    )


def test_unregistered_target_is_one_no_client_has(
    session: Session, provider: FakeProvider
) -> None:
    """The shorthand stands for a target that nothing registers."""
    assert session.execute(
        "exchange x --as client --from user --audience @unregistered"
    )["ok"]
    assert provider.posts[-1][1]["audience"] == [NOT_REGISTERED]


def test_compare_uses_saved_reports(session: Session) -> None:
    """Saved calls can be compared by name."""
    session.reports["a"] = _chain("gateway", "node")
    session.reports["b"] = _chain("orchestrator", "gateway", "node")
    result = session.execute("compare a b")
    assert result["hops"] == [2, 3]
    assert result["identical_at_last_hop"] is True


def test_provider_problems_are_named(session: Session, provider: FakeProvider) -> None:
    """A provider that can't be reached is told apart from a refusal."""
    discovery = f"{provider.issuer.rstrip('/')}/.well-known"
    provider.routes[discovery] = lambda _url, _options: FakeResponse(500)
    assert "Discovery failed" in session.execute("discovery")["provider_problem"]


def test_parser_never_exits() -> None:
    """Argparse's way out would end the session and lose its tokens."""
    with pytest.raises(UsageError, match="the problem"):
        _build_parser().error("the problem")


def test_refresh_keeps_the_old_refresh_token_without_a_new_one(
    session: Session, provider: FakeProvider
) -> None:
    """Without rotation, the new entry can still be refreshed and introspected."""
    base = provider.issuer.rstrip("/")
    provider.routes[f"{base}/token"] = lambda _url, _kw: FakeResponse(
        200, {"access_token": provider.mint()}
    )
    held = session.tokens["user"].refresh_token
    assert held
    result = session.execute("refresh r1 --as client --from user")
    assert result["refresh_token"]["present"] is True
    assert session.tokens["r1"].refresh_token == held
    assert session.execute("introspect r1 --as client --refresh")["ok"]
    result = session.execute("refresh r2 --as client --from r1")
    assert result["ok"]
    assert provider.posts[-1][1]["refresh_token"] == held
    assert result["refresh_token_rotated"] is None
    assert session.tokens["r2"].refresh_token == held


def test_refresh_token_issued_as_the_exchanged_token_is_usable(
    session: Session, provider: FakeProvider
) -> None:
    """RFC 8693 returns a requested refresh token in `access_token`."""
    session.tokens["ro"] = TokenResponse(
        access_token="opaque-refresh", issued_token_type=TYPE_REFRESH
    )
    assert session.tokens["ro"].view()["refresh_token"]["present"] is True
    assert session.execute("refresh r --as orchestrator --from ro")["ok"]
    assert provider.posts[-1][1]["refresh_token"] == "opaque-refresh"
    assert session.execute("revoke ro --as orchestrator --refresh")["ok"]
    revoked = provider.posts[-1][1]
    assert revoked["token"] == "opaque-refresh"
    assert revoked["token_type_hint"] == "refresh_token"
    assert (
        "is a refresh token"
        in session.execute("call gateway --token ro")["usage_error"]
    )


def test_record_never_holds_a_token_from_the_command_line(
    ls_settings: Settings, provider: FakeProvider, tmp_path: Path
) -> None:
    """A token pasted into a command is removed from the record."""
    record = tmp_path / "record.jsonl"
    session = Session(ls_settings, provider, output=lambda _line: None, record=record)
    token = provider.mint()
    session.execute(f"show {token}")
    assert token not in record.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "line",
    [
        "exchange x --as gateway --from ro --audience @node",
        "userinfo ro",
        "introspect ro --as orchestrator",
        "call gateway --token ro",
        "wait-expiry ro",
    ],
)
def test_refresh_token_is_never_used_as_an_access_token(
    session: Session, line: str
) -> None:
    """A token issued as a refresh token can only be redeemed."""
    session.tokens["ro"] = TokenResponse(
        access_token="opaque-refresh", issued_token_type=TYPE_REFRESH
    )
    assert "is a refresh token" in session.execute(line)["usage_error"]


def test_lifetimes_of_a_refresh_token(session: Session, provider: FakeProvider) -> None:
    """The times of a refresh token aren't those of an access token."""
    session.tokens["ro"] = TokenResponse(
        access_token=provider.mint(), issued_token_type=TYPE_REFRESH
    )
    row = session.execute("lifetimes")["tokens"]["ro"]
    assert row["refresh_token"] is True
    assert row["exp_minus_iat"] is None


def test_lifetimes_survive_times_of_the_wrong_type(
    session: Session, provider: FakeProvider
) -> None:
    """One odd token doesn't cost the rows of the others."""
    session.tokens["odd"] = TokenResponse(access_token=provider.mint(exp="soon"))
    rows = session.execute("lifetimes")["tokens"]
    assert rows["odd"]["seconds_left"] is None
    assert rows["odd"]["exp_minus_iat"] is None
    assert rows["user"]["seconds_left"] > 0


def test_record_leaves_out_the_arguments_of_commands_that_cannot_run(
    ls_settings: Settings, provider: FakeProvider, tmp_path: Path
) -> None:
    """An opaque token pasted in place of a name doesn't reach the record."""
    record = tmp_path / "record.jsonl"
    session = Session(ls_settings, provider, output=lambda _line: None, record=record)
    session.execute("call gateway --token opaque-secret-value")
    assert "opaque-secret-value" not in record.read_text(encoding="utf-8")
    assert json.loads(record.read_text(encoding="utf-8"))["command"] == "call"
